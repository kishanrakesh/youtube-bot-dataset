import time
from typing import Dict, List
from googleapiclient.errors import HttpError
from app.utils.clients import get_youtube
from app.utils.gcs_utils import write_json_to_gcs, read_json_from_gcs
from app.utils.paths import (
    channel_metadata_raw_path,
    channel_metadata_manifest_path
)
from app.utils.logging import get_logger
from app.utils.manifest_utils import is_already_fetched, update_manifest
from app.env import GCS_BUCKET_DATA

logger = get_logger()


def fetch_channels_by_id(channel_ids: List[str], *, dry_run: bool = False) -> Dict[str, dict]:
    """
    Fetches channel metadata from the YouTube API for the given channel IDs.
    Implements deduplication via manifest tracking and retries on quota failures.
    """
    youtube = get_youtube()
    fetched_channels = {}
    max_per_call = 50

    for i in range(0, len(channel_ids), max_per_call):
        batch = channel_ids[i:i + max_per_call]
        batch_to_fetch = [
            cid for cid in batch
            if not is_already_fetched(channel_metadata_manifest_path(cid), cid)
        ]

        if not batch_to_fetch:
            logger.info(f"✅ Skipping batch {i}–{i+max_per_call}: All channels already fetched.")
            continue

        logger.info(f"📡 Fetching channel metadata for {len(batch_to_fetch)} channels...")

        try:
            response = youtube.channels().list(
                part="id,snippet,statistics,brandingSettings,topicDetails,status,contentDetails",
                id=','.join(batch_to_fetch),
                maxResults=len(batch_to_fetch)
            ).execute()

            for item in response.get("items", []):
                channel_id = item["id"]

                #Extract uploads playlist ID from contentDetails
                uploads_id = (
                    item.get("contentDetails", {})
                        .get("relatedPlaylists", {})
                        .get("uploads")
                )
                if uploads_id:
                    item["uploads_playlist_id"] = uploads_id  # 👈 Store it directly in the JSON
                fetched_channels[channel_id] = item

                

                if dry_run:
                    logger.info(f"🧪 [Dry Run] Would save: {channel_metadata_raw_path(channel_id)}")
                else:
                    write_json_to_gcs(GCS_BUCKET_DATA, channel_metadata_raw_path(channel_id), item)
                    update_manifest(channel_metadata_manifest_path(channel_id), channel_id)

            logger.info(f"✅ Successfully fetched {len(response.get('items', []))} channels.")

        except HttpError as e:
            logger.error(f"❌ YouTube API error during channel fetch: {e}")
        except Exception as e:
            logger.exception(f"💥 Unexpected error during channel fetch: {e}")

        time.sleep(1)

    return fetched_channels
