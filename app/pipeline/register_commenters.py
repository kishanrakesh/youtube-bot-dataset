#!/usr/bin/env python3
"""
Step 1: Register commenter channels from all video_comments/raw JSONs in GCS.
"""

import logging, os, asyncio, argparse
from dotenv import load_dotenv; load_dotenv()

from app.screenshots.register_commenter_channels import register_commenter_channels
from app.utils.gcs_utils import list_gcs_files

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

TEST_BUCKET = os.getenv("GCS_BUCKET_DATA", "yt-bot-data")
COMMENTS_PREFIX = "youtube-bot-dataset/video_comments/raw/"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max number of commenter channels to register")
    args = parser.parse_args()

    gcs_paths = [p for p in list_gcs_files(TEST_BUCKET, COMMENTS_PREFIX) if p.endswith(".json")]
    logging.info("📂 Found %d comment JSONs", len(gcs_paths))

    if gcs_paths:
        asyncio.run(register_commenter_channels(TEST_BUCKET, gcs_paths, limit=args.limit))
