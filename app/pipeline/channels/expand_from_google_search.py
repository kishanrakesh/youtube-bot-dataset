#!/usr/bin/env python3
"""Expand bot graph by searching Google Custom Search for related YouTube channels.

This pipeline:
1. Fetches confirmed bot channels from Firestore
2. For each bot channel, performs Google Custom Search queries to find related channels
3. Validates that discovered channels still exist on YouTube
4. Expands the bot graph for valid channels
5. Marks discovered channels as "pending_review" until manual review
"""

import argparse
import asyncio
import logging
import os
import re
from typing import List, Set, Optional
from datetime import datetime

import requests
from dotenv import load_dotenv
from google.cloud import firestore
from googleapiclient.errors import HttpError

from app.pipeline.channels.scraping import expand_bot_graph_async, fetch_channel_item
from app.utils.clients import get_youtube

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

# Google Custom Search API configuration
# Set these in your .env file:
#   GOOGLE_CSE_API_KEY=your-api-key-here
#   GOOGLE_CSE_ID=your-search-engine-id-here
GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")

db = firestore.Client()


def fetch_bot_channels(
    limit: Optional[int] = None,
    is_bot_checked: bool = True
) -> List[dict]:
    """Fetch confirmed bot channels from Firestore.

    Args:
        limit: Maximum number of channels to fetch (None for all)
        is_bot_checked: Only fetch manually reviewed bot channels

    Returns:
        List of channel documents with metadata
    """
    LOGGER.info(f"�� Fetching bot channels (is_bot_checked={is_bot_checked})...")

    # Query for confirmed bots
    query = db.collection("channel").where("is_bot", "==", True)

    if is_bot_checked:
        query = query.where("is_bot_checked", "==", True)

    if limit:
        query = query.limit(limit)

    docs = list(query.stream())

    # Extract channel info
    channels = []
    for doc in docs:
        data = doc.to_dict() or {}
        metrics = data.get("avatar_metrics", {})
        bot_prob = metrics.get("bot_probability", 0.0)

        # Get handle from channel_data.snippet.customUrl, snippet.customUrl, or custom_url
        custom_url = data.get("custom_url", "")
        snippet = data.get("snippet", {})
        channel_data = data.get("channel_data", {})
        channel_data_snippet = channel_data.get("snippet", {}) if isinstance(channel_data, dict) else {}

        # Try multiple locations for the handle
        handle = (
            channel_data_snippet.get("customUrl", "") or  # channel_data.snippet.customUrl
            snippet.get("customUrl", "") or                # snippet.customUrl
            custom_url                                      # custom_url
        )

        # Ensure handle starts with @
        if handle and not handle.startswith("@"):
            handle = f"@{handle}"

        channels.append({
            "channel_id": doc.id,
            "bot_probability": bot_prob,
            "avatar_label": data.get("avatar_label", "UNKNOWN"),
            "title": data.get("title", ""),
            "custom_url": custom_url,
            "handle": handle,
        })

    LOGGER.info(f"✅ Found {len(channels)} bot channels")
    return channels


def google_custom_search(
    query: str,
    site_search: str = "youtube.com",
    num_results: int = 10
) -> List[str]:
    """Perform Google Custom Search to find YouTube channels.

    Args:
        query: Search query string
        site_search: Site to restrict search to
        num_results: Maximum number of results to return

    Returns:
        List of YouTube channel URLs found
    """
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_ID:
        LOGGER.error("❌ Google Custom Search API credentials not configured")
        LOGGER.error("   Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID environment variables")
        return []

    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_CSE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "siteSearch": site_search,
            "num": min(num_results, 10),  # API max is 10 per request
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        items = data.get("items", [])

        urls = []
        for item in items:
            link = item.get("link", "")
            if link:
                urls.append(link)

        LOGGER.info(f"🔍 Found {len(urls)} results for query: {query}")
        return urls

    except requests.RequestException as e:
        LOGGER.error(f"❌ Google Custom Search failed: {e}")
        return []
    except Exception as e:
        LOGGER.exception(f"💥 Unexpected error in Google Custom Search: {e}")
        return []


def extract_channel_ids_from_urls(urls: List[str]) -> Set[str]:
    """Extract channel IDs and handles from YouTube URLs.

    Supports formats:
    - youtube.com/channel/UC...
    - youtube.com/@handle

    Args:
        urls: List of YouTube URLs

    Returns:
        Set of channel IDs (UC...) and handles (@...)
    """
    identifiers = set()

    # Regex patterns for channel URLs
    channel_id_pattern = re.compile(r"youtube\.com/channel/(UC[a-zA-Z0-9_-]+)")
    handle_pattern = re.compile(r"youtube\.com/@([a-zA-Z0-9_.-]+)")

    for url in urls:
        # Extract channel ID
        match = channel_id_pattern.search(url)
        if match:
            identifiers.add(match.group(1))
            continue

        # Extract handle
        match = handle_pattern.search(url)
        if match:
            identifiers.add(f"@{match.group(1)}")
            continue

    return identifiers


def validate_channel_exists(youtube, identifier: str) -> Optional[str]:
    """Check if a channel still exists on YouTube.

    Args:
        youtube: YouTube API client
        identifier: Channel ID or handle

    Returns:
        Channel ID if exists, None otherwise
    """
    try:
        channel_item = fetch_channel_item(youtube, identifier)
        if channel_item:
            channel_id = channel_item.get("id")
            LOGGER.info(f"✅ Channel {identifier} exists: {channel_id}")
            return channel_id
        else:
            LOGGER.warning(f"⚠️ Channel {identifier} not found or inaccessible")
            return None
    except Exception as e:
        LOGGER.warning(f"⚠️ Error validating channel {identifier}: {e}")
        return None


def search_related_channels(
    bot_channel_id: str,
    bot_handle: str = "",
    bot_title: str = "",
    search_patterns: Optional[List[str]] = None,
    max_results_per_query: int = 10
) -> Set[str]:
    """Search for channels related to a bot channel using Google Custom Search.

    Args:
        bot_channel_id: The bot channel ID
        bot_handle: The bot channel handle (e.g., @username)
        bot_title: Bot channel title (if available)
        search_patterns: Custom search query patterns
        max_results_per_query: Maximum results per search query

    Returns:
        Set of discovered channel identifiers (IDs and handles)
    """
    all_identifiers = set()

    # Default search patterns - search for handle appearing anywhere on YouTube pages
    # Since CSE is already restricted to youtube.com, just search for the handle text
    if search_patterns is None:
        search_patterns = [
            bot_handle if bot_handle else None,
            f"\"{bot_title}\"" if bot_title else None,
        ]

    # Filter out None patterns
    search_patterns = [p for p in search_patterns if p]

    for pattern in search_patterns:
        LOGGER.info(f"🔍 Searching: {pattern}")
        urls = google_custom_search(pattern, num_results=max_results_per_query)
        identifiers = extract_channel_ids_from_urls(urls)
        all_identifiers.update(identifiers)

    # Remove the original bot channel if found
    all_identifiers.discard(bot_channel_id)
    if bot_handle:
        all_identifiers.discard(bot_handle)

    return all_identifiers


async def expand_bot_graph_from_search(
    bot_channels: List[dict],
    use_api: bool = True,
    max_results_per_channel: int = 10,
    validate_channels: bool = True,
    dry_run: bool = False
) -> None:
    """Expand bot graph by searching for related channels via Google Custom Search.

    Args:
        bot_channels: List of bot channel documents to search from
        use_api: Whether to use YouTube API for validation and expansion
        max_results_per_channel: Maximum search results per bot channel
        validate_channels: Validate channels exist before expanding
        dry_run: If True, don't actually expand the graph, just report findings
    """
    youtube = get_youtube() if use_api else None

    total_discovered = 0
    total_validated = 0
    total_expanded = 0

    for i, bot_channel in enumerate(bot_channels, 1):
        channel_id = bot_channel["channel_id"]
        handle = bot_channel.get("handle", "")
        title = bot_channel.get("title", "")
        bot_prob = bot_channel.get("bot_probability", 0.0)

        LOGGER.info(f"\n{'='*80}")
        LOGGER.info(f"[{i}/{len(bot_channels)}] Processing bot channel: {channel_id}")
        LOGGER.info(f"   Handle: {handle}")
        LOGGER.info(f"   Title: {title}")
        LOGGER.info(f"   Bot Probability: {bot_prob:.4f}")
        LOGGER.info(f"{'='*80}")

        # Search for related channels
        discovered = search_related_channels(
            bot_channel_id=channel_id,
            bot_handle=handle,
            bot_title=title,
            max_results_per_query=max_results_per_channel
        )

        if not discovered:
            LOGGER.info("   No related channels found")
            continue

        LOGGER.info(f"   Found {len(discovered)} potential channels")
        total_discovered += len(discovered)

        # Validate and expand
        valid_channels = []
        for identifier in discovered:
            if validate_channels and youtube:
                validated_id = validate_channel_exists(youtube, identifier)
                if validated_id:
                    valid_channels.append(validated_id)
                    total_validated += 1
            else:
                valid_channels.append(identifier)

        LOGGER.info(f"   Validated {len(valid_channels)} channels")

        if dry_run:
            LOGGER.info(f"   [DRY RUN] Would expand graph for: {valid_channels}")
            continue

        # Expand bot graph for valid channels
        if valid_channels:
            try:
                LOGGER.info(f"   🚀 Expanding graph for {len(valid_channels)} channels...")

                # Store discovery metadata
                for ch_id in valid_channels:
                    db.collection("channel_discoveries").add({
                        "discovered_from_channel_id": channel_id,
                        "discovered_channel_id": ch_id,
                        "discovery_method": "google_custom_search",
                        "discovered_at": datetime.now(),
                        "is_validated": validate_channels,
                    })

                # Expand the graph with "pending_review" status
                await expand_bot_graph_async(
                    seed_channels=valid_channels,
                    use_api=use_api,
                    is_bot=False,  # Mark as non-bot until reviewed
                    bot_check_type="pending_review"  # Needs manual review
                )

                total_expanded += len(valid_channels)
                LOGGER.info(f"   ✅ Expansion complete for {len(valid_channels)} channels")

            except Exception as e:
                LOGGER.exception(f"   💥 Error expanding graph: {e}")

    # Summary
    LOGGER.info(f"\n{'='*80}")
    LOGGER.info("📊 Expansion Summary")
    LOGGER.info(f"{'='*80}")
    LOGGER.info(f"Bot channels processed: {len(bot_channels)}")
    LOGGER.info(f"Total channels discovered: {total_discovered}")
    LOGGER.info(f"Total channels validated: {total_validated}")
    LOGGER.info(f"Total channels expanded: {total_expanded}")
    LOGGER.info(f"{'='*80}\n")


def main(
    limit: Optional[int] = 10,
    max_results_per_channel: int = 10,
    use_api: bool = True,
    validate: bool = True,
    dry_run: bool = False
) -> None:
    """Main entrypoint for expanding bot graph from Google Custom Search.

    Args:
        limit: Maximum number of bot channels to process
        max_results_per_channel: Maximum search results per bot channel
        use_api: Use YouTube API for validation and expansion
        validate: Validate channels exist before expanding
        dry_run: Don't actually expand, just report findings
    """
    # Fetch bot channels
    bot_channels = fetch_bot_channels(
        limit=limit,
        is_bot_checked=True
    )

    if not bot_channels:
        LOGGER.error("❌ No bot channels found matching criteria")
        return

    # Run expansion
    asyncio.run(expand_bot_graph_from_search(
        bot_channels=bot_channels,
        use_api=use_api,
        max_results_per_channel=max_results_per_channel,
        validate_channels=validate,
        dry_run=dry_run
    ))


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Expand bot graph using Google Custom Search",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of bot channels to process"
    )
    parser.add_argument(
        "--max-results-per-channel",
        type=int,
        default=10,
        help="Maximum search results per bot channel"
    )
    parser.add_argument(
        "--use-api",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use YouTube Data API for validation and expansion"
    )
    parser.add_argument(
        "--validate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Validate channels exist before expanding"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually expand, just report findings"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(
        limit=args.limit,
        max_results_per_channel=args.max_results_per_channel,
        use_api=args.use_api,
        validate=args.validate,
        dry_run=args.dry_run
    )
