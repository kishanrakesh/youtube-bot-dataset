# app/clients.py

import os
import logging
from google.cloud import storage, bigquery
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Singleton instances
_gcs: Optional[storage.Client] = None
_bq: Optional[bigquery.Client] = None
_youtube = None

# Environment variables
GCS_BUCKET_DATA = os.getenv("GCS_BUCKET_DATA", "your-default-bucket-name")
API_KEY = os.getenv("GCP_API_KEY")  # Required for YouTube API

def get_gcs() -> storage.Client:
    global _gcs
    logger.debug(f"Using GCS bucket: {GCS_BUCKET_DATA}")
    if _gcs is None:
        logger.info("Initializing GCS client...")
        _gcs = storage.Client()
    return _gcs

def get_bq() -> bigquery.Client:
    global _bq
    if _bq is None:
        logger.info("Initializing BigQuery client...")
        _bq = bigquery.Client()
    return _bq

def get_youtube():
    global _youtube
    if _youtube is None:
        if not API_KEY:
            logger.error("API_KEY not set in environment.")
            raise RuntimeError("❌ API_KEY is not set in environment variables.")
        try:
            logger.info("Initializing YouTube Data API client...")
            _youtube = build("youtube", "v3", developerKey=API_KEY)
        except HttpError as e:
            logger.exception("Failed to build YouTube API client.")
            raise RuntimeError(f"Failed to initialize YouTube API client: {e}")
    return _youtube
