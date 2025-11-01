#!/usr/bin/env python3
"""
Backfill avatar metrics for channel docs in Firestore.
Only updates docs missing `avatar_metrics`.
"""

import logging
from google.cloud import firestore
from app.utils.image_processing import classify_avatar_url
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger("backfill_metrics")

COLLECTION_NAME = "channel"
BATCH_SIZE = 300  # Firestore batch limit

def batched_query(collection, batch_size=500):
    db = firestore.Client()
    docs = db.collection(collection).order_by("registered_at").limit(batch_size)
    last_doc = None

    while True:
        if last_doc:
            docs = db.collection(collection).order_by("registered_at").start_after(last_doc).limit(batch_size)

        results = list(docs.stream())
        if not results:
            break

        yield results   # return a batch (list of docs)
        last_doc = results[-1]


def backfill_channel_metrics():
    db = firestore.Client()

    # Count docs in collection (requires Firestore >= v2.11)
    try:
        total_docs = db.collection(COLLECTION_NAME).count().get()[0][0].value
    except Exception:
        total_docs = None
        LOGGER.info("ℹ️ Could not get exact doc count (older Firestore version).")

    docs = db.collection(COLLECTION_NAME).stream()

    total = 0
    updated = 0

    batch = db.batch()

    with tqdm(total=total_docs, unit="doc") as pbar:
        for batch_docs in batched_query("channel", batch_size=500):
            for doc in batch_docs:   # <-- now doc is a DocumentSnapshot
                total += 1
                data = doc.to_dict()

                if "avatar_metrics" in data and data["avatar_metrics"]:
                    pbar.update(1)
                    continue

                avatar_url = data.get("avatar_url")
                is_bot = data.get("is_bot")
                if not avatar_url or not is_bot:
                    pbar.update(1)
                    continue

                try:
                    _, metrics = classify_avatar_url(avatar_url, size=128)
                    batch.update(doc.reference, {"avatar_metrics": metrics})
                    updated += 1
                except Exception as e:
                    LOGGER.warning(f"⚠️ Failed {doc.id}: {e}")

                if updated % BATCH_SIZE == 0 and updated > 0:
                    batch.commit()
                    LOGGER.info(f"✅ Committed {updated} updates so far...")
                    batch = db.batch()

                pbar.update(1)


    # Final commit
    if updated % BATCH_SIZE:
        batch.commit()

    LOGGER.info(f"🎉 Finished {total} docs scanned, {updated} updated with metrics.")


if __name__ == "__main__":
    backfill_channel_metrics()
