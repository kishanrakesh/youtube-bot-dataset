#!/usr/bin/env python3
"""
Score all channels in Firestore using trained XGB model
and save ordered results to CSV.
"""

import os
import joblib
import pandas as pd
import numpy as np
from google.cloud import firestore
from app.utils.logging import get_logger

logger = get_logger()
db = firestore.Client()

MODEL_PATH = "xgb_bot_model.pkl"
OUTPUT_CSV = "channels_ranked.csv"
COLLECTION_NAME = "channel"

METRICS = [
    "sat_mean", "white", "skin", "ed", "sat_std",
    "sym", "lines", "var", "dom", "bright", "entropy"
]


def fetch_all_channels(limit: int = 20000) -> pd.DataFrame:
    snaps = db.collection(COLLECTION_NAME).limit(limit).stream()
    records = []
    for snap in snaps:
        doc = snap.to_dict() or {}
        metrics = doc.get("avatar_metrics") or doc.get("metrics")
        if not metrics:
            continue
        rec = {"channel_id": snap.id, **metrics}
        # Keep label if already annotated
        rec["is_bot"] = doc.get("is_bot")
        records.append(rec)
    return pd.DataFrame(records)


def load_model(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ Model not found at {path}")
    logger.info(f"📥 Loading model from {path}")
    return joblib.load(path)


def score_channels(df: pd.DataFrame, model) -> pd.DataFrame:
    X = df[METRICS].values
    probs = model.predict_proba(X)[:, 1]
    df["bot_probability"] = probs
    return df.sort_values("bot_probability", ascending=False)


def main():
    # 1. Load data
    df = fetch_all_channels()
    if df.empty:
        logger.error("❌ No channels with avatar_metrics found in Firestore")
        return
    logger.info(f"📊 Loaded {len(df)} channels (labeled={df['is_bot'].notna().sum()})")

    # 2. Load trained model
    model = load_model(MODEL_PATH)

    # 3. Score + rank
    df_scored = score_channels(df, model)

    # 4. Save
    df_scored.to_csv(OUTPUT_CSV, index=False)
    logger.info(f"✅ Ranked results saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
