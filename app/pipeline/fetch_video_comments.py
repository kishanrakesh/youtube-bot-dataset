#!/usr/bin/env python3
import argparse, logging
from app.youtube_api.fetch_comment_threads_by_video_id import fetch_comment_threads_by_video_id
from app.pipeline.load_trending import main as load_trending
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

def main(region, category, date, max_pages, max_comment_pages):
    videos = load_trending(region, category, date, max_pages)
    for idx, item in enumerate(videos, start=1):
        vid = item.get("id")
        if not vid: continue
        logging.info(f"🗨️ Fetching comments for video {idx}/{len(videos)}: {vid}")
        fetch_comment_threads_by_video_id(vid, dry_run=False, max_api_calls=max_comment_pages)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="US")
    parser.add_argument("--category", default="general")
    parser.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-comment-pages", type=int, default=2)
    args = parser.parse_args()
    main(args.region, args.category, args.date, args.max_pages, args.max_comment_pages)
