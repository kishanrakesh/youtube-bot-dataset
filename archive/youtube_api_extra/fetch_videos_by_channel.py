import json
from typing import List, Dict
from googleapiclient.errors import HttpError
from app.utils.clients import get_youtube
from app.utils.gcs_utils import read_json_from_gcs, write_json_to_gcs, file_exists_in_gcs
from app.utils.paths import (
    video_by_channel_raw_path,
    video_metadata_seen_path,
    videos_by_channel_seen_path,
    channel_metadata_raw_path
)
from app.utils.logging import get_logger
from datetime import datetime
import os
from app.env import GCS_BUCKET_DATA

from app.utils.clients import get_youtube

logger = get_logger()

def has_seen_channel(channel_id: str, page: int) -> bool:
    """Check if this channel's videos have already been fetched."""
    path = videos_by_channel_seen_path(channel_id, page)
    return read_json_from_gcs(GCS_BUCKET_DATA, path) is not None

def mark_channel_seen(channel_id: str, page: int):
    seen_path = videos_by_channel_seen_path(channel_id, page)
    write_json_to_gcs(GCS_BUCKET_DATA, seen_path, {
        "fetched_at": datetime.utcnow().isoformat()
    })

def save_channel_videos(channel_id: str, videos: List[Dict], page_number: int):
    """Save raw video list for this channel to GCS."""
    path = video_by_channel_raw_path(channel_id, page_number)
    write_json_to_gcs(GCS_BUCKET_DATA, path, data={"items": videos})

def fetch_videos_by_channel(channel_id: str, dry_run: bool = False, max_pages: int = None):
    """
    Fetch videos uploaded by a specific channel using the uploads playlist ID.
    Supports optional max_pages limit to avoid fetching excessively large channels.
    Skips pages that are already fetched by checking GCS seen flags.
    """
    logger.info(f"🚀 Starting fetch for videos by channel: {channel_id}")
    youtube = get_youtube()

    # Step 1: Read the channel metadata from GCS to get uploads_playlist_id
    try:
        channel_data = read_json_from_gcs(GCS_BUCKET_DATA, channel_metadata_raw_path(channel_id))
        uploads_playlist_id = channel_data.get("uploads_playlist_id")
        if not uploads_playlist_id:
            logger.warning(f"⚠️ No uploads_playlist_id found for channel {channel_id}. Skipping.")
            return
    except Exception as e:
        logger.exception(f"❌ Failed to read channel metadata for {channel_id}")
        return

    all_videos = []
    next_page_token = None
    page_number = 1

    try:
        while True:
            if max_pages is not None and page_number > max_pages:
                logger.info(f"⏹️ Reached max_pages limit ({max_pages}), stopping early.")
                break

            if has_seen_channel(channel_id, page_number):
                logger.info(f"⏩ Page {page_number} already fetched for channel {channel_id}, skipping.")
                page_number += 1
                continue

            request = youtube.playlistItems().list(
                part="id,snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            items = response.get("items", [])
            all_videos.extend(items)

            logger.info(f"📄 Page {page_number}: Retrieved {len(items)} videos")

            if not dry_run:
                save_channel_videos(channel_id, items, page_number)
                mark_channel_seen(channel_id, page_number)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                logger.info("✅ No more pages to fetch for this channel.")
                break

            page_number += 1

    except HttpError as e:
        logger.error(f"❌ YouTube API error for channel {channel_id}: {e}")
        return
    except Exception as e:
        logger.exception(f"❌ Unexpected error for channel {channel_id}: {e}")
        return

    logger.info(f"✅ Fetched {len(all_videos)} total videos for channel {channel_id}")
