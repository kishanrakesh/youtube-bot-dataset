#!/usr/bin/env python3
"""
Bot Comment Analysis
====================
Counts top-level comments in GCS video_comments/raw/*.json whose
authorChannelId matches a channel marked is_bot=True in Firestore.

Strategy (fast path):
  1. Pull all is_bot=True channel IDs from Firestore into a frozenset.
  2. List all comment blobs in GCS.
  3. Stream each blob with ijson — only extracts the authorChannelId value,
     never loads the full JSON into memory.
  4. ThreadPoolExecutor (32 workers) parallelises the GCS streaming.

Usage:
    python -m scripts.analysis.bot_comment_analysis
    make bot-comment-analysis
"""

import concurrent.futures
import logging
import sys
import time

import ijson
from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

BUCKET = "yt-bot-data"
COMMENTS_PREFIX = "youtube-bot-dataset/video_comments/raw/"
MAX_WORKERS = 32


def fetch_bot_ids() -> frozenset[str]:
    db = firestore.Client()
    ids = frozenset(
        doc.id for doc in
        db.collection("channel")
          .where(filter=FieldFilter("is_bot", "==", True))
          .stream()
    )
    LOGGER.info(f"Firestore bot channels (is_bot=True): {len(ids):,}")
    return ids


def count_bot_top_level(blob, bot_ids: frozenset) -> int:
    """Stream one GCS blob and count top-level comments by bot authors."""
    count = 0
    try:
        with blob.open("rb") as f:
            for val in ijson.items(
                f,
                "items.item.snippet.topLevelComment.snippet.authorChannelId.value",
            ):
                if val in bot_ids:
                    count += 1
    except Exception as exc:
        LOGGER.warning(f"Skipped {blob.name}: {exc}")
    return count


def main() -> None:
    # 1. Bot IDs
    bot_ids = fetch_bot_ids()
    if not bot_ids:
        LOGGER.error("No bot channels found in Firestore.")
        sys.exit(1)

    # 2. List blobs
    gcs = storage.Client()
    blobs = [
        b for b in gcs.bucket(BUCKET).list_blobs(prefix=COMMENTS_PREFIX)
        if b.name.endswith(".json")
    ]
    LOGGER.info(f"GCS comment files to scan: {len(blobs):,}")

    # 3. Parallel count
    t0 = time.time()
    total = 0
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for n in pool.map(lambda b: count_bot_top_level(b, bot_ids), blobs):
            total += n
            done += 1
            if done % 1000 == 0:
                LOGGER.info(f"  {done}/{len(blobs)} files … bot comments so far: {total:,}")

    elapsed = time.time() - t0

    sep = "=" * 52
    print(f"\n{sep}")
    print(f"  Bot top-level comments in GCS logs : {total:,}")
    print(f"  GCS files scanned                  : {len(blobs):,}")
    print(f"  Firestore bot channels checked      : {len(bot_ids):,}")
    print(f"  Time                               : {elapsed:.1f}s")
    print(sep)


if __name__ == "__main__":
    main()
