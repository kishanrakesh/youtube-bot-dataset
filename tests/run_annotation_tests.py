#!/usr/bin/env python3
"""
Smoke test for the annotation pipeline:

1. Register commenter channels from all video_comments/raw JSONs in GCS.
2. Capture homepage screenshots for those channels (Playwright → GCS).
3. Launch manual review UI (OpenCV) to label a few.
"""

import logging, os, asyncio
from dotenv import load_dotenv; load_dotenv()

from app.screenshots.register_commenter_channels import register_commenter_channels
from app.pipeline.screenshots.capture import fetch_channels_needing_screenshots, save_screenshots
from app.labelling.review_channel_screenshots import fetch_docs, review_docs
from app.utils.gcs_utils import list_gcs_files   # helper to list objects in GCS

# ───── config ─────
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

TEST_BUCKET = os.getenv("GCS_BUCKET_DATA", "yt-bot-data")
COMMENTS_PREFIX = "youtube-bot-dataset/video_comments/raw/"   # prefix where comment JSONs are stored

if __name__ == "__main__":
    # Step 1: Find all comment JSONs and register channels
    # logging.info("📝 Looking up all comment JSONs in %s", COMMENTS_PREFIX)
    # gcs_paths = [p for p in list_gcs_files(TEST_BUCKET, COMMENTS_PREFIX) if p.endswith(".json")]
    # logging.info("📂 Found %d comment JSONs", len(gcs_paths))

    # if gcs_paths:
    #     register_commenter_channels(TEST_BUCKET, gcs_paths)

    # # Step 2: Capture screenshots (async)
    # logging.info("📸 Capturing screenshots...")
    # docs = fetch_channels_needing_screenshots(limit=500)   # adjust limit for testing
    # asyncio.run(save_screenshots(docs, parallel_tabs=10))

    # Step 3: Manual review (sync)
    # logging.info("👀 Launching manual review UI...")
    review_docs(fetch_docs(limit=300))
