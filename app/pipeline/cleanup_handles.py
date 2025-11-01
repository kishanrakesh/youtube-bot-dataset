#!/usr/bin/env python3
"""
Cleanup migrated handle-based channel docs:
- For each non-UC channel doc in channel_pending
- Look up the 'snippet.customUrl' match in the main 'channel' collection
- If the UC twin exists, delete the handle doc
"""

import logging
from google.cloud import firestore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
db = firestore.Client()

def cleanup_handles():
    pending_ref = db.collection("channel_pending")
    channel_ref = db.collection("channel")

    docs = pending_ref.stream()
    total_checked, total_deleted, total_skipped = 0, 0, 0

    for doc in docs:
        doc_id = doc.id
        total_checked += 1

        if doc_id.startswith("UC"):
            continue  # already a UC channelId, not a handle

        # normalize handle (Firestore stores with "@")
        handle = f"@{doc_id.lower()}"

        twin_q = channel_ref.where(
            "channel_data.snippet.customUrl", "==", handle
        ).limit(1).stream()
        twin_docs = list(twin_q)

        if twin_docs:
            uc_id = twin_docs[0].id
            logging.info(f"🗑️ Deleting handle {doc_id} → UC twin {uc_id} found")
            doc.reference.delete()
            total_deleted += 1
        else:
            logging.info(f"⚠️ No UC twin for handle {doc_id}, keeping")
            total_skipped += 1

    logging.info(
        f"✅ Cleanup done: {total_checked} checked, "
        f"{total_deleted} deleted, {total_skipped} skipped"
    )

if __name__ == "__main__":
    cleanup_handles()
