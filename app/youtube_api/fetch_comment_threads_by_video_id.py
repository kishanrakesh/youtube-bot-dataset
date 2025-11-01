#fetch_comment_threads_by_video_id

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from typing import List, Dict, Optional
from datetime import datetime
from app.utils.clients import get_youtube
from app.utils.gcs_utils import write_json_to_gcs, file_exists_in_gcs
from app.utils.paths import (
    video_comments_path,
    video_comments_seen_path
)
from app.utils.logging import get_logger
import os
import json
from app.env import GCS_BUCKET_DATA

logger = get_logger()

LIKE_THRESHOLD = 10
MAX_CONSECUTIVE_LOW_LIKE_PAGES = 2


def fetch_comment_threads_by_video_id(
    video_id: str,
    dry_run: bool = False,
    max_api_calls: Optional[int] = None
) -> Optional[str]:
    """
    Fetches comment threads for a given video ID using YouTube Data API.
    Stops early if two consecutive pages have no comments with >=10 likes.
    Stores raw results in GCS and updates manifest.

    Optional: Stop after `max_api_calls` pages.

    Returns the GCS path of the saved file (if any), or None if already processed.
    """
    youtube: Resource = get_youtube()
    manifest_path = video_comments_seen_path(video_id)

    if not dry_run and file_exists_in_gcs(GCS_BUCKET_DATA, manifest_path):
        logger.info(f"⏩ Skipping video {video_id} — already fetched (manifest exists)")
        return None

    logger.info(f"🗨️ Fetching comment threads for video {video_id}")

    all_items: List[dict] = []
    next_page_token: Optional[str] = None
    consecutive_low_like_pages = 0
    page_number = 0
    api_calls_made = 0

    try:
        while True:
            if max_api_calls is not None and api_calls_made >= max_api_calls:
                logger.info(f"🛑 Reached max_api_calls={max_api_calls}. Stopping.")
                break

            page_number += 1
            api_calls_made += 1

            request = youtube.commentThreads().list(
                part="id,snippet,replies",
                videoId=video_id,
                order="relevance",
                maxResults=100,
                pageToken=next_page_token
            )
            response = request.execute()
            items = response.get("items", [])

            logger.info(f"📄 Page {page_number}: {len(items)} items fetched")
            all_items.extend(items)

            # Check for like threshold
            has_high_like = any(
                item.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                    .get("likeCount", 0) >= LIKE_THRESHOLD
                for item in items
            )

            if not has_high_like:
                consecutive_low_like_pages += 1
                logger.info(f"⚠️ Page {page_number} below like threshold ({consecutive_low_like_pages} in a row)")
                if consecutive_low_like_pages >= MAX_CONSECUTIVE_LOW_LIKE_PAGES:
                    logger.info("⛔ Breaking early due to low engagement")
                    break
            else:
                consecutive_low_like_pages = 0

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

    except HttpError as e:
        logger.error(f"❌ YouTube API error while fetching comments for {video_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"❌ Unexpected error during comment fetch: {e}")
        return None

    if not dry_run:
        gcs_path = video_comments_path(video_id)
        write_json_to_gcs(GCS_BUCKET_DATA, gcs_path, {"items": all_items})
        write_json_to_gcs(GCS_BUCKET_DATA, manifest_path, {"fetched_at": datetime.utcnow().isoformat()})

        logger.info(f"✅ Stored {len(all_items)} comments for video {video_id} to {gcs_path}")
        return gcs_path
    else:
        logger.info(f"💡 Dry run: {len(all_items)} comments would have been saved for video {video_id}")
        return None
