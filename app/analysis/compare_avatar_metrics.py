#!/usr/bin/env python3
"""
Export all bot avatar metrics + summarize ranges.
- Saves CSV of all bot metrics
- Prints min/max/median summary
"""

from google.cloud import firestore
import pandas as pd
from tabulate import tabulate

db = firestore.Client()

OUTPUT_CSV = "bot_metrics.csv"

METRICS = [
    "sat_mean", "white", "skin", "ed", "sat_std",
    "sym", "lines", "var", "dom", "bright", "entropy"
]

def fetch_bot_channels(limit: int = 5000):
    snaps = db.collection("channel").where("is_bot", "==", True).limit(limit).stream()
    records = []
    for snap in snaps:
        doc = snap.to_dict() or {}
        metrics = doc.get("metrics")
        if metrics:
            rec = {"channel_id": snap.id}
            rec.update(metrics)
            records.append(rec)
    return pd.DataFrame(records)

def main():
    df = fetch_bot_channels()
    if df.empty:
        print("❌ No bot channels found in Firestore with metrics")
        return

    # Save all raw data
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Saved raw bot metrics → {OUTPUT_CSV}")

    # Summarize min / max / median
    summary = df[METRICS].agg(["min", "max", "median"]).T
    summary = summary.reset_index().rename(columns={"index": "metric"})
    print("\n=== Bot Metric Ranges ===")
    print(tabulate(summary, headers="keys", tablefmt="github"))

if __name__ == "__main__":
    main()
