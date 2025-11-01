#!/usr/bin/env python3
"""
Backfill bot probabilities for existing channels that have metrics
but no probability score.
"""

import joblib
import numpy as np
from google.cloud import firestore
from app.utils.logging import get_logger

logger = get_logger()
db = firestore.Client()

METRICS = [
    "sat_mean","white","skin","ed","sat_std",
    "sym","lines","var","dom","bright","entropy"
]

def backfill(model_path="xgb_bot_model.pkl", limit=10000):
    model = joblib.load(model_path)
    snaps = db.collection("channel").limit(limit).stream()
    batch = db.batch()
    updated = 0

    for snap in snaps:
        doc = snap.to_dict() or {}
        metrics = doc.get("avatar_metrics", {})
        if not metrics or metrics.get("has_bot_probability"):
            continue

        try:
            X = np.array([[metrics[m] for m in METRICS]])
            prob = float(model.predict_proba(X)[:,1][0])
            metrics["bot_probability"] = prob
            metrics["has_bot_probability"] = True

            batch.update(snap.reference, {"avatar_metrics": metrics})
            updated += 1

            if updated % 100 == 0:
                batch.commit()
                batch = db.batch()
                logger.info(f"✅ Backfilled {updated} so far...")
        except Exception as e:
            logger.warning(f"⚠️ Failed {snap.id}: {e}")

    if updated:
        batch.commit()
    logger.info(f"🎉 Backfill complete: {updated} docs updated")

if __name__ == "__main__":
    backfill()
