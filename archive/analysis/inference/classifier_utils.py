# classifier_utils.py
import joblib, numpy as np

_PCA_KMEANS_MODEL = None
def get_pca_kmeans_model(path="kmeans_pca_bot_model.pkl"):
    global _PCA_KMEANS_MODEL
    if _PCA_KMEANS_MODEL is None:
        try:
            _PCA_KMEANS_MODEL = joblib.load(path)
        except FileNotFoundError:
            print(f"⚠️ No PCA+KMeans model found at {path}")
            _PCA_KMEANS_MODEL = None
    return _PCA_KMEANS_MODEL

def score_with_pca_kmeans(metrics: dict) -> dict:
    model_bundle = get_pca_kmeans_model()
    if model_bundle is None:
        metrics["bot_probability"] = 0.0
        metrics["has_bot_probability"] = False
        return metrics

    pca = model_bundle["pca"]
    kmeans = model_bundle["kmeans"]
    features = model_bundle["features"]
    cluster_bot_prob = model_bundle["cluster_bot_prob"]

    # Extract metrics → PCA → KMeans
    X = np.array([[metrics[f] for f in features]])
    X_pca = pca.transform(X)
    cluster = int(kmeans.predict(X_pca)[0])
    prob = float(cluster_bot_prob.get(cluster, 0.0))

    metrics["bot_probability"] = prob
    metrics["cluster"] = cluster
    metrics["has_bot_probability"] = True
    return metrics
