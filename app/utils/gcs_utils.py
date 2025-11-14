"""Google Cloud Storage utility functions for file operations."""

import io
import json
import logging
import uuid
from typing import Optional, List

from google.cloud import storage

from app.utils.clients import get_gcs

__all__ = [
    "file_exists_in_gcs",
    "read_json_from_gcs",
    "write_json_to_gcs",
    "list_gcs_files",
    "upload_file_to_gcs",
    "upload_png",
    "delete_gcs_file",
]

LOGGER = logging.getLogger(__name__)
gcs = get_gcs()


def file_exists_in_gcs(bucket_name: str, blob_path: str) -> bool:
    """Check if a file exists in GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_path: Path to the blob within the bucket
        
    Returns:
        True if the blob exists, False otherwise
    """
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    exists = blob.exists()
    LOGGER.debug(f"Checked existence of {blob_path}: {exists}")
    return exists


def write_json_to_gcs(bucket_name: str, blob_path: str, data: dict) -> None:
    """Write a Python dict as JSON to GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_path: Path to the blob within the bucket
        data: Dictionary to serialize as JSON
    """
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(data, indent=2), content_type="application/json")
    LOGGER.info(f"Uploaded JSON to {blob_path}")


def upload_bytes(
    bucket_name: str,
    blob_path: str,
    byte_data: bytes,
    content_type: str = "application/octet-stream"
) -> None:
    """Upload raw bytes to GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_path: Path to the blob within the bucket
        byte_data: Raw bytes to upload
        content_type: MIME type of the content
    """
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(byte_data, content_type=content_type)
    LOGGER.info(f"Uploaded bytes to {blob_path}")


def read_json_from_gcs(bucket_name: str, blob_path: str) -> Optional[dict]:
    """Read and parse JSON from GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_path: Path to the blob within the bucket
        
    Returns:
        Parsed JSON as a dictionary, or None if blob doesn't exist
    """
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    if blob.exists():
        data = json.loads(blob.download_as_text())
        LOGGER.info(f"Downloaded JSON from {blob_path}")
        return data
    else:
        LOGGER.warning(f"Tried to download non-existent blob: {blob_path}")
        return None


def download_bytes(bucket_name: str, blob_path: str) -> Optional[bytes]:
    """Download raw bytes from GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_path: Path to the blob within the bucket
        
    Returns:
        Raw bytes, or None if blob doesn't exist
    """
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    if blob.exists():
        data = blob.download_as_bytes()
        LOGGER.info(f"Downloaded bytes from {blob_path}")
        return data
    else:
        LOGGER.warning(f"Tried to download non-existent blob: {blob_path}")
        return None


def list_files(bucket_name: str, prefix: str = "") -> List[str]:
    """List all files in a GCS bucket under a given prefix.
    
    Args:
        bucket_name: Name of the GCS bucket
        prefix: Path prefix to filter by
        
    Returns:
        List of blob names (file paths)
    """
    bucket = gcs.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    files = [blob.name for blob in blobs]
    LOGGER.debug(f"Listed files under prefix '{prefix}': {len(files)} found")
    return files


def delete_file(bucket_name: str, blob_path: str) -> None:
    """Delete a file from GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_path: Path to the blob to delete
    """
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.delete()
    LOGGER.info(f"Deleted blob: {blob_path}")


def list_gcs_files(bucket_name: str, prefix: str = "") -> List[str]:
    """List all file paths in a GCS bucket under a given prefix.
    
    Args:
        bucket_name: Name of the GCS bucket
        prefix: Path prefix (e.g. "youtube-bot-dataset/video_comments/raw/")
        
    Returns:
        List of file paths (strings) relative to the bucket
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
    """Upload a local file to GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        path: Destination path in GCS
        local_path: Path to local file to upload
        content_type: MIME type of the content
        cache_control: Cache-Control header value
        
    Returns:
        The gs:// URI of the uploaded file
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
    """Upload raw bytes to GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        path: Destination path in GCS
        data: Raw bytes to upload
        content_type: MIME type of the content
        cache_control: Cache-Control header value
        
    Returns:
        The gs:// URI of the uploaded file
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
    """Upload a PNG screenshot to GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        cid: Channel ID
        png_bytes: Raw PNG image bytes
        
    Returns:
        The gs:// URI of the uploaded file
    """
    path = f"channel_screenshots/raw/{cid}_{uuid.uuid4().hex}.png"
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(path)
    blob.upload_from_file(io.BytesIO(png_bytes), content_type="image/png")
    return f"gs://{bucket_name}/{path}"