#!/usr/bin/env python3
"""Fetch trending videos from YouTube and store to GCS."""

import argparse
import logging
from datetime import datetime, UTC

from app.youtube_api.fetch_trending_videos_general import fetch_trending_videos_general
from app.youtube_api.fetch_trending_videos_by_category import fetch_trending_videos_by_category

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def main(region: str, category: str, date: str, max_pages: int) -> None:
    """Fetch trending videos for specified region and category."""
    LOGGER.info(f"🌎 Fetching trending videos for {region}, category {category}")
    
    if category == "general":
        fetch_trending_videos_general(region, date=date, dry_run=False, max_api_calls=max_pages)
    else:
        fetch_trending_videos_by_category(region, category, dry_run=False, max_api_calls=max_pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch trending videos from YouTube")
    parser.add_argument("--region", default="US", help="Region code (e.g., US, GB)")
    parser.add_argument("--category", default="general", help="Category ID or 'general'")
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"),
                        help="Date for the fetch (YYYY-MM-DD)")
    parser.add_argument("--max-pages", type=int, default=2,
                        help="Maximum number of pages to fetch")
    
    args = parser.parse_args()
    main(args.region, args.category, args.date, args.max_pages)
