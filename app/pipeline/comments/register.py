#!/usr/bin/env python3
"""
Register commenter channels from video_comments/raw JSONs in GCS.

This script:
- Lists comment JSONs under COMMENTS_PREFIX
- Processes each JSON to extract commenter channel information
- Registers channels to Firestore
- Uses a GCS manifest to track progress and enable resume
"""

import argparse
import asyncio
import logging
import os
from dotenv import load_dotenv

from app.pipeline.comments.register_channels import register_commenter_channels
from app.utils.gcs_utils import list_gcs_files

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

# Configuration from environment
BUCKET = os.getenv("GCS_BUCKET_DATA", "yt-bot-data")
COMMENTS_PREFIX = os.getenv("COMMENTS_PREFIX", "youtube-bot-dataset/video_comments/raw/")
MANIFEST_PATH = os.getenv("REGISTER_COMMENTERS_MANIFEST", "manifests/register_commenters/manifest.json")


def main(
    limit: int | None,
    force: bool,
    resume: bool,
    concurrency: int,
    batch_size: int,
    queue_size: int,
    like_threshold: int
) -> None:
    """Register commenter channels from comment JSONs in GCS."""
    gcs_paths = [p for p in list_gcs_files(BUCKET, COMMENTS_PREFIX) if p.endswith(".json")]
    LOGGER.info(f"📂 Found {len(gcs_paths)} comment JSONs under prefix {COMMENTS_PREFIX}")

    if not gcs_paths:
        LOGGER.warning("No JSON files found to process")
        return

    # Default to resume behavior if neither force nor resume is explicitly set
    if not force:
        resume = True

    asyncio.run(register_commenter_channels(
        bucket=BUCKET,
        gcs_paths=gcs_paths,
        limit_files=limit,
        like_threshold=like_threshold,
        manifest_path=MANIFEST_PATH,
        force=force,
        resume=resume,
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Register commenter channels from GCS comment data"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of JSON files to process (not channel count)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore manifest and reprocess all files"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume using manifest (default if neither force/resume given)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("REGISTER_COMMENTERS_CONCURRENCY", "8")),
        help="Number of concurrent channel scrapes"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("REGISTER_COMMENTERS_BATCH", "100")),
        help="Firestore batch write size"
    )
    parser.add_argument(
        "--queue-size",
        type=int,
        default=int(os.getenv("REGISTER_COMMENTERS_QSIZE", "2000")),
        help="Processing queue size"
    )
    parser.add_argument(
        "--like-threshold",
        type=int,
        default=int(os.getenv("REGISTER_COMMENTERS_LIKE_THRESHOLD", "10")),
        help="Minimum likes for comment to be processed"
    )
    
    args = parser.parse_args()
    main(
        limit=args.limit,
        force=args.force,
        resume=args.resume,
        concurrency=args.concurrency,
        batch_size=args.batch_size,
        queue_size=args.queue_size,
        like_threshold=args.like_threshold
    )
