#!/usr/bin/env python3
"""
Export labeled avatar dataset for image classification training.

Downloads:
- Bot avatars from GCS (avatar_gcs_uri)
- Not-bot avatars from YouTube URLs (avatar_url)

Handles:
- Channel ID vs Handle conflict detection
- Balanced sampling
- Train/val split (80/20)
"""

import os
import sys
import random
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import requests
import cv2
import numpy as np
from google.cloud import firestore, storage

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DATASET_DIR = Path("dataset")
TRAIN_DIR = DATASET_DIR / "train"
VAL_DIR = DATASET_DIR / "val"
BOT_CLASS = "bot"
NOT_BOT_CLASS = "not_bot"

# Sampling config
TRAIN_SPLIT = 0.8
NOT_BOT_SAMPLE_SIZE = 400  # Sample from 28k to balance with 237 bots
RANDOM_SEED = 42

random.seed(RANDOM_SEED)


def create_directories():
    """Create dataset directory structure."""
    for split in [TRAIN_DIR, VAL_DIR]:
        (split / BOT_CLASS).mkdir(parents=True, exist_ok=True)
        (split / NOT_BOT_CLASS).mkdir(parents=True, exist_ok=True)
    logger.info(f"✅ Created dataset directories in {DATASET_DIR}")


def download_from_gcs(gcs_uri: str) -> np.ndarray:
    """Download image from GCS and return as numpy array."""
    try:
        # Parse gs://bucket/path
        bucket_name, path = gcs_uri.replace("gs://", "").split("/", 1)
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(path)
        
        data = blob.download_as_bytes()
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        logger.warning(f"Failed to download from GCS {gcs_uri}: {e}")
        return None


def download_from_url(url: str, timeout: int = 10) -> np.ndarray:
    """Download image from URL and return as numpy array."""
    try:
        # Upgrade to higher resolution if possible
        url = upgrade_avatar_url(url, size=800)
        
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        logger.warning(f"Failed to download from URL {url[:50]}...: {e}")
        return None


def upgrade_avatar_url(url: str, size: int = 800) -> str:
    """Replace size parameter in YouTube avatar URL."""
    import re
    match = list(re.finditer(r"(=s)(\d+)(-[^?]*)", url))
    if not match:
        return url
    last = match[-1]
    start, end = last.span(2)
    return url[:start] + str(size) + url[end:]


def save_image(img: np.ndarray, filepath: Path) -> bool:
    """Save image to disk."""
    try:
        cv2.imwrite(str(filepath), img)
        return True
    except Exception as e:
        logger.warning(f"Failed to save image to {filepath}: {e}")
        return False


def collect_bot_identifiers(bot_docs: List) -> set:
    """Collect all bot channel IDs and handles to avoid conflicts."""
    identifiers = set()
    for doc in bot_docs:
        d = doc.to_dict()
        # Add channel ID
        identifiers.add(doc.id)
        # Add handle (without @)
        if d.get('handle'):
            handle = d.get('handle').lstrip('@')
            identifiers.add(handle)
    return identifiers


def export_bots(bot_docs: List, bot_identifiers: set) -> Tuple[int, int]:
    """
    Export bot avatars from GCS.
    Returns (train_count, val_count)
    """
    logger.info(f"📥 Exporting {len(bot_docs)} bot avatars from GCS...")
    
    random.shuffle(bot_docs)
    train_size = int(len(bot_docs) * TRAIN_SPLIT)
    
    train_count, val_count = 0, 0
    
    for i, doc in enumerate(bot_docs):
        d = doc.to_dict()
        gcs_uri = d.get('avatar_gcs_uri')
        
        if not gcs_uri:
            logger.debug(f"Skipping bot {doc.id} - no avatar_gcs_uri")
            continue
        
        # Download from GCS
        img = download_from_gcs(gcs_uri)
        if img is None:
            continue
        
        # Determine split
        is_train = i < train_size
        split_dir = TRAIN_DIR if is_train else VAL_DIR
        
        # Save with channel_id as filename
        filepath = split_dir / BOT_CLASS / f"{doc.id}.png"
        if save_image(img, filepath):
            if is_train:
                train_count += 1
            else:
                val_count += 1
        
        if (i + 1) % 50 == 0:
            logger.info(f"  Processed {i + 1}/{len(bot_docs)} bots...")
    
    logger.info(f"✅ Exported bots: {train_count} train, {val_count} val")
    return train_count, val_count


def export_not_bots(not_bot_docs: List, bot_identifiers: set, sample_size: int) -> Tuple[int, int]:
    """
    Export not-bot avatars from URLs.
    Filters out any conflicts with bot identifiers.
    Returns (train_count, val_count)
    """
    logger.info(f"📥 Filtering and sampling {sample_size} not-bot avatars from {len(not_bot_docs)}...")
    
    # Filter out conflicts
    safe_docs = []
    conflicts = 0
    
    for doc in not_bot_docs:
        d = doc.to_dict()
        channel_id = doc.id
        handle = d.get('handle', '').lstrip('@')
        
        # Check for conflicts
        if channel_id in bot_identifiers or (handle and handle in bot_identifiers):
            conflicts += 1
            logger.debug(f"⚠️  Skipping {channel_id} - conflicts with bot identifier")
            continue
        
        if not d.get('avatar_url'):
            continue
        
        safe_docs.append(doc)
    
    logger.info(f"  Filtered: {len(safe_docs)} safe not-bots, {conflicts} conflicts detected")
    
    # Random sample
    if len(safe_docs) > sample_size:
        sampled_docs = random.sample(safe_docs, sample_size)
    else:
        sampled_docs = safe_docs
        logger.warning(f"⚠️  Only {len(safe_docs)} safe not-bots available (requested {sample_size})")
    
    random.shuffle(sampled_docs)
    train_size = int(len(sampled_docs) * TRAIN_SPLIT)
    
    train_count, val_count = 0, 0
    
    for i, doc in enumerate(sampled_docs):
        d = doc.to_dict()
        avatar_url = d.get('avatar_url')
        
        # Download from URL
        img = download_from_url(avatar_url)
        if img is None:
            continue
        
        # Determine split
        is_train = i < train_size
        split_dir = TRAIN_DIR if is_train else VAL_DIR
        
        # Save with channel_id as filename
        filepath = split_dir / NOT_BOT_CLASS / f"{doc.id}.png"
        if save_image(img, filepath):
            if is_train:
                train_count += 1
            else:
                val_count += 1
        
        if (i + 1) % 50 == 0:
            logger.info(f"  Processed {i + 1}/{len(sampled_docs)} not-bots...")
    
    logger.info(f"✅ Exported not-bots: {train_count} train, {val_count} val")
    return train_count, val_count


def main():
    logger.info("🚀 Starting avatar dataset export...")
    
    # Create directories
    create_directories()
    
    # Connect to Firestore
    logger.info("🔗 Connecting to Firestore...")
    db = firestore.Client()
    
    # Fetch bot channels
    logger.info("📊 Fetching bot channels...")
    bot_docs = list(db.collection('channel')
        .where('is_bot', '==', True)
        .where('is_bot_checked', '==', True)
        .stream())
    
    # Filter bots with avatars
    bots_with_avatars = [doc for doc in bot_docs if doc.to_dict().get('avatar_gcs_uri')]
    logger.info(f"  Found {len(bot_docs)} bots, {len(bots_with_avatars)} with GCS avatars")
    
    # Collect bot identifiers for conflict detection
    bot_identifiers = collect_bot_identifiers(bot_docs)
    logger.info(f"  Collected {len(bot_identifiers)} unique bot identifiers (IDs + handles)")
    
    # Fetch not-bot channels
    logger.info("📊 Fetching not-bot channels...")
    not_bot_docs = list(db.collection('channel')
        .where('is_bot', '==', False)
        .where('is_bot_checked', '==', True)
        .stream())
    logger.info(f"  Found {len(not_bot_docs)} not-bots")
    
    # Export bots
    bot_train, bot_val = export_bots(bots_with_avatars, bot_identifiers)
    
    # Export not-bots
    not_bot_train, not_bot_val = export_not_bots(not_bot_docs, bot_identifiers, NOT_BOT_SAMPLE_SIZE)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("📊 EXPORT SUMMARY")
    logger.info("="*60)
    logger.info(f"Training set:")
    logger.info(f"  Bots: {bot_train}")
    logger.info(f"  Not-bots: {not_bot_train}")
    logger.info(f"  Total: {bot_train + not_bot_train}")
    logger.info(f"  Ratio: 1:{not_bot_train/max(bot_train, 1):.2f}")
    logger.info(f"")
    logger.info(f"Validation set:")
    logger.info(f"  Bots: {bot_val}")
    logger.info(f"  Not-bots: {not_bot_val}")
    logger.info(f"  Total: {bot_val + not_bot_val}")
    logger.info(f"")
    logger.info(f"Dataset location: {DATASET_DIR.absolute()}")
    logger.info("="*60)
    
    # Check if we have enough data
    if bot_train < 50 or not_bot_train < 50:
        logger.warning("⚠️  WARNING: Training set is quite small!")
        logger.warning("   Consider labeling more channels or adjusting sampling.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
