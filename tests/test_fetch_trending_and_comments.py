#test_fetch_trending_and_comments

#!/usr/bin/env python3
"""
Test script:
1. Fetch trending videos (general OR category, based on config).
2. Store each page JSON in GCS.
3. For each video ID, fetch comment threads and store in GCS.
"""

import logging
from datetime import datetime
from dotenv import load_dotenv; load_dotenv()

from app.youtube_api.fetch_trending_videos_general import fetch_trending_videos_general
from app.youtube_api.fetch_trending_videos_by_category import fetch_trending_videos_by_category
from app.youtube_api.fetch_comment_threads_by_video_id import fetch_comment_threads_by_video_id
from app.utils.gcs_utils import read_json_from_gcs
from app.utils.paths import trending_video_raw_path
from app.env import GCS_BUCKET_DATA

# ───── logging setup ─────
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ───── config ─────
REGION = "US"
DATE = datetime.utcnow().strftime("%Y-%m-%d")
TRENDING_TYPE = "17"   # set to "general" or category ID string like "17"
MAX_PAGES = 2               # pages of trending to fetch
MAX_COMMENT_PAGES = 2       # comment pages per video


def fetch_trending(trending_type: str, region: str, date: str, max_pages: int):
    """Fetch trending videos (general or category)."""
    if trending_type == "general":
        fetch_trending_videos_general(region, date=date, dry_run=False, max_api_calls=max_pages)
    else:
        fetch_trending_videos_by_category(region, trending_type, dry_run=False, max_api_calls=max_pages)


def load_trending(trending_type: str, region: str, date: str, max_pages: int):
    """Load trending results from GCS and return combined video list."""
    all_videos = []
    for page in range(1, max_pages + 1):
        trending_path = trending_video_raw_path(region, trending_type, page, date)
        page_data = read_json_from_gcs(GCS_BUCKET_DATA, trending_path)
        if not page_data:
            logging.info(f"⚠️ No data found for {trending_type} page {page}")
            continue

        items = page_data.get("items", [])
        logging.info(f"📥 Loaded {len(items)} videos from {trending_path}")
        all_videos.extend(items)

    return all_videos


if __name__ == "__main__":
    # Step 1: Fetch trending
    logging.info(f"🌎 Fetching {MAX_PAGES} page(s) of trending ({TRENDING_TYPE})...")
    fetch_trending(TRENDING_TYPE, REGION, DATE, MAX_PAGES)

    # Step 2: Load trending videos
    all_videos = load_trending(TRENDING_TYPE, REGION, DATE, MAX_PAGES)

    # Step 3: Fetch comment threads for each video
    for idx, item in enumerate(all_videos):
        vid = item.get("id")
        if not vid:
            continue
        logging.info(f"🗨️ Fetching comments for video {idx+1}/{len(all_videos)}: {vid}")
        fetch_comment_threads_by_video_id(vid, dry_run=False, max_api_calls=MAX_COMMENT_PAGES)
