# app/gcs/gcs_utils.py

import json, uuid, io
import logging
from google.cloud import storage
from typing import Optional, List

from app.utils.clients import get_gcs

logger = logging.getLogger(__name__)
gcs = get_gcs()


def file_exists_in_gcs(bucket_name: str, blob_path: str) -> bool:
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    exists = blob.exists()
    logger.debug(f"Checked existence of {blob_path}: {exists}")
    return exists


def write_json_to_gcs(bucket_name: str, blob_path: str, data: dict):
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(data, indent=2), content_type="application/json")
    logger.info(f"Uploaded JSON to {blob_path}")


def upload_bytes(bucket_name: str, blob_path: str, byte_data: bytes, content_type: str = "application/octet-stream"):
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(byte_data, content_type=content_type)
    logger.info(f"Uploaded bytes to {blob_path}")


def read_json_from_gcs(bucket_name: str, blob_path: str) -> Optional[dict]:
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    if blob.exists():
        data = json.loads(blob.download_as_text())
        logger.info(f"Downloaded JSON from {blob_path}")
        return data
    else:
        logger.warning(f"Tried to download non-existent blob: {blob_path}")
        return None


def download_bytes(bucket_name: str, blob_path: str) -> Optional[bytes]:
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    if blob.exists():
        data = blob.download_as_bytes()
        logger.info(f"Downloaded bytes from {blob_path}")
        return data
    else:
        logger.warning(f"Tried to download non-existent blob: {blob_path}")
        return None


def list_files(bucket_name: str, prefix: str = "") -> list:
    bucket = gcs.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    files = [blob.name for blob in blobs]
    logger.debug(f"Listed files under prefix '{prefix}': {len(files)} found")
    return files


def delete_file(bucket_name: str, blob_path: str):
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.delete()
    logger.info(f"Deleted blob: {blob_path}")

def list_gcs_files(bucket_name: str, prefix: str = "") -> List[str]:
    """
    List all file paths in a GCS bucket under a given prefix.
    
    Args:
        bucket_name: Name of the GCS bucket.
        prefix: Path prefix (e.g. "youtube-bot-dataset/video_comments/raw/").

    Returns:
        List of file paths (strings) relative to the bucket.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    return [blob.name for blob in blobs]


def upload_file_to_gcs(
    bucket_name: str,
    path: str,
    local_path: str,
    *,
    content_type: Optional[str] = None,
    cache_control: Optional[str] = None,
) -> str:
    """
    Upload a local file to GCS at `path`.
    Returns the gs:// URI.
    """
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(path)
    if cache_control:
        blob.cache_control = cache_control
    with open(local_path, "rb") as f:
        blob.upload_from_file(f, rewind=True, content_type=content_type)
    # Ensure metadata (e.g., cache-control) is persisted if set pre-upload
    if cache_control:
        blob.patch()
    return f"gs://{bucket_name}/{path}"

def upload_bytes_to_gcs(
    bucket_name: str,
    path: str,
    data: bytes,
    *,
    content_type: Optional[str] = None,
    cache_control: Optional[str] = None,
) -> str:
    """
    Upload raw bytes to GCS at `path`.
    Returns the gs:// URI.
    """
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(path)
    if cache_control:
        blob.cache_control = cache_control
    blob.upload_from_string(data, content_type=content_type)
    if cache_control:
        blob.patch()
    return f"gs://{bucket_name}/{path}"

def upload_png(bucket_name: str, cid: str, png_bytes: bytes) -> str:
    """Upload PNG to GCS and return gs:// URI."""
    path = f"channel_screenshots/raw/{cid}_{uuid.uuid4().hex}.png"
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(path)
    blob.upload_from_file(io.BytesIO(png_bytes), content_type="image/png")
    return f"gs://{bucket_name}/{path}"