#!/usr/bin/env python3
"""
Summarize min/max/median for bot channels across avatar metrics,
and dump all raw metric data to CSV for manual inspection.
"""

from google.cloud import firestore
import pandas as pd
from tabulate import tabulate

db = firestore.Client()

METRICS = [
    "sat_mean", "white", "skin", "ed", "sat_std",
    "sym", "lines", "var", "dom", "bright", "entropy"
]

OUTPUT_CSV = "bot_metrics.csv"

def fetch_bot_channels(limit: int = 5000):
    snaps = db.collection("channel").where("is_bot", "==", True).limit(limit).stream()
    records = []
    for snap in snaps:
        doc = snap.to_dict() or {}
        metrics = doc.get("metrics")
        if metrics:
            records.append({"channel_id": snap.id, **metrics})
    return pd.DataFrame(records)

def main():
    df = fetch_bot_channels()
    if df.empty:
        print("❌ No bot channels found in Firestore with metrics")
        return

    # Summary stats
    summary = df[METRICS].agg(["min", "max", "median"]).T
    summary = summary.reset_index().rename(columns={"index": "metric"})
    print("=== Bot Metric Ranges ===")
    print(tabulate(summary, headers="keys", tablefmt="github"))

    # Find channels at extremes
    print("\n=== Channels at extremes ===")
    for m in METRICS:
        min_idx = df[m].idxmin()
        max_idx = df[m].idxmax()
        print(f"{m:<10} min={df.loc[min_idx, m]} ({df.loc[min_idx, 'channel_id']}) "
              f" | max={df.loc[max_idx, m]} ({df.loc[max_idx, 'channel_id']})")

    # Save full dataset
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Saved all bot metrics to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
