"""Recommendation engine used by the dashboard."""
from pathlib import Path
import json
import re

import numpy as np
import pandas as pd
from scipy.sparse import load_npz

CLUSTER_NAMES = {
    0: "Heavy browsers (cosmetics)",
    1: "Quick buyers (cosmetics)",
    2: "Sports, fashion & electronics shoppers",
    3: "Window shoppers (cosmetics)",
}

PRICE_LABELS = ["Low", "Mid", "High"]


class Recommender:
    def __init__(self, root):
        root = Path(root)
        models, data = root / "models", root / "data"

        cfg = json.loads((models / "config.json").read_text())
        self.cfg = cfg
        self.weights = [1.0, 0.0, 0.0]   # sirf Collaborative Filtering (S), SS aur C band
        self.cap = float(cfg["rating_cap"])
        self.event_w = cfg["rating_weights"]
        self.synthetic_from = int(cfg["synthetic_user_id_from"])

        # saved model parts
        self.R = load_npz(models / "R.npz").tocsr()
        sim = np.load(models / "similarity.npz")
        self.S, self.SS, self.C = sim["S"], sim["SS"], sim["C"]
        self.item_ids = np.load(models / "item_ids.npy")
        self.user_ids = np.load(models / "user_ids.npy")
        self.u_idx = {int(u): i for i, u in enumerate(self.user_ids)}
        self.i_idx = {int(p): i for i, p in enumerate(self.item_ids)}

        pop = np.asarray(self.R.sum(axis=0)).ravel()
        self.pop_n = pop / pop.max()

        # used only to explain "because of X"
        w = self.weights
        self.M_explain = w[0] * self.S + w[1] * self.SS + w[2] * self.C

        # tables
        prod = pd.read_csv(data / "products.csv").set_index("product_id")
        prod = prod.reindex(self.item_ids)
        prod.insert(0, "product_id", prod.index.values)
        prod = prod.reset_index(drop=True)
        rank = prod.groupby("main_category")["price"].rank(pct=True)
        prod["price_bucket"] = np.where(rank <= 1 / 3, "Low", np.where(rank <= 2 / 3, "Mid", "High"))
        self.products = prod
        self.categories = sorted(prod["main_category"].unique())

        users = pd.read_csv(data / "users.csv")
        self.label_to_id = {r.user_label.upper(): int(r.user_id) for r in users.itertuples()}
        self.id_to_label = {int(r.user_id): r.user_label for r in users.itertuples()}
        self.all_user_ids = users["user_id"].astype(int).tolist()

        ev = pd.read_csv(data / "events.csv", parse_dates=["event_time"])
        ev = ev.merge(prod[["product_id", "product_name", "main_category", "price_pkr"]],
                      on="product_id", how="left")
        self.events = ev.sort_values("event_time")
        self._events_by_user = {u: g for u, g in self.events.groupby("user_id")}

        cl = pd.read_csv(models / "user_clusters.csv")
        self.cluster_of = dict(zip(cl["user_id"].astype(int), cl["cluster"].astype(int)))

        metrics = models / "metrics.csv"
        self.metrics = pd.read_csv(metrics) if metrics.exists() else None

    # ------------------------------------------------------------------ users
    def find_user(self, text):
        """Accepts a numeric user_id or a label such as U0042. Returns user_id or None."""
        text = str(text).strip()
        if not text:
            return None
        m = re.fullmatch(r"[uU]\s*0*(\d+)", text)
        if m:
            return self.label_to_id.get("U%04d" % int(m.group(1)))
        if text.isdigit() and int(text) in self.id_to_label:
            return int(text)
        return None

    def is_synthetic(self, user_id):
        return int(user_id) >= self.synthetic_from

    def user_profile(self, user_id):
        ev = self._events_by_user.get(int(user_id))
        if ev is None:
            return None
        counts = ev["event_type"].value_counts()
        buy = ev[ev["event_type"] == "purchase"]
        cats = ev[ev["event_type"] != "remove_from_cart"]["main_category"].value_counts(normalize=True)
        c = self.cluster_of.get(int(user_id))
        return {
            "user_id": int(user_id),
            "label": self.id_to_label.get(int(user_id), str(user_id)),
            "synthetic": self.is_synthetic(user_id),
            "views": int(counts.get("view", 0)),
            "carts": int(counts.get("cart", 0)),
            "purchases": int(counts.get("purchase", 0)),
            "unique_products": int(ev["product_id"].nunique()),
            "avg_spend_pkr": float(buy["price_pkr"].mean()) if len(buy) else float("nan"),
            "category_share": cats,
            "cluster": c,
            "cluster_name": CLUSTER_NAMES.get(c, "Not clustered") if c is not None else "Not clustered",
            "in_model": int(user_id) in self.u_idx,
        }

    def user_history(self, user_id, n=10):
        ev = self._events_by_user.get(int(user_id))
        if ev is None:
            return pd.DataFrame()
        out = ev[ev["event_type"] != "remove_from_cart"].tail(n).iloc[::-1]
        return out[["event_time", "event_type", "product_name", "main_category", "price_pkr"]]

    # ---------------------------------------------------------------- scoring
    def _hybrid(self, row):
        """Hybrid+ score for every product given a user's rating vector."""
        s = np.zeros(len(self.item_ids))
        for M, wt in zip((self.S, self.SS, self.C), self.weights):
            x = row @ M
            s += wt * x / (x.max() + 1e-9)
        return s + 1e-3 * self.pop_n

    def _reasons(self, row, picks):
        """For each recommended product, the history item that pushed it the most."""
        out = []
        for j in picks:
            contrib = row * self.M_explain[:, j]
            i = int(np.argmax(contrib))
            out.append(self.products.at[i, "product_name"] if contrib[i] > 0 else "")
        return out

    def _table(self, picks, scores, reasons):
        t = self.products.iloc[picks].copy()
        t["score"] = scores[picks]
        t["reason"] = reasons
        return t.reset_index(drop=True)

    def _top(self, s, k):
        top = np.argpartition(-s, k)[:k]
        return top[np.argsort(-s[top])]

    def _row_from_events(self, user_id):
        """Rating vector built from raw events (same weights as training)."""
        ev = self._events_by_user.get(int(user_id))
        row = np.zeros(len(self.item_ids))
        if ev is None:
            return row
        for pid, et in zip(ev["product_id"], ev["event_type"]):
            i = self.i_idx.get(int(pid))
            if i is not None:
                row[i] += self.event_w.get(et, 0)
        return np.minimum(row, self.cap)

    # ------------------------------------------------------------ existing user
    def recommend_user(self, user_id, k=10):
        """Returns (table, strategy text)."""
        user_id = int(user_id)
        if user_id in self.u_idx:
            row = self.R[self.u_idx[user_id]].toarray().ravel()
            how = "Item-based collaborative filtering on the user's history"
        else:
            row = self._row_from_events(user_id)
            how = "Item-based collaborative filtering using the user's events (user was too sparse to be in the training matrix)"
        if row.sum() == 0:
            return self.recommend_new(k=k)
        s = self._hybrid(row)
        ev = self._events_by_user.get(user_id)
        if ev is not None:
            bought = ev.loc[ev["event_type"] == "purchase", "product_id"].unique()
            idx = [self.i_idx[int(p)] for p in bought if int(p) in self.i_idx]
            if idx:
                s[idx] = -np.inf
        picks = self._top(s, k)
        return self._table(picks, s, self._reasons(row, picks)), how
    # ---------------------------------------------------------------- new user
    def recommend_new(self, categories=None, price_pref=None, liked=None, k=10):
        """Cold start.
        1. nothing at all       -> most popular products overall
        2. categories (+price)  -> most popular products inside those categories
        3. liked products       -> Hybrid+ similarity to those products
        """
        cats = list(categories or [])
        liked_idx = [self.i_idx[int(p)] for p in (liked or []) if int(p) in self.i_idx]
        p = self.products
        cat_mask = p["main_category"].isin(cats).values if cats else np.ones(len(p), bool)
        price_f = np.ones(len(p))
        if price_pref in PRICE_LABELS:
            price_f = np.where(p["price_bucket"].values == price_pref, 1.0, 0.6)

        row = np.zeros(len(p))
        if liked_idx:
            row[liked_idx] = self.cap
            s = self._hybrid(row)
            s = s / (s.max() + 1e-9)
            if cats:
                s = s * np.where(cat_mask, 1.0, 0.4)
            how = "Cold start: products similar to the ones you picked (item similarity)"
            if cats:
                how += ", favouring your categories"
            s = s * price_f
            s[liked_idx] = -np.inf
        elif cats:
            s = self.pop_n * cat_mask * price_f
            how = "Cold start: most popular products in your chosen categories"
        else:
            s = self.pop_n * price_f
            how = "Cold start: most popular products overall (no information about this user yet)"
        picks = self._top(s, k)
        reasons = self._reasons(row, picks) if liked_idx else [""] * len(picks)
        return self._table(picks, s, reasons), how

    def popular_in(self, categories, n=30):
        """Most popular products in the given categories."""
        mask = self.products["main_category"].isin(categories).values if categories else np.ones(len(self.products), bool)
        order = np.argsort(-(self.pop_n * mask))[:n]
        return self.products.iloc[order]