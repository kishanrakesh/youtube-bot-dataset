#!/usr/bin/env python3
"""
Download and filter commenter avatars using MobileNet classifier.

Two-stage filtering:
1. Download low-res avatars (88x88 - fast)
2. Run MobileNet classifier
3. If bot_probability > threshold, download high-res (224x224)
4. Save only suspected bot avatars for dataset

This efficiently filters thousands of commenters to find bot candidates.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import requests
from google.cloud import storage

from app.utils.image_processing import upgrade_avatar_url, download_avatar

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

# Default paths
DEFAULT_OUTPUT_DIR = "data/datasets/avatar_images/bot_candidates"
BUCKET_NAME = os.getenv("DATA_BUCKET", "yt-bot-data")


def extract_channel_id_from_url(url: str) -> Optional[str]:
    """Extract channel ID from avatar URL.
    
    Args:
        url: Avatar URL like https://yt3.ggpht.com/ytc/AIdro_abc...
        
    Returns:
        Channel ID if extractable, otherwise generates hash from URL
    """
    # YouTube avatar URLs don't contain channel IDs directly
    # So we'll create a hash from the URL path
    match = re.search(r'ggpht\.com/([^?]+)', url)
    if match:
        path = match.group(1)
        # Use first 22 chars of path as identifier (similar to channel ID length)
        return path.replace('/', '_')[:22]
    return None


def classify_avatar_mobilenet_simple(img: np.ndarray) -> tuple[str, float]:
    """Quick MobileNet classification of avatar image.
    
    Args:
        img: OpenCV image (BGR)
        
    Returns:
        Tuple of (label, bot_probability)
    """
    try:
        from app.utils.mobilenet_classifier import classify_avatar_mobilenet
        label, bot_prob, metrics = classify_avatar_mobilenet(img)
        return label, bot_prob
    except FileNotFoundError:
        LOGGER.error("❌ MobileNet model not found at models/avatar/mobilenet_v2_best.pth")
        LOGGER.error("Please train the model on Google Colab first.")
        LOGGER.error("See: docs/MOBILENET_INTEGRATION_GUIDE.md")
        raise
    except Exception as e:
        LOGGER.error(f"MobileNet classification failed: {e}")
        return "UNKNOWN", 0.0


def download_and_classify(
    url: str,
    threshold: float = 0.3,
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
) -> Optional[str]:
    """Download avatar, classify it, and save if it's a bot candidate.
    
    Args:
        url: Avatar image URL
        threshold: Bot probability threshold (0.0-1.0)
        output_dir: Directory to save bot candidates
        
    Returns:
        Saved file path if bot detected, None otherwise
    """
    try:
        # Step 1: Download low-res for quick classification (88x88)
        lowres_url = upgrade_avatar_url(url, size=88)
        img_lowres = download_avatar(lowres_url, timeout=5)
        
        if img_lowres is None:
            return None
        
        # Step 2: Classify with MobileNet
        label, bot_prob = classify_avatar_mobilenet_simple(img_lowres)
        
        # Step 3: Check threshold
        if bot_prob < threshold:
            return None  # Not a bot candidate
        
        LOGGER.info(f"🤖 Bot candidate found! Probability: {bot_prob:.2%}")
        
        # Step 4: Download high-res version (224x224) for training
        highres_url = upgrade_avatar_url(url, size=224)
        img_highres = download_avatar(highres_url, timeout=5)
        
        if img_highres is None:
            LOGGER.warning(f"Failed to download high-res version, using low-res")
            img_highres = cv2.resize(img_lowres, (224, 224))
        
        # Step 5: Save to output directory
        channel_id = extract_channel_id_from_url(url)
        if not channel_id:
            channel_id = f"unknown_{hash(url) % 1000000}"
        
        filename = f"{channel_id}_{bot_prob:.3f}.jpg"
        filepath = output_dir / filename
        
        cv2.imwrite(str(filepath), img_highres)
        return str(filepath)
        
    except Exception as e:
        LOGGER.warning(f"Failed to process {url}: {e}")
        return None


def get_avatar_urls_from_gcs(bucket_name: str, limit: int = 1000) -> Set[str]:
    """Fetch avatar URLs from comment JSON files in GCS.
    
    Args:
        bucket_name: GCS bucket name
        limit: Max number of comment files to process
        
    Returns:
        Set of unique avatar URLs
    """
    LOGGER.info(f"📥 Fetching comment JSONs from gs://{bucket_name}/comments/...")
    
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix="comments/", max_results=limit))
    
    LOGGER.info(f"Found {len(blobs)} comment files")
    
    avatar_urls = set()
    
    for i, blob in enumerate(blobs, 1):
        if i % 10 == 0:
            LOGGER.info(f"Processing file {i}/{len(blobs)}...")
        
        try:
            content = blob.download_as_text()
            data = json.loads(content)
            
            # Extract avatar URLs from comment threads
            items = data.get("items", [])
            for item in items:
                snippet = item.get("snippet", {})
                top_comment = snippet.get("topLevelComment", {})
                comment_snippet = top_comment.get("snippet", {})
                avatar_url = comment_snippet.get("authorProfileImageUrl")
                
                if avatar_url:
                    avatar_urls.add(avatar_url)
                    
        except Exception as e:
            LOGGER.warning(f"Failed to process {blob.name}: {e}")
            continue
    
    LOGGER.info(f"✅ Extracted {len(avatar_urls)} unique avatar URLs")
    return avatar_urls


async def scrape_avatars_from_video_playwright(video_id: str) -> Set[str]:
    """Scrape commenter avatars from a YouTube video using Playwright.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Set of avatar URLs
    """
    from playwright.async_api import async_playwright
    
    LOGGER.info(f"🌐 Scraping avatars from video: {video_id}")
    
    avatar_urls = set()
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            
            # Scroll to load comments
            LOGGER.info("Scrolling to load comments...")
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)
            
            # Extract avatar images
            avatar_elements = await page.query_selector_all("#author-thumbnail img")
            LOGGER.info(f"Found {len(avatar_elements)} avatar elements")
            
            for elem in avatar_elements:
                src = await elem.get_attribute("src")
                if src and "ggpht.com" in src:
                    avatar_urls.add(src)
            
        except Exception as e:
            LOGGER.error(f"Failed to scrape video: {e}")
        finally:
            await browser.close()
    
    LOGGER.info(f"✅ Scraped {len(avatar_urls)} avatar URLs")
    return avatar_urls


def main(
    limit: int = 1000,
    threshold: float = 0.3,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    use_playwright: bool = False,
    video_id: Optional[str] = None
):
    """Main entry point for bot avatar downloading.
    
    Args:
        limit: Max number of comment files to process (GCS mode)
        threshold: Bot probability threshold (0.0-1.0)
        output_dir: Directory to save bot candidates
        use_playwright: Whether to scrape from video instead of using GCS
        video_id: YouTube video ID (required if use_playwright=True)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    LOGGER.info("=" * 60)
    LOGGER.info("🤖 Bot Avatar Downloader with MobileNet Filtering")
    LOGGER.info("=" * 60)
    LOGGER.info(f"Output directory: {output_path}")
    LOGGER.info(f"Bot threshold: {threshold:.2%}")
    LOGGER.info(f"Mode: {'Playwright scraping' if use_playwright else 'GCS comments'}")
    LOGGER.info("=" * 60)
    
    # Get avatar URLs
    if use_playwright:
        if not video_id:
            LOGGER.error("❌ --video-id required when using --use-playwright")
            return
        avatar_urls = asyncio.run(scrape_avatars_from_video_playwright(video_id))
    else:
        avatar_urls = get_avatar_urls_from_gcs(BUCKET_NAME, limit=limit)
    
    if not avatar_urls:
        LOGGER.warning("No avatar URLs found. Exiting.")
        return
    
    # Process avatars
    LOGGER.info(f"\n🔍 Classifying {len(avatar_urls)} avatars...")
    
    stats = {
        "downloaded": 0,
        "skipped_below_threshold": 0,
        "failed": 0
    }
    
    for i, url in enumerate(avatar_urls, 1):
        if i % 50 == 0:
            LOGGER.info(f"Progress: {i}/{len(avatar_urls)} ({stats['downloaded']} bots found)")
        
        # Check if already exists
        channel_id = extract_channel_id_from_url(url)
        if channel_id:
            existing = list(output_path.glob(f"{channel_id}_*.jpg"))
            if existing:
                stats["skipped_below_threshold"] += 1
                continue
        
        # Download and classify
        saved_path = download_and_classify(url, threshold=threshold, output_dir=output_path)
        
        if saved_path:
            stats["downloaded"] += 1
            LOGGER.info(f"✅ [{stats['downloaded']}] Saved: {saved_path}")
        else:
            stats["skipped_below_threshold"] += 1
    
    # Summary
    LOGGER.info("\n" + "=" * 60)
    LOGGER.info("✅ Download Complete")
    LOGGER.info("=" * 60)
    LOGGER.info(f"Total avatars processed: {len(avatar_urls)}")
    LOGGER.info(f"Bot candidates found:    {stats['downloaded']}")
    LOGGER.info(f"Below threshold:         {stats['skipped_below_threshold']}")
    LOGGER.info(f"Failed:                  {stats['failed']}")
    LOGGER.info("=" * 60)
    LOGGER.info(f"\n📁 Bot candidates saved to: {output_path}")
    LOGGER.info("\nNext steps:")
    LOGGER.info("1. Review images in bot_candidates/ folder")
    LOGGER.info("2. Move confirmed bots to: data/datasets/avatar_images/train/bot/")
    LOGGER.info("3. Move false positives to: data/datasets/avatar_images/train/human/")
    LOGGER.info("4. Retrain model with new data")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download and filter bot candidate avatars using MobileNet"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Max number of comment JSON files to process (default: 1000)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Bot probability threshold 0.0-1.0 (default: 0.3 for high recall)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for bot candidates"
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Scrape from video page instead of using GCS comments"
    )
    parser.add_argument(
        "--video-id",
        type=str,
        help="YouTube video ID to scrape (required with --use-playwright)"
    )
    
    args = parser.parse_args()
    
    main(
        limit=args.limit,
        threshold=args.threshold,
        output_dir=args.output_dir,
        use_playwright=args.use_playwright,
        video_id=args.video_id
    )
