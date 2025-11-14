#!/usr/bin/env python3
"""List all channels in Firestore and show their fields."""

from google.cloud import firestore
import json

db = firestore.Client()

print("\n📊 Listing Firestore Channels")
print("="*80)

# Get all channels (or first 100)
channels_ref = db.collection("channels")
docs = channels_ref.limit(10).stream()

count = 0
for doc in docs:
    count += 1
    data = doc.to_dict()
    
    print(f"\nChannel #{count}: {doc.id}")
    print(f"  Title: {data.get('title', 'N/A')}")
    print(f"  Fields: {', '.join(data.keys())}")
    
    # Check for bot-related fields
    if 'is_bot' in data:
        print(f"  is_bot: {data['is_bot']}")
    if 'bot_probability' in data:
        print(f"  bot_probability: {data['bot_probability']}")
    if 'avatar_label' in data:
        print(f"  avatar_label: {data['avatar_label']}")

print(f"\n{'='*80}")
print(f"Total channels shown: {count}")

# Try to count total (this might be slow)
try:
    all_docs = list(channels_ref.limit(1000).stream())
    print(f"Total channels in collection (up to 1000): {len(all_docs)}")
    
    # Count bots
    bots_count = sum(1 for doc in all_docs if doc.to_dict().get('is_bot') == True)
    print(f"Channels with is_bot=True: {bots_count}")
    
    prob_bots = sum(1 for doc in all_docs if doc.to_dict().get('bot_probability', 0) > 0.5)
    print(f"Channels with bot_probability>0.5: {prob_bots}")
    
except Exception as e:
    print(f"Could not count all: {e}")

print("="*80)
