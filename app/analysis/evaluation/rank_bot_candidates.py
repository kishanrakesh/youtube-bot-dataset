#!/usr/bin/env python3
"""
Bot Metrics Threshold + Ranking Analysis

1. Loads bot/non-bot channels with metrics from Firestore
2. Computes min/max for each metric in both groups
3. Suggests thresholds using a padding factor
4. Produces ranked CSV for annotation (bot-likeness score)

"""

import pandas as pd
import numpy as np
from google.cloud import firestore
from sklearn.preprocessing import MinMaxScaler

from app.utils.logging import get_logger

logger = get_logger()
db = firestore.Client()

# ---------------- Config ----------------
OUTPUT_THRESHOLDS = "metric_thresholds.csv"
OUTPUT_RANKED = "ranked_channels.csv"
METRICS = [
    "sat_mean", "white", "skin", "ed", "sat_std",
    "sym", "lines", "var", "dom", "bright", "entropy"
]

# Metrics where bots are usually *lower* → flip for ranking
FLIP = {"entropy", "sym", "sat_mean", "sat_std", "bright"}

# Padding for thresholding (10% buffer)
PADDING = 0.1
# ----------------------------------------

def fetch_all_channels(limit: int = 5000):
    snaps = db.collection("channel").limit(limit).stream()
    records = []
    for snap in snaps:
        doc = snap.to_dict() or {}
        metrics = doc.get("metrics")
        if not metrics:
            continue
        rec = {"channel_id": snap.id, **metrics}
        rec["is_bot"] = doc.get("is_bot")
        records.append(rec)
    return pd.DataFrame(records)


def normalize_for_ranking(df: pd.DataFrame):
    df_norm = df.copy()
    scaler = MinMaxScaler()
    df_norm[METRICS] = scaler.fit_transform(df_norm[METRICS])

    # Flip bot-lower features
    for m in FLIP:
        if m in df_norm:
            df_norm[m] = 1 - df_norm[m]

    df_norm["bot_likeness"] = df_norm[METRICS].mean(axis=1)
    return df_norm


def compute_thresholds(df: pd.DataFrame):
    results = []
    if "is_bot" not in df:
        return pd.DataFrame()

    df_bots = df[df["is_bot"] == True]
    df_non = df[df["is_bot"] == False]

    for m in METRICS:
        if m not in df:
            continue

        bot_min, bot_max = df_bots[m].min(), df_bots[m].max()
        non_min, non_max = df_non[m].min(), df_non[m].max()

        # Suggest thresholds with padding
        if bot_max < non_min:
            # Bots are strictly lower
            thr = bot_max * (1 + PADDING)
            rule = f"{m} <= {thr:.3f}"
        elif bot_min > non_max:
            # Bots are strictly higher
            thr = bot_min * (1 - PADDING)
            rule = f"{m} >= {thr:.3f}"
        else:
            thr = None
            rule = "⚠️ Overlap (no safe rule)"

        results.append({
            "metric": m,
            "bot_min": bot_min,
            "bot_max": bot_max,
            "non_min": non_min,
            "non_max": non_max,
            "suggested_rule": rule
        })

    return pd.DataFrame(results)


def main():
    df = fetch_all_channels()
    if df.empty:
        logger.error("❌ No channels with metrics found in Firestore")
        return

    logger.info(f"📥 Loaded {len(df)} channels with metrics (bots={df['is_bot'].sum()}, non-bots={(df['is_bot']==False).sum()})")

    # --- Threshold analysis ---
    thresholds = compute_thresholds(df)
    thresholds.to_csv(OUTPUT_THRESHOLDS, index=False)
    logger.info(f"✅ Saved metric thresholds → {OUTPUT_THRESHOLDS}")

    # --- Ranking for annotation ---
    df_ranked = normalize_for_ranking(df)
    df_ranked = df_ranked.sort_values("bot_likeness", ascending=False)
    df_ranked.to_csv(OUTPUT_RANKED, index=False)
    logger.info(f"✅ Saved ranked channels → {OUTPUT_RANKED}")


if __name__ == "__main__":
    main()
