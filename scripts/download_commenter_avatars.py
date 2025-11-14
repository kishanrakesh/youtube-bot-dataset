#!/usr/bin/env python3
"""
Download profile images of all commenters from YouTube comment threads.

This script:
1. Queries Firestore for comment JSON files
2. Extracts commenter channel IDs and avatar URLs
3. Downloads high-resolution avatars
4. Organizes them into bot/human/unlabeled folders for training
5. Optionally uses Playwright to scrape avatars from live comment sections

Usage:
    python scripts/download_commenter_avatars.py --limit 100
    python scripts/download_commenter_avatars.py --use-playwright --video-id abc123
"""

import argparse
import asyncio
import hashlib
import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

import cv2
import numpy as np
import requests
from google.cloud import firestore, storage
from playwright.async_api import async_playwright

from app.pipeline.channels.scraping import PlaywrightContext
from app.utils.image_processing import upgrade_avatar_url

# ───── Configuration ─────
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("DATASET_BUCKET", "yt-bot-dataset")
OUTPUT_DIR = Path("data/datasets/avatar_images")
TEMP_DIR = OUTPUT_DIR / "unlabeled"

# Avatar quality
AVATAR_SIZE = 256  # Download high-res for training

# ───── Firestore & GCS ─────
_db: firestore.Client | None = None
_storage: storage.Client | None = None


def db() -> firestore.Client:
    """Get or create Firestore client."""
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def storage_client():
    """Get or create GCS client."""
    global _storage
    if _storage is None:
        _storage = storage.Client()
    return _storage


def bucket():
    """Get GCS bucket."""
    return storage_client().bucket(BUCKET_NAME)


# ───── Download & Save ─────
def download_avatar(url: str, timeout: int = 10) -> Optional[np.ndarray]:
    """Download avatar image from URL.
    
    Args:
        url: Avatar image URL
        timeout: Request timeout in seconds
        
    Returns:
        Image as numpy array (BGR), or None if failed
    """
    try:
        url = upgrade_avatar_url(url, size=AVATAR_SIZE)
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        LOGGER.warning(f"Failed to download {url}: {e}")
        return None


def save_avatar(img: np.ndarray, channel_id: str, output_dir: Path) -> Optional[Path]:
    """Save avatar image to disk.
    
    Args:
        img: Image as numpy array
        channel_id: YouTube channel ID
        output_dir: Directory to save to
        
    Returns:
        Path to saved file, or None if failed
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"{channel_id}.jpg"
        
        # Don't overwrite existing files
        if filepath.exists():
            LOGGER.debug(f"Skipping existing: {filepath}")
            return filepath
        
        success = cv2.imwrite(str(filepath), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if success:
            LOGGER.info(f"✅ Saved: {filepath}")
            return filepath
        else:
            LOGGER.warning(f"Failed to write: {filepath}")
            return None
    except Exception as e:
        LOGGER.error(f"Error saving avatar for {channel_id}: {e}")
        return None


# ───── Extract from Comment JSONs ─────
def extract_avatars_from_comment_json(json_data: dict) -> List[Dict[str, str]]:
    """Extract commenter info from YouTube comment thread JSON.
    
    Args:
        json_data: Comment thread JSON from YouTube API
        
    Returns:
        List of dicts with 'channel_id', 'author', 'avatar_url'
    """
    commenters = []
    
    try:
        items = json_data.get("items", [])
        for item in items:
            # Top-level comment
            top_comment = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            
            channel_id = top_comment.get("authorChannelId", {}).get("value")
            author = top_comment.get("authorDisplayName")
            avatar_url = top_comment.get("authorProfileImageUrl")
            
            if channel_id and avatar_url:
                commenters.append({
                    "channel_id": channel_id,
                    "author": author,
                    "avatar_url": avatar_url
                })
            
            # Replies
            replies = item.get("replies", {}).get("comments", [])
            for reply in replies:
                reply_snippet = reply.get("snippet", {})
                
                channel_id = reply_snippet.get("authorChannelId", {}).get("value")
                author = reply_snippet.get("authorDisplayName")
                avatar_url = reply_snippet.get("authorProfileImageUrl")
                
                if channel_id and avatar_url:
                    commenters.append({
                        "channel_id": channel_id,
                        "author": author,
                        "avatar_url": avatar_url
                    })
    except Exception as e:
        LOGGER.error(f"Error extracting from JSON: {e}")
    
    return commenters


def fetch_comment_jsons_from_gcs(limit: int = 100) -> List[dict]:
    """Fetch comment thread JSONs from GCS.
    
    Args:
        limit: Maximum number of JSON files to fetch
        
    Returns:
        List of comment thread JSON objects
    """
    LOGGER.info(f"Fetching up to {limit} comment JSONs from GCS...")
    
    blobs = bucket().list_blobs(prefix="comments/", max_results=limit)
    json_objects = []
    
    for blob in blobs:
        if not blob.name.endswith('.json'):
            continue
        
        try:
            content = blob.download_as_text()
            import json
            data = json.loads(content)
            json_objects.append(data)
        except Exception as e:
            LOGGER.warning(f"Failed to load {blob.name}: {e}")
    
    LOGGER.info(f"Loaded {len(json_objects)} comment JSONs")
    return json_objects


# ───── Playwright Scraping ─────
async def scrape_avatars_from_video_playwright(video_id: str) -> List[Dict[str, str]]:
    """Scrape commenter avatars from a YouTube video using Playwright.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        List of dicts with 'channel_id', 'author', 'avatar_url'
    """
    LOGGER.info(f"Scraping avatars from video {video_id} using Playwright...")
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    commenters = []
    
    async with PlaywrightContext() as context:
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)  # Let page render
            
            # Scroll to comments section
            await page.evaluate("window.scrollTo(0, 800)")
            await asyncio.sleep(2)
            
            # Wait for comments to load
            try:
                await page.wait_for_selector("ytd-comment-thread-renderer", timeout=10000)
            except:
                LOGGER.warning("No comments found on video")
                return commenters
            
            # Scroll to load more comments
            for _ in range(5):  # Load ~50-100 comments
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)
            
            # Extract avatar URLs from rendered page
            avatar_elements = await page.query_selector_all("ytd-comment-view-model yt-img-shadow img")
            
            LOGGER.info(f"Found {len(avatar_elements)} avatar elements")
            
            for elem in avatar_elements:
                try:
                    # Get avatar URL
                    avatar_url = await elem.get_attribute("src")
                    if not avatar_url or "yt3.ggpht.com" not in avatar_url:
                        continue
                    
                    # Try to get channel ID from nearby button
                    parent = await elem.evaluate_handle("el => el.closest('ytd-comment-view-model')")
                    button = await parent.query_selector("#author-thumbnail-button")
                    
                    if button:
                        aria_label = await button.get_attribute("aria-label")
                        # aria_label is like "@username"
                        handle = aria_label.strip("@") if aria_label else None
                        
                        # We can't easily get channel ID from rendered page,
                        # so we'll use URL hash as unique identifier
                        url_hash = hashlib.md5(avatar_url.encode()).hexdigest()[:16]
                        channel_id = f"SCRAPED_{url_hash}"
                        
                        commenters.append({
                            "channel_id": channel_id,
                            "author": handle or "Unknown",
                            "avatar_url": avatar_url
                        })
                except Exception as e:
                    LOGGER.debug(f"Failed to extract avatar: {e}")
                    continue
            
        except Exception as e:
            LOGGER.error(f"Error scraping video {video_id}: {e}")
        finally:
            await page.close()
    
    # Deduplicate by avatar URL
    seen = set()
    unique_commenters = []
    for c in commenters:
        if c["avatar_url"] not in seen:
            seen.add(c["avatar_url"])
            unique_commenters.append(c)
    
    LOGGER.info(f"Scraped {len(unique_commenters)} unique avatars")
    return unique_commenters


# ───── Main Processing ─────
def download_avatars_from_json(
    json_objects: List[dict],
    output_dir: Path = TEMP_DIR
) -> Dict[str, int]:
    """Download avatars from comment JSON objects.
    
    Args:
        json_objects: List of comment thread JSONs
        output_dir: Directory to save avatars to
        
    Returns:
        Dict with stats: {"downloaded": X, "skipped": Y, "failed": Z}
    """
    stats = {"downloaded": 0, "skipped": 0, "failed": 0}
    seen_channels: Set[str] = set()
    
    # Extract all commenter info
    all_commenters = []
    for json_data in json_objects:
        commenters = extract_avatars_from_comment_json(json_data)
        all_commenters.extend(commenters)
    
    LOGGER.info(f"Found {len(all_commenters)} total commenters")
    
    # Download avatars
    for commenter in all_commenters:
        channel_id = commenter["channel_id"]
        avatar_url = commenter["avatar_url"]
        
        # Skip duplicates
        if channel_id in seen_channels:
            stats["skipped"] += 1
            continue
        
        seen_channels.add(channel_id)
        
        # Check if already exists
        existing_file = output_dir / f"{channel_id}.jpg"
        if existing_file.exists():
            LOGGER.debug(f"Already exists: {channel_id}")
            stats["skipped"] += 1
            continue
        
        # Download
        img = download_avatar(avatar_url)
        if img is None:
            stats["failed"] += 1
            continue
        
        # Save
        saved_path = save_avatar(img, channel_id, output_dir)
        if saved_path:
            stats["downloaded"] += 1
        else:
            stats["failed"] += 1
    
    return stats


async def download_avatars_from_video(
    video_id: str,
    output_dir: Path = TEMP_DIR
) -> Dict[str, int]:
    """Download avatars by scraping a YouTube video's comments.
    
    Args:
        video_id: YouTube video ID
        output_dir: Directory to save avatars to
        
    Returns:
        Dict with stats
    """
    stats = {"downloaded": 0, "skipped": 0, "failed": 0}
    
    # Scrape avatars
    commenters = await scrape_avatars_from_video_playwright(video_id)
    
    # Download
    for commenter in commenters:
        channel_id = commenter["channel_id"]
        avatar_url = commenter["avatar_url"]
        
        existing_file = output_dir / f"{channel_id}.jpg"
        if existing_file.exists():
            stats["skipped"] += 1
            continue
        
        img = download_avatar(avatar_url)
        if img is None:
            stats["failed"] += 1
            continue
        
        saved_path = save_avatar(img, channel_id, output_dir)
        if saved_path:
            stats["downloaded"] += 1
        else:
            stats["failed"] += 1
    
    return stats


# ───── CLI ─────
def main():
    parser = argparse.ArgumentParser(description="Download commenter profile images")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of comment JSON files to process"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(TEMP_DIR),
        help="Output directory for avatars"
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Use Playwright to scrape from live page instead of JSON files"
    )
    parser.add_argument(
        "--video-id",
        type=str,
        help="YouTube video ID to scrape (requires --use-playwright)"
    )
    
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    LOGGER.info(f"📥 Starting avatar download...")
    LOGGER.info(f"Output directory: {output_dir}")
    
    if args.use_playwright:
        if not args.video_id:
            LOGGER.error("--video-id required when using --use-playwright")
            return
        
        stats = asyncio.run(download_avatars_from_video(args.video_id, output_dir))
    else:
        # Fetch from GCS comment JSONs
        json_objects = fetch_comment_jsons_from_gcs(limit=args.limit)
        if not json_objects:
            LOGGER.warning("No comment JSONs found. Try using --use-playwright")
            return
        
        stats = download_avatars_from_json(json_objects, output_dir)
    
    # Report
    LOGGER.info(f"\n{'='*50}")
    LOGGER.info(f"✅ Download Complete")
    LOGGER.info(f"{'='*50}")
    LOGGER.info(f"Downloaded: {stats['downloaded']}")
    LOGGER.info(f"Skipped:    {stats['skipped']}")
    LOGGER.info(f"Failed:     {stats['failed']}")
    LOGGER.info(f"Total:      {stats['downloaded'] + stats['skipped'] + stats['failed']}")
    LOGGER.info(f"{'='*50}\n")
    
    LOGGER.info(f"Avatars saved to: {output_dir}")
    LOGGER.info(f"\nNext steps:")
    LOGGER.info(f"1. Label images as bot/human by moving to train/bot/ or train/human/")
    LOGGER.info(f"2. Run: python ml/training/avatar/train_avatar_classifier.py")


if __name__ == "__main__":
    main()
