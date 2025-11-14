#!/usr/bin/env python3
"""Quick script to check what fields exist in Firestore channels."""

from google.cloud import firestore

db = firestore.Client()

# Get first 5 channel documents to inspect
channels = db.collection("channels").limit(5).stream()

print("\n📊 Firestore Channel Schema Check")
print("="*80)

for i, doc in enumerate(channels, 1):
    data = doc.to_dict()
    print(f"\nChannel {i}: {doc.id}")
    print(f"Fields: {list(data.keys())}")
    
    # Show relevant bot-related fields
    bot_fields = {k: v for k, v in data.items() if 'bot' in k.lower() or 'label' in k.lower()}
    if bot_fields:
        print(f"Bot-related fields: {bot_fields}")

print("\n" + "="*80)
