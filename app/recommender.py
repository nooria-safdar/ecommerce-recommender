"""Naya model (Hybrid) - notebook se export hui CSV files se recommendations deta hai."""
import os
import pandas as pd

SYN_MIN = 990000001


class NewModel:
    def __init__(self, folder):
        recs = pd.read_csv(os.path.join(folder, "recommendations_top10_all.csv"))
        recs = recs[recs["mode"] == "discovery"].sort_values(["user_id", "rank"])   # sirf nayi cheezein
        self.by_user = {int(u): g["product_id"].astype(int).tolist() for u, g in recs.groupby("user_id")}

        cold_real = pd.read_csv(os.path.join(folder, "cold_start_top10.csv")).sort_values("rank")
        cold_syn = pd.read_csv(os.path.join(folder, "cold_start_top10_synthetic.csv")).sort_values("rank")
        self.cold = {"real": cold_real["product_id"].astype(int).tolist(),
                     "synthetic": cold_syn["product_id"].astype(int).tolist()}

    def recommend(self, user_id, k=10):
        user_id = int(user_id)
        segment = "synthetic" if user_id >= SYN_MIN else "real"
        if user_id in self.by_user:
            how = ("Hybrid model (collaborative filtering + SVD + KMeans user groups + 7-day popularity), "
                   "only products the user has not seen before")
            return self.by_user[user_id][:k], how, segment
        how = "Popularity (last 7 days): this user has no history in the model yet"
        return self.cold[segment][:k], how, segment