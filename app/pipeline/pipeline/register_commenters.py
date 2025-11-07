# app/pipeline/register_commenters.py
#!/usr/bin/env python3
"""
Step 1: Register commenter channels from video_comments/raw JSONs in GCS.
- Lists comment JSONs under COMMENTS_PREFIX and calls the worker.
- --limit now limits the NUMBER OF JSON FILES processed (not channels).
- Uses a GCS manifest so re-runs skip files already completed.
"""

import logging, os, asyncio, argparse
from dotenv import load_dotenv; load_dotenv()

from app.screenshots.register_commenter_channels import register_commenter_channels
from app.utils.gcs_utils import list_gcs_files

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

BUCKET = os.getenv("GCS_BUCKET_DATA", "yt-bot-data")
COMMENTS_PREFIX = os.getenv("COMMENTS_PREFIX", "youtube-bot-dataset/video_comments/raw/")
MANIFEST_PATH = os.getenv("REGISTER_COMMENTERS_MANIFEST", "manifests/register_commenters/manifest.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of JSON files to process (NOT channel count).")
    parser.add_argument("--force", action="store_true",
                        help="Ignore manifest; reprocess all files.")
    parser.add_argument("--resume", action="store_true",
                        help="Resume using manifest (default if neither given).")
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("REGISTER_COMMENTERS_CONCURRENCY", "8")))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("REGISTER_COMMENTERS_BATCH", "100")))
    parser.add_argument("--queue-size", type=int, default=int(os.getenv("REGISTER_COMMENTERS_QSIZE", "2000")))
    parser.add_argument("--like-threshold", type=int, default=int(os.getenv("REGISTER_COMMENTERS_LIKE_THRESHOLD", "10")))
    args = parser.parse_args()

    gcs_paths = [p for p in list_gcs_files(BUCKET, COMMENTS_PREFIX) if p.endswith(".json")]
    logging.info("📂 Found %d comment JSONs under prefix %s", len(gcs_paths), COMMENTS_PREFIX)

    if not args.force:
        # default to resume behavior if neither flag is set
        args.resume = True

    if gcs_paths:
        asyncio.run(register_commenter_channels(
            bucket=BUCKET,
            gcs_paths=gcs_paths,
            limit_files=args.limit,
            # concurrency=args.concurrency,
            # batch_size=args.batch_size,
            # queue_size=args.queue_size,
            like_threshold=args.like_threshold,
            manifest_path=MANIFEST_PATH,
            force=args.force,
            resume=args.resume,
        ))
