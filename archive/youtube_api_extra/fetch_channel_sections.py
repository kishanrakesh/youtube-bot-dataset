import time
from typing import Dict, Optional
from googleapiclient.errors import HttpError
from app.utils.clients import get_youtube
from app.utils.logging import get_logger
from app.utils.gcs_utils import write_json_to_gcs, read_json_from_gcs
from app.utils.paths import channel_sections_raw_path, channel_sections_manifest_path
from app.env import GCS_BUCKET_DATA

logger = get_logger()

def fetch_channel_sections(channel_id: str, dry_run: bool = False) -> Optional[Dict]:
    """
    Fetches the channelSections of a YouTube channel.

    Args:
        channel_id (str): The YouTube channel ID.
        dry_run (bool): If True, does not write any files to GCS.

    Returns:
        Optional[Dict]: The raw JSON response from the YouTube API or None on error.
    """
    youtube = get_youtube()
    gcs_path = channel_sections_raw_path(channel_id)
    manifest_path = channel_sections_manifest_path()

    # Check if this channel section has already been fetched
    try:
        seen_manifest = read_json_from_gcs(GCS_BUCKET_DATA, manifest_path) or {}
        if channel_id in seen_manifest.get("fetched", []):
            logger.info(f"🔁 ChannelSections already fetched for {channel_id}")
            return None
    except Exception as e:
        logger.warning(f"⚠️ Could not read manifest for channelSections: {e}")


    logger.info(f"📡 Fetching channelSections for {channel_id}")
    try:
        request = youtube.channelSections().list(
            part="snippet,contentDetails",
            channelId=channel_id
        )
        response = request.execute()
    except HttpError as e:
        logger.error(f"❌ YouTube API error while fetching channelSections for {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"❌ Unexpected error fetching channelSections for {channel_id}: {e}")
        return None

    if not dry_run:
        try:
            write_json_to_gcs(GCS_BUCKET_DATA, gcs_path, response)
            logger.info(f"✅ Saved channelSections for {channel_id} to GCS at {gcs_path}")

            # Update manifest
            seen_manifest.setdefault("fetched", []).append(channel_id)
            write_json_to_gcs(GCS_BUCKET_DATA, manifest_path, seen_manifest)
        except Exception as e:
            logger.error(f"❌ Failed to write channelSections or manifest to GCS: {e}")

    return response
