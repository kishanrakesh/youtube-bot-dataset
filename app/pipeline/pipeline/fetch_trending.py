#!/usr/bin/env python3
import argparse, logging
from datetime import datetime
from app.youtube_api.fetch_trending_videos_general import fetch_trending_videos_general
from app.youtube_api.fetch_trending_videos_by_category import fetch_trending_videos_by_category

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

def main(region, category, date, max_pages):
    if category == "general":
        fetch_trending_videos_general(region, date=date, dry_run=False, max_api_calls=max_pages)
    else:
        fetch_trending_videos_by_category(region, category, dry_run=False, max_api_calls=max_pages)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="US")
    parser.add_argument("--category", default="general")
    parser.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args()
    main(args.region, args.category, args.date, args.max_pages)
