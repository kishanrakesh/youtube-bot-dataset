#!/usr/bin/env python3
"""Fetch YouTube comments for trending videos."""

import argparse
import logging
from datetime import datetime, UTC

from app.youtube_api.fetch_comment_threads_by_video_id import fetch_comment_threads_by_video_id
from app.pipeline.trending.load import main as load_trending

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def main(region: str, category: str, date: str, max_pages: int, max_comment_pages: int) -> None:
    """Fetch comments for all videos from trending."""
    videos = load_trending(region, category, date, max_pages)
    
    for idx, item in enumerate(videos, start=1):
        vid = item.get("id")
        if not vid:
            continue
            
        LOGGER.info(f"🗨️ Fetching comments for video {idx}/{len(videos)}: {vid}")
        fetch_comment_threads_by_video_id(vid, dry_run=False, max_api_calls=max_comment_pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch comments for trending videos")
    parser.add_argument("--region", default="US", help="Region code (e.g., US, GB)")
    parser.add_argument("--category", default="general", help="Category ID or 'general'")
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"),
                        help="Date for the videos (YYYY-MM-DD)")
    parser.add_argument("--max-pages", type=int, default=2,
                        help="Maximum number of trending pages to process")
    parser.add_argument("--max-comment-pages", type=int, default=2,
                        help="Maximum number of comment pages per video")
    
    args = parser.parse_args()
    main(args.region, args.category, args.date, args.max_pages, args.max_comment_pages)
