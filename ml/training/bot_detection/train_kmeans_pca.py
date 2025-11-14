# train_kmeans_pca.py
import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import joblib

# Load your labeled metrics CSV
df = pd.read_csv("bot_metrics.csv")

# Features
FEATURES = [
    "sat_mean","white","skin","ed","sat_std",
    "sym","lines","var","dom","bright","entropy"
]
X = df[FEATURES].values

# --- PCA ---
pca = PCA(n_components=5, random_state=42)  # keep top 5 PCs
X_pca = pca.fit_transform(X)

# --- KMeans ---
kmeans = KMeans(n_clusters=30, random_state=42, n_init=10)
df["cluster"] = kmeans.fit_predict(X_pca)

# Compute bot % per cluster
print(df)
cluster_bot_prob = df.groupby("cluster")["label"].mean().to_dict()

# Save bundle
joblib.dump({
    "pca": pca,
    "kmeans": kmeans,
    "features": FEATURES,
    "cluster_bot_prob": cluster_bot_prob
}, "kmeans_pca_bot_model.pkl")

print("✅ Saved PCA+KMeans model to kmeans_pca_bot_model.pkl")
