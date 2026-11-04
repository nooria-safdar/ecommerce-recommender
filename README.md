# E-commerce Product Recommendation System

[Live Demo](https://YOUR-APP.vercel.app)

![Workflow](assets/workflow-diagram.png)

## Overview
Online stores lose sales when customers can't find what they want. This project recommends products to each customer using their **browsing and purchase history** (views, add-to-cart, purchases), and handles **new users with no history** (cold start) with a separate popularity-based approach.

## Aim
- Recommend the top 10 products a customer is most likely to buy next
- Learn from implicit feedback (view, cart, purchase) since there are no star ratings
- Serve new users with no history using recent popular products
- Evaluate honestly on a time-based split, with no data leakage

## Key Features
- **Implicit ratings**: events converted to scores (view = 1, cart = 1.5, purchase = 2, capped at 2)
- **Hybrid recommender**: Item-based Collaborative Filtering + SVD (50 factors) + K-Means user clusters (K = 8) + 7-day popularity, equal weights (0.25 each)
- **Cold-start handling**: new users get top products by recent popularity
- **Honest evaluation**: two modes, *resurface* (previously viewed items allowed) and *discovery* (only brand-new items), with bootstrap confidence intervals
- **Rolling backtest**: 4 time windows to check that gains over popularity are real
- **Exported artifacts**: top-10 recommendations per user (CSV), model (joblib), metrics (JSON) for the dashboard

## Data
Event logs (`events.csv`), `products.csv`, `users.csv`, `seller_offers.csv`.
Users with ID >= 990000001 are **synthetic** (demo only); the main model is trained and evaluated on **real users only**.
The raw data is not included in this repo. Put it in `data/` before running the notebook.

## Method
1. Cleaning and EDA (nulls, duplicates, outliers, VIF multicollinearity, statistical tests)
2. Time-based split: train before 2019-12-20, test from 2019-12-20; validation 13-19 Dec
3. User-item matrix, then Popularity, CF, SVD, NMF baselines
4. Clustering (silhouette + elbow) and hybrid weight search on validation
5. One-time final test, rolling backtest, export

## Results (honest summary)
| Setting | Result |
|---|---|
| Final test, new items, 161 users | Hybrid Hit@10 = 0.199 vs Popularity 0.161 (difference not statistically significant on this single test) |
| Final test, previously seen items allowed | Hybrid Hit@10 = 0.453 vs Popularity 0.236 |
| Rolling backtest, 377 users | Hybrid beats Popularity by +0.043 Hit@10 (95% CI 0.009 to 0.076) |

**Takeaway:** the model is strong at bringing users back to items they already showed interest in, and gives a small but real gain over popularity for discovering new items. Test sets are small, so numbers should be read with their confidence intervals.

## Project Structure
```
ecommerce-recommender/
├── notebooks/recommendation_system.ipynb   # full pipeline
├── artifacts/                              # recommendations_top10_all.csv, cold_start_top10.csv, metrics.json, products.csv
├── frontend/                               # React/Vite dashboard (deployed on Vercel)
├── assets/                                 # screenshots, workflow diagram
├── data/                                   # raw data (not tracked)
├── requirements.txt
└── README.md
```

## How to Run Locally
```bash
git clone https://github.com/YOUR-USERNAME/ecommerce-recommender.git
cd ecommerce-recommender
pip install -r requirements.txt
jupyter notebook notebooks/recommendation_system.ipynb
```
Note: the notebook reads data from `/kaggle/input/...`. Change the `BASE` path in the first cells to your local `data/` folder.

## Tech Stack
Python, pandas, NumPy, SciPy, scikit-learn (TruncatedSVD, KMeans), statsmodels, Matplotlib, Seaborn, React, Vite, Vercel

## Author
Your Name | [LinkedIn](https://linkedin.com/in/YOUR-PROFILE)
