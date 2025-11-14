"""Fetch general trending videos from YouTube API.

Retrieves trending videos for a region without category filtering,
handling pagination and duplicate detection across pages.
"""

from datetime import datetime
from typing import Optional

from googleapiclient.errors import HttpError

from app.utils.clients import get_youtube
from app.utils.gcs_utils import read_json_from_gcs, write_json_to_gcs
from app.utils.paths import trending_video_raw_path, trending_video_manifest_path, trending_seen_path
from app.utils.logging import get_logger

LOGGER = get_logger()
BUCKET = "yt-bot-data"


def should_skip_general_trending(region: str, date: str, page: int = 1) -> bool:
    """Check if a trending page has already been fetched.
    
    Args:
        region: Region code (e.g., 'US', 'GB')
        date: Date string in YYYY-MM-DD format
        page: Page number
        
    Returns:
        True if page has been seen, False otherwise
    """
    seen_path = trending_seen_path(region, "general", page, date)
    return read_json_from_gcs(BUCKET, seen_path) is not None


def mark_trending_page_seen(region: str, category_id: str, page: int, fetch_date: str) -> None:
    """Mark a trending page as seen in GCS.
    
    Args:
        region: Region code (e.g., 'US', 'GB')
        category_id: Category identifier (or 'general')
        page: Page number
        fetch_date: Date string in YYYY-MM-DD format
    """
    seen_path = trending_seen_path(region, category_id, page, fetch_date)
    write_json_to_gcs(BUCKET, seen_path, {
        "fetched_at": datetime.now().isoformat()
    })


def save_page_to_gcs(region: str, date: str, page: int, response: dict) -> None:
    """Save a trending videos page response to GCS and update manifest.
    
    Args:
        region: Region code (e.g., 'US', 'GB')
        date: Date string in YYYY-MM-DD format
        page: Page number
        response: YouTube API response dictionary
    """
    path = trending_video_raw_path(region, "general", page, dt=date)
    write_json_to_gcs(BUCKET, path, response)
    LOGGER.info(f"💾 Saved general trending page {page} → gs://{BUCKET}/{path}")

    manifest_path = trending_video_manifest_path()
    manifest = read_json_from_gcs(BUCKET, manifest_path) or {}
    key = f"{date}_{region}_general_page_{page}"
    manifest[key] = {"gcs_path": path, "saved_at": datetime.now().isoformat()}
    write_json_to_gcs(BUCKET, manifest_path, manifest)
    LOGGER.info(f"📝 Updated manifest with page {page}: {manifest_path}")


def fetch_trending_videos_general(
    region: str,
    date: Optional[str] = None,
    dry_run: bool = False,
    max_api_calls: Optional[int] = None
) -> None:
    """Fetch general trending videos for a region with pagination.
    
    Retrieves trending videos without category filtering, handling
    pagination and deduplication across pages.
    
    Args:
        region: Region code (e.g., 'US', 'GB')
        date: Date string in YYYY-MM-DD format (defaults to today)
        dry_run: If True, don't save to GCS
        max_api_calls: Maximum number of API calls to make (for testing)
    """
    youtube = get_youtube()
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    page = 1
    api_calls_made = 0
    seen_ids = set()
    next_page_token = None

    while True:
        if max_api_calls is not None and api_calls_made >= max_api_calls:
            LOGGER.info(f"🛑 Reached max_api_calls={max_api_calls}. Stopping.")
            page += 1
            continue

        if should_skip_general_trending(region, date, page):
            LOGGER.info(f"✅ Already fetched page {page} for {region}/{date}, skipping")
            page += 1
            continue

        try:
            api_calls_made += 1
            response = youtube.videos().list(
                part="id,snippet,statistics",
                chart="mostPopular",
                regionCode=region,
                maxResults=50,
                pageToken=next_page_token
            ).execute()

            items = response.get("items", [])
            new_items = [item for item in items if item.get("id") not in seen_ids]
            seen_ids.update(item.get("id") for item in new_items)

            if not dry_run:
                save_page_to_gcs(region, date, page, response)
                mark_trending_page_seen(region, "general", page, date)

            LOGGER.info(f"📦 Page {page}: stored {len(new_items)} videos")

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                LOGGER.info("✅ No more pages to fetch.")
                break

            page += 1

        except HttpError as e:
            LOGGER.warning(f"⚠️ API error for {region} (general trending): {e}")
            break
        except Exception as e:
            LOGGER.exception(f"🔥 Unexpected error: {e}")
            break
