# app/orchestration/pipeline.py

import logging
from app.utils.clients import get_youtube, get_gcs
from app.utils.paths import (
    get_trending_manifest_path,
    get_trending_raw_path,
    get_videos_seen_path,
    get_comment_raw_path,
    get_channels_seen_path,
    get_channel_raw_path,
    get_featured_channel_raw_path,
    get_featured_channel_edge_raw_path,
)
from utils.gcs_utils import file_exists_in_gcs, save_json, load_json
from app.utils.fetch_trending_videos_by_category import (
    fetch_trending_videos,
    fetch_comment_threads,
    fetch_channel_data,
    fetch_channel_sections,
)
from utils.parsers import parse_comments, parse_channels_from_comments, parse_featured_channels_from_section

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def orchestrate_trending_video_ingestion(region: str, category: str, page_token: str = None):
    """
    Fetch trending videos by region and category, track using manifest, and store in GCS.
    """
    key = f"{region}_{category}_page_{page_token or 0}"
    manifest_path = get_trending_manifest_path()
    manifest = load_json(manifest_path) if file_exists_in_gcs(manifest_path) else {}

    if key in manifest:
        logger.info(f"Trending fetch skipped: already fetched {key}")
        return

    try:
        response = fetch_trending_videos(region, category, page_token)
        raw_path = get_trending_raw_path(region, category, page_token)
        save_json(raw_path, response)
        manifest[key] = region  # Just a placeholder value
        save_json(manifest_path, manifest)
        logger.info(f"Fetched and stored trending videos: {key}")
    except Exception as e:
        logger.error(f"Failed to fetch trending videos for {key}: {e}")

def orchestrate_video_comment_fetch(video_id: str):
    """
    Fetch comment threads for a video and store raw JSONs.
    """
    try:
        comments = fetch_comment_threads(video_id)
        for i, page in enumerate(comments):
            raw_path = get_comment_raw_path(video_id, i)
            save_json(raw_path, page)
            logger.info(f"Saved comments for video {video_id}, page {i}")
    except Exception as e:
        logger.error(f"Error fetching comments for video {video_id}: {e}")

def orchestrate_commenter_channel_discovery(video_id: str):
    """
    Parse commenters from raw comments, fetch channel data if not seen.
    """
    try:
        comment_pages = parse_comments(video_id)
        channel_ids = parse_channels_from_comments(comment_pages)

        for channel_id in channel_ids:
            seen_path = get_channels_seen_path(channel_id)
            if file_exists_in_gcs(seen_path):
                logger.debug(f"Skipping seen channel: {channel_id}")
                continue

            try:
                data = fetch_channel_data(channel_id)
                raw_path = get_channel_raw_path(channel_id)
                save_json(raw_path, data)
                save_json(seen_path, {"seen": True})
                logger.info(f"Fetched and stored channel data: {channel_id}")
            except Exception as inner:
                logger.warning(f"Failed to fetch channel {channel_id}: {inner}")

    except Exception as e:
        logger.error(f"Channel discovery failed for video {video_id}: {e}")

def orchestrate_featured_channels_enrichment(channel_id: str):
    """
    Fetch channelSections for a channel, extract featured, fetch their data.
    """
    try:
        section_data = fetch_channel_sections(channel_id)
        save_json(get_featured_channel_edge_raw_path(channel_id), section_data)
        featured_ids = parse_featured_channels_from_section(section_data)

        for fc_id in featured_ids:
            seen_path = get_channels_seen_path(fc_id)
            if file_exists_in_gcs(seen_path):
                logger.debug(f"Skipping seen featured channel: {fc_id}")
                continue

            try:
                data = fetch_channel_data(fc_id)
                save_json(get_featured_channel_raw_path(fc_id), data)
                save_json(seen_path, {"seen": True})
                logger.info(f"Fetched and stored featured channel data: {fc_id}")
            except Exception as inner:
                logger.warning(f"Failed to fetch featured channel {fc_id}: {inner}")

    except Exception as e:
        logger.error(f"Featured enrichment failed for {channel_id}: {e}")

# Entry points for orchestration
if __name__ == "__main__":
    # orchestrate_trending_videos()
    # Add more orchestration calls here
