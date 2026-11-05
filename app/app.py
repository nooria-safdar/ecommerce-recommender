import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flask import Flask, jsonify, render_template, request
import os
import json
import numpy as np
import pandas as pd
from recsys_v2 import Recommender
from recommender import NewModel

app = Flask(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))               # app folder
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

# Product information
products = pd.read_csv(os.path.join(DATA_DIR, "products.csv"))
image_map = pd.read_csv(os.path.join(DATA_DIR, "product_image_map.csv")).fillna("")
products = products.merge(image_map, on="product_id", how="left")
products["image_file"] = products["image_file"].fillna("")

# Data used for the 4 number cards
users = pd.read_csv(os.path.join(DATA_DIR, "users.csv"))
events = pd.read_csv(os.path.join(DATA_DIR, "events.csv"))
sellers = pd.read_csv(os.path.join(DATA_DIR, "sellers.csv"))
offers = pd.read_csv(os.path.join(DATA_DIR, "seller_offers.csv"))

# Cold-start (category picking) engine + profile helper
rec = Recommender(ROOT)

# NEW MODEL (notebook se export hui files)
new_model = NewModel(HERE)
try:
    with open(os.path.join(HERE, "metrics.json")) as f:
        NEW_METRICS = json.load(f)
except Exception:
    NEW_METRICS = {}

# ---------- Badges for the product cards (all from real data) ----------
shown_events = events[events["event_type"] != "remove_from_cart"]
interaction_count = shown_events.groupby("product_id").size()
purchase_count = events[events["event_type"] == "purchase"].groupby("product_id").size()

POPULAR = set(interaction_count[interaction_count >= interaction_count.quantile(0.85)].index)
BEST_SELLER = set(purchase_count[purchase_count >= purchase_count.quantile(0.95)].index)

event_day = pd.to_datetime(shown_events["event_time"], utc=True)
last_week = shown_events[event_day >= event_day.max() - pd.Timedelta(days=7)]
recent_count = last_week.groupby("product_id").size()
normal_week = interaction_count * 7 / ((event_day.max() - event_day.min()).days + 1)
TRENDING = set(recent_count[
    (recent_count >= 8) & (recent_count >= 1.5 * normal_week.reindex(recent_count.index))
].index)

_prod_by_id = rec.products.drop_duplicates("product_id").set_index("product_id", drop=False)


def to_cards(table):
    """Turns the recommendation table into the list of product cards sent to the browser."""
    table = table.merge(products[["product_id", "image_file"]], on="product_id", how="left")
    cards = table[[
        "product_id", "product_name", "main_category", "brand",
        "price_pkr", "avg_rating", "review_count", "image_file", "reason"
    ]].replace({np.nan: None}).to_dict(orient="records")

    for c in cards:
        pid = c["product_id"]
        if (c["reason"] or "").startswith("In your cart"):
            c["badge"] = "In your cart"
        elif pid in BEST_SELLER:
            c["badge"] = "Best Seller"
        elif pid in TRENDING:
            c["badge"] = "Trending"
        elif pid in POPULAR:
            c["badge"] = "Popular"
        else:
            c["badge"] = "Recommended"
    return cards


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/summary")
def summary():
    return jsonify({
        "products": int(len(products)),
        "users": int(len(users)),
        "interactions": int(len(events)),
        "sellers": int(len(sellers))
    })


@app.route("/api/search")
def search_products():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    text = (
        products["product_name"] + " "
        + products["brand"].fillna("") + " "
        + products["main_category"]
    ).str.lower()

    match = text.str.contains(q, regex=False) | (products["product_id"].astype(str) == q)
    found = products[match].head(8)

    return jsonify(
        found[["product_id", "product_name", "main_category", "image_file"]]
        .to_dict(orient="records")
    )


@app.route("/api/offers/<int:product_id>")
def product_offers(product_id):
    product = products[products["product_id"] == product_id]
    if product.empty:
        return jsonify({"error": "Product not found"}), 404
    p = product.iloc[0]

    o = offers[offers["product_id"] == product_id].merge(
        sellers[["seller_id", "seller_name"]], on="seller_id", how="left"
    )
    o = o.sort_values("total_cost_pkr")

    best_id = None
    if not o.empty:
        in_stock = o[o["stock"] != "Out of Stock"]
        best_id = (in_stock if len(in_stock) else o).iloc[0]["seller_id"]

    rows = []
    for r in o.itertuples():
        rows.append({
            "seller": r.seller_name,
            "price": int(r.price_pkr),
            "shipping": int(r.shipping_pkr),
            "total": int(r.total_cost_pkr),
            "rating": float(r.rating),
            "reviews": int(r.review_count),
            "stock": r.stock,
            "quality": r.quality,
            "best": bool(r.seller_id == best_id)
        })

    return jsonify({
        "product": {
            "product_id": int(p["product_id"]),
            "name": p["product_name"],
            "category": p["main_category"],
            "image_file": p["image_file"]
        },
        "offers": rows
    })


@app.route("/api/analytics")
def analytics():
    shown = events[events["event_type"] != "remove_from_cart"]

    # 1) Top 5 most popular products
    names = products.set_index("product_id")["product_name"]
    top = shown["product_id"].value_counts().head(5)
    top_products = [{"name": names[pid], "count": int(c)} for pid, c in top.items()]

    # 2) Interactions by category
    cat = (
        shown.merge(products[["product_id", "main_category"]], on="product_id")
        ["main_category"].value_counts()
    )
    categories = [{"name": k, "count": int(v)} for k, v in cat.items()]

    # 3) Activity per day
    daily = (
        events.assign(day=events["event_time"].str[:10])
        .groupby(["day", "event_type"]).size()
        .unstack(fill_value=0).reset_index()
    )
    daily_rows = [
        {"day": r.day, "views": int(r.view), "carts": int(r.cart), "purchases": int(r.purchase)}
        for r in daily.itertuples()
    ]

    # 4) NEW model results (notebook ke final test + backtest se)
    model, model_table = {}, []
    warm_path = os.path.join(HERE, "test_results_warm.csv")
    if os.path.exists(warm_path):
        warm = pd.read_csv(warm_path)
        nice = {"FINAL hybrid": "Hybrid (final model)", "CF": "Collaborative filtering",
                "SVD n=50": "SVD (50 factors)", "Popularity (7d, real)": "Popularity (7 days)"}
        for _, r in warm.iterrows():
            row = {
                "model": nice.get(r["model"], r["model"]),
                "final": bool(r["model"] == "FINAL hybrid"),
                "users": int(r["users"]),
                "hit_old": round(float(r["hit_resurface"]), 3),
                "hit_new": round(float(r["hit_DISCOVERY"]), 3),
                "ci_lo": round(float(r["disc_ci_lo"]), 3),
                "ci_hi": round(float(r["disc_ci_hi"]), 3),
                "ndcg": round(float(r["ndcg_DISCOVERY"]), 3),
            }
            model_table.append(row)
            if row["final"]:
                model["real"] = row

    syn = NEW_METRICS.get("synthetic_segment_validation")
    if syn:
        model["synthetic"] = {"users": syn["users"], "hit": syn["hit@10_new_items"],
                              "ci_lo": syn["ci"][0], "ci_hi": syn["ci"][1]}
    bt = NEW_METRICS.get("rolling_backtest_one_row_per_user")
    if bt:
        model["backtest"] = {"users": bt["users"], "hit_diff": bt["hit_diff_vs_popularity"],
                             "ndcg_diff": bt["ndcg_diff_vs_popularity"]}

    return jsonify({
        "top_products": top_products,
        "categories": categories,
        "daily": daily_rows,
        "model": model,
        "model_table": model_table,
    })


@app.route("/api/categories")
def categories():
    return jsonify(list(rec.categories))


@app.route("/api/new-user")
def new_user():
    cats = [c for c in request.args.get("categories", "").split(",") if c]
    price = request.args.get("price") or None
    liked = [int(x) for x in request.args.get("liked", "").split(",") if x.isdigit()]

    table, how = rec.recommend_new(cats, price, liked, 10)
    recommendations = to_cards(table)

    return jsonify({"method": how, "recommendations": recommendations})


@app.route("/api/user/<int:user_id>")
def user_dashboard(user_id):
    if user_id not in rec.id_to_label:
        return jsonify({"error": "User ID not found"}), 404

    # ---- NAYA MODEL ----
    ids, how, segment = new_model.recommend(user_id, 10)
    ids = [p for p in ids if p in _prod_by_id.index]
    table = _prod_by_id.loc[ids].reset_index(drop=True).copy()
    table["reason"] = ""
    recommendations = to_cards(table)

    # User profile for the dashboard
    profile = None
    p = rec.user_profile(user_id)
    if p is not None:
        spend = p["avg_spend_pkr"]
        recent = [
            {
                "time": r.event_time.strftime("%d %b %H:%M"),
                "action": r.event_type,
                "product": r.product_name,
                "category": r.main_category,
            }
            for r in rec.user_history(user_id, 6).itertuples()
        ]
        profile = {
            "label": p["label"],
            "type": "Synthetic user (demo)" if segment == "synthetic" else "Real user",
            "group": p["cluster_name"],
            "views": p["views"],
            "carts": p["carts"],
            "purchases": p["purchases"],
            "products": p["unique_products"],
            "avg_spend": None if pd.isna(spend) else int(spend),
            "interests": [
                {"name": k, "percent": round(float(v) * 100, 1)}
                for k, v in p["category_share"].head(5).items()
            ],
            "recent": recent,
        }

    return jsonify({
        "user_id": int(user_id),
        "method": how,
        "total_recommendations": len(recommendations),
        "recommendations": recommendations,
        "profile": profile,
    })


if __name__ == "__main__":
    app.run(debug=True)
