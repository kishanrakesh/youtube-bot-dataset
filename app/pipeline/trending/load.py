#!/usr/bin/env python3
import argparse, logging
from datetime import datetime
from app.utils.gcs_utils import read_json_from_gcs
from app.utils.paths import trending_video_raw_path
from app.env import GCS_BUCKET_DATA

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

def main(region, category, date, max_pages):
    all_videos = []
    for page in range(1, max_pages + 1):
        path = trending_video_raw_path(region, category, page, date)
        page_data = read_json_from_gcs(GCS_BUCKET_DATA, path)
        if not page_data:
            logging.info(f"⚠️ No data found for {category} page {page}")
            continue
        items = page_data.get("items", [])
        logging.info(f"📥 Loaded {len(items)} videos from {path}")
        all_videos.extend(items)
    return all_videos

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="US")
    parser.add_argument("--category", default="general")
    parser.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args()
    main(args.region, args.category, args.date, args.max_pages)
