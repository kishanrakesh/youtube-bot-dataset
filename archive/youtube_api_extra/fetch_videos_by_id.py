from typing import List, Dict
from googleapiclient.errors import HttpError

from app.utils.clients import get_youtube
from app.utils.gcs_utils import read_json_from_gcs, write_json_to_gcs
from app.utils.paths import (
    video_by_id_raw_path,
    video_metadata_seen_path
)
from app.utils.logging import get_logger
from app.utils.youtube_helpers import chunk_list
from app.env import GCS_BUCKET_DATA

logger = get_logger()

def is_video_already_seen(video_id: str) -> bool:
    seen_path = video_metadata_seen_path(video_id)
    return read_json_from_gcs(GCS_BUCKET_DATA, seen_path) is not None

def mark_video_as_seen(video_id: str, dry_run: bool = False):
    seen_path = video_metadata_seen_path(video_id)
    if dry_run:
        logger.info(f"[dry-run] ✅ Would mark video {video_id} as seen at {seen_path}")
        return
    write_json_to_gcs(GCS_BUCKET_DATA, seen_path, {"seen": True})
    logger.info(f"✅ Marked video {video_id} as seen")

def fetch_video_metadata_batch(video_ids: List[str]) -> Dict[str, dict]:
    youtube = get_youtube()
    part = (
        "id,snippet,contentDetails,statistics,status,player," 
        "topicDetails,liveStreamingDetails,localizations," 
        "paidProductPlacementDetails,recordingDetails"
    )

    all_results = {}
    for batch in chunk_list(video_ids, 50):
        id_param = ",".join(batch)
        try:
            logger.info(f"⬇️  Fetching metadata for video IDs: {id_param}")
            response = youtube.videos().list(part=part, id=id_param).execute()
        except HttpError as e:
            logger.error(f"❌ YouTube API error while fetching videos: {e}")
            continue
        except Exception as e:
            logger.exception(f"❌ Unexpected error while fetching videos: {e}")
            continue

        for item in response.get("items", []):
            video_id = item.get("id")
            if video_id:
                all_results[video_id] = item

    return all_results

def save_video_metadata(video_id: str, metadata: dict, dry_run: bool = False):
    gcs_path = video_by_id_raw_path(video_id)
    if dry_run:
        logger.info(f"[dry-run] ✅ Would save video metadata to {gcs_path}")
        return
    write_json_to_gcs(GCS_BUCKET_DATA, gcs_path, metadata)
    logger.info(f"📁 Saved video metadata for {video_id} to {gcs_path}")

def fetch_videos_by_id(video_ids: List[str], dry_run: bool = False):
    to_fetch = [vid for vid in video_ids if not is_video_already_seen(vid)]

    if not to_fetch:
        logger.info("📦 All videos already seen. Nothing to fetch.")
        return

    logger.info(f"🚀 Fetching metadata for {len(to_fetch)} new video(s)")
    results = fetch_video_metadata_batch(to_fetch)

    for vid, metadata in results.items():
        save_video_metadata(vid, metadata, dry_run=dry_run)
        mark_video_as_seen(vid, dry_run=dry_run)
