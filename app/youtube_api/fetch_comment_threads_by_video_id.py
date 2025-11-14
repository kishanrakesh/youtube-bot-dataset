"""Fetch comment threads for a video from YouTube API.

Retrieves comment threads with intelligent early stopping based on
engagement metrics (like counts) to avoid quota waste on low-engagement videos.
"""

from datetime import datetime
from typing import Optional

from googleapiclient.errors import HttpError

from app.utils.clients import get_youtube
from app.utils.gcs_utils import write_json_to_gcs, file_exists_in_gcs
from app.utils.paths import video_comments_path, video_comments_seen_path
from app.utils.logging import get_logger
from app.env import GCS_BUCKET_DATA

LOGGER = get_logger()

LIKE_THRESHOLD = 10
MAX_CONSECUTIVE_LOW_LIKE_PAGES = 2


def fetch_comment_threads_by_video_id(
    video_id: str,
    dry_run: bool = False,
    max_api_calls: Optional[int] = None
) -> Optional[str]:
    """Fetch comment threads for a video with intelligent early stopping.
    
    Stops early if two consecutive pages have no comments with >=10 likes,
    conserving API quota for low-engagement videos.
    
    Args:
        video_id: YouTube video ID
        dry_run: If True, don't save to GCS
        max_api_calls: Maximum number of API calls to make (for testing)
        
    Returns:
        GCS path of saved file, or None if already processed or dry run
    """
    youtube = get_youtube()
    manifest_path = video_comments_seen_path(video_id)

    if not dry_run and file_exists_in_gcs(GCS_BUCKET_DATA, manifest_path):
        LOGGER.info(f"⏩ Skipping video {video_id} — already fetched (manifest exists)")
        return None

    LOGGER.info(f"🗨️ Fetching comment threads for video {video_id}")

    all_items = []
    next_page_token = None
    consecutive_low_like_pages = 0
    page_number = 0
    api_calls_made = 0

    try:
        while True:
            if max_api_calls is not None and api_calls_made >= max_api_calls:
                LOGGER.info(f"🛑 Reached max_api_calls={max_api_calls}. Stopping.")
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

            LOGGER.info(f"📄 Page {page_number}: {len(items)} items fetched")
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
                LOGGER.info(f"⚠️ Page {page_number} below like threshold ({consecutive_low_like_pages} in a row)")
                if consecutive_low_like_pages >= MAX_CONSECUTIVE_LOW_LIKE_PAGES:
                    LOGGER.info("⛔ Breaking early due to low engagement")
                    break
            else:
                consecutive_low_like_pages = 0

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

    except HttpError as e:
        LOGGER.error(f"❌ YouTube API error while fetching comments for {video_id}: {e}")
        return None
    except Exception as e:
        LOGGER.exception(f"❌ Unexpected error during comment fetch: {e}")
        return None

    if not dry_run:
        gcs_path = video_comments_path(video_id)
        write_json_to_gcs(GCS_BUCKET_DATA, gcs_path, {"items": all_items})
        write_json_to_gcs(GCS_BUCKET_DATA, manifest_path, {"fetched_at": datetime.now().isoformat()})

        LOGGER.info(f"✅ Stored {len(all_items)} comments for video {video_id} to {gcs_path}")
        return gcs_path
    else:
        LOGGER.info(f"💡 Dry run: {len(all_items)} comments would have been saved for video {video_id}")
        return None
