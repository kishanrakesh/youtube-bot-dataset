#!/usr/bin/env python3
"""Load trending video data from GCS."""

import argparse
import logging
from datetime import datetime, UTC
from typing import List, Dict, Any

from app.utils.gcs_utils import read_json_from_gcs
from app.utils.paths import trending_video_raw_path
from app.env import GCS_BUCKET_DATA

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def main(region: str, category: str, date: str, max_pages: int) -> List[Dict[str, Any]]:
    """Load trending videos from GCS and return them."""
    all_videos = []
    
    for page in range(1, max_pages + 1):
        path = trending_video_raw_path(region, category, page, date)
        page_data = read_json_from_gcs(GCS_BUCKET_DATA, path)
        
        if not page_data:
            LOGGER.info(f"⚠️ No data found for {category} page {page}")
            continue
            
        items = page_data.get("items", [])
        LOGGER.info(f"📥 Loaded {len(items)} videos from {path}")
        all_videos.extend(items)
    
    return all_videos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load trending videos from GCS")
    parser.add_argument("--region", default="US", help="Region code (e.g., US, GB)")
    parser.add_argument("--category", default="general", help="Category ID or 'general'")
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"),
                        help="Date for the data (YYYY-MM-DD)")
    parser.add_argument("--max-pages", type=int, default=2,
                        help="Maximum number of pages to load")
    
    args = parser.parse_args()
    videos = main(args.region, args.category, args.date, args.max_pages)
    LOGGER.info(f"✅ Loaded {len(videos)} total videos")
