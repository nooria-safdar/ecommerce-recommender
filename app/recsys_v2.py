"""Improved recommendations: the products a user is closest to buying.

Model: item-based collaborative filtering.
1. Products left in the cart (added but not bought) come first.
2. Then products that other customers bought/viewed together with this user's products.
3. A small popularity bonus helps to find new products.
4. Products the user already bought are never shown again.
"""
import numpy as np

from recsys import Recommender as BaseRecommender


class Recommender(BaseRecommender):

    def _cf_reasons(self, row, picks):
        """For each recommended product: the history product it is most similar to."""
        out = []
        for j in picks:
            contrib = row * self.S[:, j]
            i = int(np.argmax(contrib))
            out.append(self.products.at[i, "product_name"] if contrib[i] > 0 else "")
        return out

    def recommend_user(self, user_id, k=10):
        user_id = int(user_id)
        ev = self._events_by_user.get(user_id)
        row = self._row_from_events(user_id)          # uses ALL of the user's history
        if ev is None or row.sum() == 0:
            return self.recommend_new(k=k)

        def idx(kind):
            ids = ev.loc[ev["event_type"] == kind, "product_id"]
            return [self.i_idx[int(p)] for p in set(ids) if int(p) in self.i_idx]

        bought, carted, removed = idx("purchase"), idx("cart"), idx("remove_from_cart")

        x = row @ self.S                               # collaborative filtering score
        s = x / (x.max() + 1e-9) + 0.3 * self.pop_n    # + small bonus for popular products
        in_cart = np.zeros(len(s), bool)
        in_cart[carted] = True
        in_cart[bought] = False
        s[in_cart] += 1.0                              # left in the cart = closest to buying
        s[removed] -= 0.5                              # removed from the cart = less likely
        s[bought] = -np.inf                            # already bought: never show again

        picks = self._top(s, k)
        reasons = self._cf_reasons(row, picks)
        for n, j in enumerate(picks):
            if in_cart[j]:
                reasons[n] = "In your cart"

        how = ("Item-based collaborative filtering: items left in the cart come first, then products "
               "that customers with similar behaviour liked (already bought items are hidden)")
        return self._table(picks, s, reasons), how