import os
from typing import List, Dict, Optional
from datetime import datetime
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from app.utils.gcs_utils import write_json_to_gcs, file_exists_in_gcs
from app.utils.paths import trending_video_raw_path, trending_video_manifest_path, trending_seen_path
from app.utils.clients import get_youtube, get_gcs
from app.utils.logging import get_logger
from app.utils.json_utils import ensure_folder_exists, load_json, save_json
from app.utils.gcs_utils import read_json_from_gcs
from app.env import GCS_BUCKET_DATA

logger = get_logger()
youtube = get_youtube()
gcs = get_gcs()

BUCKET = os.getenv("GCS_BUCKET_DATA")


def should_skip_fetch(region: str, category_id: str, fetch_date: str, page: int) -> bool:
    seen_path = trending_seen_path(region, category_id, page, fetch_date)
    return file_exists_in_gcs(BUCKET, seen_path)

def mark_trending_page_seen(region: str, category_id: str, page: int, fetch_date: str):
    seen_path = trending_seen_path(region, category_id, page, fetch_date)
    write_json_to_gcs(GCS_BUCKET_DATA, seen_path, {
        "fetched_at": datetime.utcnow().isoformat()
    })


def save_response_to_gcs(region: str, category_id: str, fetch_date: str, page: int, response: dict, dry_run: bool) -> str:
    gcs_path = trending_video_raw_path(region, category_id, page, fetch_date)
    if dry_run:
        logger.info(f"🧪 [Dry Run] Would save: {gcs_path}")
    else:
        write_json_to_gcs(GCS_BUCKET_DATA, gcs_path, response)
        logger.info(f"✅ Saved trending video data to {gcs_path}")

    return gcs_path


def update_manifest(region: str, category_id: str, fetch_date: str, page: int, gcs_path: str):
    manifest_path = trending_video_manifest_path()
    manifest = read_json_from_gcs(BUCKET, manifest_path) or {}
    key = f"{region}_{category_id}_{fetch_date}_page_{page}"
    manifest[key] = {"gcs_path": gcs_path, "fetched_at": datetime.utcnow().isoformat()}
    write_json_to_gcs(BUCKET, manifest_path, manifest)


def fetch_trending_videos_by_category(
    region: str,
    category_id: str,
    max_api_calls: Optional[int] = None,
    fetch_date: Optional[str] = None,
    dry_run: bool = False
):
    """
    Fetches trending videos for a given region and category.
    Supports page-based API pagination with optional max_api_calls limit.

    Each page is saved to:
    video_metadata/trending/raw/{fetch_date}/{region}_{category_id}_page_{n}.json
    """
    logger.info(f"🌎 Fetching trending videos for {region}, category {category_id}")

    fetch_date = fetch_date or datetime.utcnow().strftime("%Y-%m-%d")
    page_number = 1
    api_calls_made = 0
    seen = set()
    next_page_token = None

    while True:
        if max_api_calls is not None and api_calls_made >= max_api_calls:
            logger.info(f"🛑 Reached max_api_calls={max_api_calls}. Stopping.")
            break

        if should_skip_fetch(region, category_id, fetch_date, page_number):
            logger.info(f"✅ Already fetched page {page_number} for {region}/{category_id}/{fetch_date}, skipping")
            break

        try:
            api_calls_made += 1

            request = youtube.videos().list(
                part="id,snippet,statistics,contentDetails",
                chart="mostPopular",
                regionCode=region,
                videoCategoryId=category_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            response = request.execute()
            video_ids = [item["id"] for item in response.get("items", []) if item.get("id") not in seen]
            seen.update(video_ids)

            gcs_path = save_response_to_gcs(region, category_id, fetch_date, page_number, response, dry_run)
            update_manifest(region, category_id, fetch_date, page_number, gcs_path)

            if not dry_run:
                mark_trending_page_seen(region, category_id, page_number, fetch_date)

            logger.info(f"📦 Stored {len(video_ids)} videos to {gcs_path}")

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                logger.info("✅ No more pages to fetch.")
                break

            page_number += 1


        except HttpError as e:
            logger.error(f"❌ YouTube API error: {e}")
            break
        except Exception as e:
            logger.exception(f"🔥 Unexpected error while fetching trending videos: {e}")
            break

