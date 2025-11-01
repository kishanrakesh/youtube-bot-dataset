import logging
from app.utils.gcs_utils import read_json_from_gcs, write_json_to_gcs

logger = logging.getLogger(__name__)

BUCKET_NAME = "yt-bot-data"

def is_already_fetched(manifest_path: str, key: str) -> bool:
    manifest = read_json_from_gcs(BUCKET_NAME, manifest_path) or {}
    already_fetched = key in manifest
    logger.debug(f"Check if '{key}' is in manifest '{manifest_path}': {already_fetched}")
    return already_fetched

def update_manifest(manifest_path: str, key: str):
    manifest = read_json_from_gcs(BUCKET_NAME, manifest_path) or {}
    manifest[key] = True
    write_json_to_gcs(BUCKET_NAME, manifest_path, manifest)
    logger.info(f"Updated manifest '{manifest_path}' with key '{key}'")
