#!/usr/bin/env python3
"""
Analyze comments from bot channels.

This script:
1. Fetches all channels from Firestore marked as bots or with high bot probability
2. Fetches comment JSONs from GCS
3. Counts how many comments were made by bot channels
4. Provides detailed statistics and breakdown

Usage:
    # Analyze all comments
    python scripts/analyze_bot_comments.py
    
    # Only check channels with >80% bot probability
    python scripts/analyze_bot_comments.py --min-bot-prob 0.8
    
    # Limit number of comment files to analyze
    python scripts/analyze_bot_comments.py --limit 500
    
    # Export detailed results to CSV
    python scripts/analyze_bot_comments.py --export bot_comment_analysis.csv
"""

import argparse
import csv
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

from google.cloud import firestore, storage

# ───── Configuration ─────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
LOGGER = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("DATASET_BUCKET", "yt-bot-data")
COMMENTS_PREFIX = "youtube-bot-dataset/video_comments/raw/"


# ───── Firestore & GCS Clients ─────
_db: firestore.Client | None = None
_storage: storage.Client | None = None


def db() -> firestore.Client:
    """Get or create Firestore client."""
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def storage_client() -> storage.Client:
    """Get or create GCS client."""
    global _storage
    if _storage is None:
        _storage = storage.Client()
    return _storage


def bucket() -> storage.Bucket:
    """Get GCS bucket."""
    return storage_client().bucket(BUCKET_NAME)


# ───── Fetch Bot Channels ─────
def fetch_bot_channels(min_bot_prob: float = 0.5, use_is_bot: bool = False) -> Dict[str, dict]:
    """Fetch all channels marked as bots from Firestore.
    
    Args:
        min_bot_prob: Minimum bot probability threshold (0.0-1.0)
        use_is_bot: If True, use is_bot field instead of bot_probability
        
    Returns:
        Dict mapping channel_id to channel data
    """
    channels_ref = db().collection("channel")  # Note: singular "channel"
    
    bot_channels = {}
    count = 0
    
    if use_is_bot:
        LOGGER.info(f"Fetching bot channels (is_bot=True)...")
        # Query channels with is_bot == True
        query = channels_ref.where("is_bot", "==", True)
        
        for doc in query.stream():
            data = doc.to_dict()
            channel_id = doc.id
            bot_channels[channel_id] = {
                "channel_id": channel_id,
                "title": data.get("title", "Unknown"),
                "bot_probability": data.get("bot_probability", 1.0),
                "is_bot": data.get("is_bot", True),
                "avatar_label": data.get("avatar_label", "UNKNOWN"),
                "subscriber_count": data.get("subscriber_count", 0),
                "video_count": data.get("video_count", 0),
            }
            count += 1
            
            if count % 100 == 0:
                LOGGER.info(f"  Loaded {count} bot channels...")
    else:
        LOGGER.info(f"Fetching bot channels (min_prob={min_bot_prob})...")
        # Query channels with bot probability >= threshold
        query = channels_ref.where("bot_probability", ">=", min_bot_prob)
        
        for doc in query.stream():
            data = doc.to_dict()
            channel_id = doc.id
            bot_channels[channel_id] = {
                "channel_id": channel_id,
                "title": data.get("title", "Unknown"),
                "bot_probability": data.get("bot_probability", 0.0),
                "is_bot": data.get("is_bot", False),
                "avatar_label": data.get("avatar_label", "UNKNOWN"),
                "subscriber_count": data.get("subscriber_count", 0),
                "video_count": data.get("video_count", 0),
            }
            count += 1
            
            if count % 100 == 0:
                LOGGER.info(f"  Loaded {count} bot channels...")
    
    LOGGER.info(f"✅ Found {len(bot_channels)} bot channels")
    return bot_channels


# ───── Parse Comments from GCS ─────
def extract_comment_authors_from_json(json_data: dict, top_level_only: bool = True) -> List[str]:
    """Extract author channel IDs from a comment thread JSON.
    
    Args:
        json_data: Comment thread JSON from YouTube API
        top_level_only: If True, only extract top-level comments (ignore replies)
        
    Returns:
        List of author channel IDs
    """
    author_ids = []
    
    try:
        items = json_data.get("items", [])
        for item in items:
            # Top-level comment
            top_comment = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            channel_id = top_comment.get("authorChannelId", {}).get("value")
            
            if channel_id:
                author_ids.append(channel_id)
            
            # Skip replies if top_level_only is True
            if not top_level_only:
                # Replies
                replies = item.get("replies", {}).get("comments", [])
                for reply in replies:
                    reply_snippet = reply.get("snippet", {})
                    channel_id = reply_snippet.get("authorChannelId", {}).get("value")
                    
                    if channel_id:
                        author_ids.append(channel_id)
    except Exception as e:
        LOGGER.warning(f"Error extracting authors from JSON: {e}")
    
    return author_ids


def analyze_comments_from_gcs(
    bot_channel_ids: Set[str],
    limit: int = None
) -> Dict[str, any]:
    """Analyze comments from GCS to count bot comments.
    
    Args:
        bot_channel_ids: Set of bot channel IDs
        limit: Maximum number of comment files to process (None = all)
        
    Returns:
        Dict with analysis results
    """
    LOGGER.info(f"Analyzing comments from GCS (bucket={BUCKET_NAME}, prefix={COMMENTS_PREFIX})...")
    
    # List all comment JSON files
    blobs = bucket().list_blobs(prefix=COMMENTS_PREFIX)
    
    stats = {
        "total_files": 0,
        "total_comments": 0,
        "bot_comments": 0,
        "human_comments": 0,
        "unique_bot_commenters": set(),  # Set of unique bot channel IDs
        "bot_commenters": defaultdict(int),  # channel_id -> comment_count
        "videos_with_bot_comments": set(),
        "files_processed": [],
    }
    
    for blob in blobs:
        if not blob.name.endswith('.json'):
            continue
        
        # Check limit
        if limit and stats["total_files"] >= limit:
            LOGGER.info(f"Reached limit of {limit} files")
            break
        
        stats["total_files"] += 1
        
        try:
            # Download and parse JSON
            content = blob.download_as_text()
            data = json.loads(content)
            
            # Extract video ID from filename or data
            video_id = data.get("video_id") or blob.name.split("/")[-1].replace(".json", "")
            
            # Get all comment authors (top-level only)
            author_ids = extract_comment_authors_from_json(data, top_level_only=True)
            stats["total_comments"] += len(author_ids)
            
            # Count bot vs human comments
            has_bot_comment = False
            for author_id in author_ids:
                if author_id in bot_channel_ids:
                    stats["bot_comments"] += 1
                    stats["unique_bot_commenters"].add(author_id)
                    stats["bot_commenters"][author_id] += 1
                    has_bot_comment = True
                else:
                    stats["human_comments"] += 1
            
            if has_bot_comment:
                stats["videos_with_bot_comments"].add(video_id)
            
            stats["files_processed"].append(blob.name)
            
            # Progress logging
            if stats["total_files"] % 50 == 0:
                LOGGER.info(
                    f"  Processed {stats['total_files']} files | "
                    f"Comments: {stats['total_comments']:,} | "
                    f"Bot: {stats['bot_comments']:,} ({stats['bot_comments']/max(stats['total_comments'],1)*100:.1f}%)"
                )
        
        except Exception as e:
            LOGGER.warning(f"Failed to process {blob.name}: {e}")
            continue
    
    # Convert sets to counts for final report
    stats["videos_with_bot_comments"] = len(stats["videos_with_bot_comments"])
    stats["unique_bot_commenters"] = len(stats["unique_bot_commenters"])
    
    return stats


def analyze_comments_from_firestore(
    bot_channel_ids: Set[str],
    limit: int = None
) -> Dict[str, any]:
    """Analyze comments from Firestore to count bot comments.
    
    Args:
        bot_channel_ids: Set of bot channel IDs
        limit: Maximum number of comment documents to process (None = all)
        
    Returns:
        Dict with analysis results
    """
    LOGGER.info(f"Analyzing comments from Firestore...")
    
    # Query comments collection
    comments_ref = db().collection("channel_video_comment")  # Or "comments" depending on schema
    
    stats = {
        "total_documents": 0,
        "total_comments": 0,
        "bot_comments": 0,
        "human_comments": 0,
        "bot_commenters": defaultdict(int),  # channel_id -> comment_count
        "videos_with_bot_comments": set(),
        "documents_processed": [],
    }
    
    # Stream documents
    query = comments_ref
    if limit:
        query = query.limit(limit)
    
    for doc in query.stream():
        stats["total_documents"] += 1
        data = doc.to_dict()
        
        # Get author channel ID
        author_id = data.get("author_channel_id") or data.get("channel_id")
        video_id = data.get("video_id")
        
        if not author_id:
            continue
        
        stats["total_comments"] += 1
        
        # Check if bot
        if author_id in bot_channel_ids:
            stats["bot_comments"] += 1
            stats["bot_commenters"][author_id] += 1
            if video_id:
                stats["videos_with_bot_comments"].add(video_id)
        else:
            stats["human_comments"] += 1
        
        stats["documents_processed"].append(doc.id)
        
        # Progress logging
        if stats["total_documents"] % 1000 == 0:
            LOGGER.info(
                f"  Processed {stats['total_documents']:,} documents | "
                f"Comments: {stats['total_comments']:,} | "
                f"Bot: {stats['bot_comments']:,} ({stats['bot_comments']/max(stats['total_comments'],1)*100:.1f}%)"
            )
    
    # Convert sets to counts for final report
    stats["videos_with_bot_comments"] = len(stats["videos_with_bot_comments"])
    
    return stats


# ───── Reporting ─────
def print_analysis_report(
    stats: Dict[str, any],
    bot_channels: Dict[str, dict],
    top_n: int = 20
):
    """Print detailed analysis report.
    
    Args:
        stats: Analysis statistics
        bot_channels: Bot channel information
        top_n: Number of top commenters to show
    """
    print("\n" + "="*80)
    print("🤖 BOT COMMENT ANALYSIS REPORT")
    print("="*80)
    
    # Overall stats
    print(f"\n📊 OVERALL STATISTICS")
    print(f"  Comment files processed:    {stats['total_files']:,}")
    print(f"  Total comments analyzed:    {stats['total_comments']:,} (top-level only)")
    print(f"  Bot comments:               {stats['bot_comments']:,}")
    print(f"  Human comments:             {stats['human_comments']:,}")
    print(f"  Videos with bot comments:   {stats['videos_with_bot_comments']:,}")
    
    # Percentages
    if stats['total_comments'] > 0:
        bot_pct = stats['bot_comments'] / stats['total_comments'] * 100
        print(f"\n  Bot comment rate:           {bot_pct:.2f}%")
    
    # Bot channels that commented
    unique_bot_commenters = stats['unique_bot_commenters']
    total_bot_channels = len(bot_channels)
    print(f"\n  Unique bot commenters:      {unique_bot_commenters:,} of {total_bot_channels:,} known bots")
    
    if total_bot_channels > 0:
        activity_rate = unique_bot_commenters / total_bot_channels * 100
        print(f"  Bot activity rate:          {activity_rate:.2f}%")
    
    # Comments per bot
    if unique_bot_commenters > 0:
        avg_comments_per_bot = stats['bot_comments'] / unique_bot_commenters
        print(f"  Avg comments per bot:       {avg_comments_per_bot:.2f}")
    
    # Top bot commenters
    if stats['bot_commenters']:
        print(f"\n🏆 TOP {top_n} BOT COMMENTERS")
        print(f"{'Rank':<6} {'Channel ID':<26} {'Comments':<12} {'Bot Prob':<12} {'Title'}")
        print("-" * 80)
        
        sorted_bots = sorted(
            stats['bot_commenters'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        for rank, (channel_id, comment_count) in enumerate(sorted_bots, 1):
            bot_info = bot_channels.get(channel_id, {})
            bot_prob = bot_info.get("bot_probability", 0.0)
            title = bot_info.get("title", "Unknown")[:30]
            
            print(f"{rank:<6} {channel_id:<26} {comment_count:<12} {bot_prob:<12.3f} {title}")
    
    print("\n" + "="*80)


def export_to_csv(
    stats: Dict[str, any],
    bot_channels: Dict[str, dict],
    filepath: str
):
    """Export detailed bot commenter data to CSV.
    
    Args:
        stats: Analysis statistics
        bot_channels: Bot channel information
        filepath: Output CSV file path
    """
    LOGGER.info(f"Exporting to {filepath}...")
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'channel_id',
            'channel_title',
            'bot_probability',
            'avatar_label',
            'comment_count',
            'subscriber_count',
            'video_count'
        ])
        
        # Sort by comment count
        sorted_bots = sorted(
            stats['bot_commenters'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Write rows
        for channel_id, comment_count in sorted_bots:
            bot_info = bot_channels.get(channel_id, {})
            writer.writerow([
                channel_id,
                bot_info.get("title", "Unknown"),
                bot_info.get("bot_probability", 0.0),
                bot_info.get("avatar_label", "UNKNOWN"),
                comment_count,
                bot_info.get("subscriber_count", 0),
                bot_info.get("video_count", 0)
            ])
    
    LOGGER.info(f"✅ Exported {len(sorted_bots)} rows to {filepath}")


# ───── Main ─────
def main():
    parser = argparse.ArgumentParser(
        description="Analyze comments from bot channels",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--min-bot-prob",
        type=float,
        default=0.5,
        help="Minimum bot probability threshold (default: 0.5)"
    )
    parser.add_argument(
        "--use-is-bot",
        action="store_true",
        help="Use is_bot=True field instead of bot_probability threshold"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of comment files to process (default: all)"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of top bot commenters to display (default: 20)"
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Export detailed results to CSV file"
    )
    
    args = parser.parse_args()
    
    print("\n🤖 Bot Comment Analysis")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Fetch bot channels
    bot_channels = fetch_bot_channels(
        min_bot_prob=args.min_bot_prob,
        use_is_bot=args.use_is_bot
    )
    
    if not bot_channels:
        if args.use_is_bot:
            LOGGER.error("No bot channels found with is_bot=True. Check Firestore data.")
        else:
            LOGGER.error(f"No bot channels found with bot_probability>={args.min_bot_prob}. Try --use-is-bot or adjust threshold.")
        return
    
    bot_channel_ids = set(bot_channels.keys())
    
    # Analyze comments
    stats = analyze_comments_from_gcs(
        bot_channel_ids=bot_channel_ids,
        limit=args.limit
    )
    
    # Print report
    print_analysis_report(stats, bot_channels, top_n=args.top_n)
    
    # Export if requested
    if args.export:
        export_to_csv(stats, bot_channels, args.export)
    
    print(f"\n✅ Analysis complete at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    main()
