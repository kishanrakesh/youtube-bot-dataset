#!/usr/bin/env python3
"""
Train XGB on labeled channels (bots vs non-bots),
and save model for scoring new channels.
"""

import joblib
import pandas as pd
from google.cloud import firestore
from xgboost import XGBClassifier

from app.utils.logging import get_logger

logger = get_logger()
db = firestore.Client()

METRICS = [
    "sat_mean","white","skin","ed","sat_std",
    "sym","lines","var","dom","bright","entropy"
]

def fetch_labeled_channels(limit=20000):
    snaps = db.collection("channel").limit(limit).stream()
    records = []
    for snap in snaps:
        doc = snap.to_dict() or {}
        metrics = doc.get("avatar_metrics", {})
        if not metrics or doc.get("is_bot") is None:
            continue
        rec = {"channel_id": snap.id, **metrics, "is_bot": doc["is_bot"]}
        records.append(rec)
    return pd.DataFrame(records)

def train_xgb(df: pd.DataFrame):
    X = df[METRICS].values
    y = df["is_bot"].astype(int).values
    model = XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, eval_metric="logloss", random_state=42
    )
    model.fit(X, y)
    return model

def main():
    df = fetch_labeled_channels()
    if df.empty:
        logger.error("❌ No labeled channels found")
        return

    model = train_xgb(df)
    joblib.dump(model, "xgb_bot_model.pkl")
    logger.info("✅ Saved model → xgb_bot_model.pkl")

if __name__ == "__main__":
    main()
