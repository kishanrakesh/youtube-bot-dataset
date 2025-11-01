# visualize_clusters.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import joblib

# Load your metrics + labels
df = pd.read_csv("bot_metrics.csv")

FEATURES = [
    "sat_mean","white","skin","ed","sat_std",
    "sym","lines","var","dom","bright","entropy"
]

X = df[FEATURES].values
labels = df["label"].values  # 1 = bot, 0 = non-bot

# Load model
bundle = joblib.load("kmeans_pca_bot_model.pkl")
pca = bundle["pca"]
kmeans = bundle["kmeans"]
cluster_probs = bundle["cluster_bot_prob"]

# Project to PCA space
X_pca = pca.transform(X)
clusters = kmeans.predict(X_pca)

df["cluster"] = clusters
df["bot_prob_cluster"] = df["cluster"].map(cluster_probs)

# --- Plot first 2 PCA components ---
plt.figure(figsize=(10,7))

# Non-bots first
mask_nonbot = labels == 0
plt.scatter(
    X_pca[mask_nonbot, 0], X_pca[mask_nonbot, 1],
    c=[cluster_probs[c] for c in clusters[mask_nonbot]],
    cmap="coolwarm", alpha=0.4, edgecolor="k", marker="x", label="Non-bot"
)

# Bots on top
mask_bot = labels == 1
plt.scatter(
    X_pca[mask_bot, 0], X_pca[mask_bot, 1],
    c=[cluster_probs[c] for c in clusters[mask_bot]],
    cmap="coolwarm", alpha=0.9, edgecolor="k", marker="o", s=80, label="Bot"
)

# Cluster centroids
centroids_pca = kmeans.cluster_centers_
plt.scatter(
    centroids_pca[:,0], centroids_pca[:,1],
    c="black", marker="*", s=200, label="Cluster centroid"
)

plt.colorbar(label="Cluster bot probability")
plt.xlabel("PCA Component 1")
plt.ylabel("PCA Component 2")
plt.title("PCA + KMeans clustering (bots prioritized, centroids shown)")
plt.legend()
plt.grid(True)
plt.show()

# --- Cluster scores ---
cluster_scores = df.groupby("cluster")["label"].mean().sort_values(ascending=False)
print("\n=== Bot fraction per cluster (score) ===")
print(cluster_scores)
