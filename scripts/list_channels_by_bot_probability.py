#!/usr/bin/env python3
"""List channels sorted by bot probability (highest first)."""

import argparse
from google.cloud import firestore

def list_channels_by_probability(limit=100, min_probability=0.0):
    """Query Firestore and display channels sorted by bot probability.
    
    Args:
        limit: Maximum number of channels to fetch
        min_probability: Minimum bot probability to include
    """
    db = firestore.Client()
    
    # Fetch channels
    print(f"📥 Fetching up to {limit} channels...")
    query = db.collection("channel").limit(limit * 2)  # Fetch more for sorting
    docs = list(query.stream())
    
    # Extract channels with bot probability
    channels = []
    for doc in docs:
        data = doc.to_dict() or {}
        metrics = data.get("avatar_metrics", {})
        bot_prob = metrics.get("bot_probability", 0.0)
        
        if bot_prob >= min_probability:
            channels.append({
                "channel_id": doc.id,
                "bot_probability": bot_prob,
                "avatar_label": data.get("avatar_label", "UNKNOWN"),
                "is_bot_checked": data.get("is_bot_checked", False),
                "is_screenshot_stored": data.get("is_screenshot_stored", False),
                "about_links_count": data.get("about_links_count", 0),
                "featured_channels_count": data.get("featured_channels_count", 0),
            })
    
    # Sort by bot probability (descending)
    channels.sort(key=lambda x: x["bot_probability"], reverse=True)
    channels = channels[:limit]
    
    # Display results
    print(f"\n🤖 Top {len(channels)} Channels by Bot Probability")
    print("=" * 120)
    print(f"{'Rank':<6} {'Channel ID':<26} {'Bot Prob':<12} {'Label':<12} {'Checked':<10} {'Screenshot':<12} {'Links':<8} {'Featured'}")
    print("=" * 120)
    
    for i, ch in enumerate(channels, 1):
        print(f"{i:<6} {ch['channel_id']:<26} {ch['bot_probability']:<12.4f} {ch['avatar_label']:<12} "
              f"{'✓' if ch['is_bot_checked'] else '✗':<10} {'✓' if ch['is_screenshot_stored'] else '✗':<12} "
              f"{ch['about_links_count']:<8} {ch['featured_channels_count']}")
    
    print("=" * 120)
    print(f"\n✅ Found {len(channels)} channels")
    
    # Statistics
    if channels:
        avg_prob = sum(ch['bot_probability'] for ch in channels) / len(channels)
        max_prob = channels[0]['bot_probability']
        min_prob = channels[-1]['bot_probability']
        print(f"\n📊 Statistics:")
        print(f"   Max probability: {max_prob:.4f}")
        print(f"   Min probability: {min_prob:.4f}")
        print(f"   Average probability: {avg_prob:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List channels sorted by bot probability")
    parser.add_argument("--limit", type=int, default=100, help="Number of channels to display")
    parser.add_argument("--min-probability", type=float, default=0.0, help="Minimum bot probability")
    
    args = parser.parse_args()
    list_channels_by_probability(args.limit, args.min_probability)
