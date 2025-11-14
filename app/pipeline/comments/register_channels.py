"""Register commenter channels from comment JSONs in GCS.

Features:
- Manifest-based resumability (GCS manifest: completed & in_progress)
- Streaming parse of large JSONs using ijson (low memory)
- Sequential processing with single Playwright browser
- Batched Firestore commits (default 100)
- Avatar classification and bot detection
- About page scraping for external links and featured channels
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Set, List

import ijson
from google.cloud import firestore, storage

from app.utils.image_processing import classify_avatar_url, get_xgb_model
from app.utils.manifest_utils import ManifestManager
from app.pipeline.channels.scraping import PlaywrightContext, scrape_about_page, expand_bot_graph_async

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

COLLECTION_NAME = "channel"


# ============================================================================
# Storage Client Helper
# ============================================================================

def _storage_client() -> storage.Client:
    """Get Google Cloud Storage client.
    
    Returns:
        Initialized storage client
    """
    return storage.Client()


# ============================================================================
# Comment Parsing
# ============================================================================

def _iter_comment_items_from_gcs(bucket: str, blob_path: str):
    """Incrementally yield comment thread items from a GCS JSON file.
    
    Uses ijson to avoid loading the full JSON into memory. Yields each item
    in the top-level 'items' array of a commentThreads response.
    
    Args:
        bucket: GCS bucket name
        blob_path: Path to comment JSON file in bucket
        
    Yields:
        Individual comment thread objects from the 'items' array
    """
    client = _storage_client()
    blob = client.bucket(bucket).blob(blob_path)
    with blob.open("rb") as f:
        for obj in ijson.items(f, "items.item"):
            yield obj


# ============================================================================
# Firestore Batching
# ============================================================================

class _Batcher:
    """Async-friendly Firestore batcher with automatic commits.
    
    Batches Firestore write operations and commits them when the batch
    size is reached. Thread-safe for async usage.
    """
    
    def __init__(self, client: firestore.Client, batch_size: int = 100) -> None:
        """Initialize the batcher.
        
        Args:
            client: Firestore client instance
            batch_size: Number of operations before auto-commit
        """
        self.client = client
        self.batch_size = batch_size
        self._batch = self.client.batch()
        self._count = 0
        self._lock = asyncio.Lock()

    async def set(self, doc_ref, data: dict, merge: bool = False) -> None:
        """Add a set operation to the batch.
        
        Args:
            doc_ref: Firestore document reference
            data: Data to set
            merge: Whether to merge with existing data
        """
        async with self._lock:
            self._batch.set(doc_ref, data, merge=merge)
            self._count += 1
            if self._count >= self.batch_size:
                await self._commit_locked()

    async def _commit_locked(self) -> None:
        """Commit the current batch (must hold lock).
        
        Creates a new batch for subsequent operations.
        """
        batch = self._batch
        self._batch = self.client.batch()
        self._count = 0
        await asyncio.to_thread(batch.commit)

    async def flush(self) -> None:
        """Flush any remaining operations in the batch."""
        async with self._lock:
            if self._count > 0:
                await self._commit_locked()


# ============================================================================
# Data Extraction Helpers
# ============================================================================

def _extract_channel_id_from_thread(thread: dict) -> Optional[str]:
    """Extract commenter channel ID from comment thread.
    
    Args:
        thread: Comment thread object from YouTube API
        
    Returns:
        Channel ID or None if not found
    """
    try:
        return thread["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"]
    except Exception:
        return None


def _extract_like_count_from_thread(thread: dict) -> int:
    """Extract like count from comment thread.
    
    Args:
        thread: Comment thread object from YouTube API
        
    Returns:
        Like count (defaults to 0 if not found)
    """
    try:
        return int(thread["snippet"]["topLevelComment"]["snippet"].get("likeCount", 0))
    except Exception:
        return 0


# ============================================================================
# Channel Expansion for Pending Review
# ============================================================================

async def expand_channels_for_review(
    channel_ids: List[str],
    *,
    use_api: bool = True
) -> None:
    """Expand channels discovered via comments for manual review.
    
    Expands channels with is_bot=False and bot_check_type="pending_review",
    preserving full metadata (avatars, banners, screenshots, About page links)
    before manual review determines if they are bots.
    
    This prevents data loss if channels are deleted/suspended before review.
    
    Args:
        channel_ids: List of channel IDs to expand
        use_api: Whether to use YouTube Data API for metadata (default: True)
    """
    if not channel_ids:
        LOGGER.info("No channels to expand for review")
        return
    
    LOGGER.info(f"🔍 Expanding {len(channel_ids)} channels for manual review")
    
    await expand_bot_graph_async(
        seed_channels=channel_ids,
        use_api=use_api,
        is_bot=False,
        bot_check_type="pending_review"
    )
    
    LOGGER.info(f"✅ Expansion complete. Channels ready for review.")


# ============================================================================
# Main Registration Function
# ============================================================================

async def register_commenter_channels(
    bucket: str,
    gcs_paths: List[str],
    *,
    limit_files: Optional[int] = None,
    like_threshold: int = 10,
    manifest_path: str = "manifests/register_commenters/manifest.json",
    force: bool = False,
    resume: bool = True,
    expand_for_review: bool = True,
    use_api_for_expansion: bool = True,
) -> None:
    """Register commenter channels from GCS comment JSON files.
    
    Sequential processing of comment files using a single Playwright browser.
    Extracts channels from comments, classifies avatars, scrapes About pages,
    and registers channels in Firestore.
    
    Args:
        bucket: GCS bucket name
        gcs_paths: List of paths to comment JSON files
        limit_files: Maximum number of files to process (None = all)
        like_threshold: Minimum likes required to include a commenter
        manifest_path: Path to manifest file for tracking progress
        force: If True, reprocess completed files
        resume: If True, skip files marked as completed in manifest
        expand_for_review: If True, expand discovered channels for manual review
        use_api_for_expansion: If True, use YouTube API during expansion
    """
    db = firestore.Client()
    model = get_xgb_model()

    # Use ManifestManager instead of manual manifest functions
    manifest_manager = ManifestManager(bucket=bucket, manifest_path=manifest_path)
    
    if force:
        manifest_manager.reset()
    
    completed = set(manifest_manager.get_completed()) if resume else set()
    remaining = [p for p in gcs_paths if (force or p not in completed)]
    if limit_files is not None:
        remaining = remaining[: max(0, limit_files)]

    LOGGER.info(
        "🧭 Files to process: %d (completed skipped: %d, force=%s, resume=%s)",
        len(remaining), len(completed), force, resume
    )

    total_new = 0
    seen_this_run: Set[str] = set()
    new_channels: List[str] = []  # Track newly added channels for expansion
    batcher = _Batcher(db, batch_size=100)

    async with PlaywrightContext() as context:
        for idx, gcs_path in enumerate(remaining, start=1):
            LOGGER.info(f"📥 [{idx}/{len(remaining)}] Processing file: {gcs_path}")
            manifest_manager.mark_in_progress(gcs_path)

            for thread in _iter_comment_items_from_gcs(bucket, gcs_path):
                cid = _extract_channel_id_from_thread(thread)
                if not cid:
                    continue
                if _extract_like_count_from_thread(thread) < like_threshold:
                    continue
                if cid in seen_this_run:
                    continue
                seen_this_run.add(cid)

                doc_ref = db.collection(COLLECTION_NAME).document(cid)
                LOGGER.info(f"🔍 Checking if {cid} already exists in Firestore...")
                exists = await asyncio.to_thread(lambda: doc_ref.get().exists)
                if exists:
                    LOGGER.info(f"⏭️ Skipping {cid} - already exists")
                    continue

                LOGGER.info(f"🆕 Processing new channel {cid}")
                avatar_url = (
                    thread.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                    .get("authorProfileImageUrl")
                )

                label, metrics = "MISSING", {}
                if avatar_url:
                    try:
                        LOGGER.info(f"🖼️ Classifying avatar for {cid}...")
                        label, metrics = classify_avatar_url(avatar_url, size=128, model=model)
                        if label == "DEFAULT":
                            LOGGER.info(f"🚫 Skipping default avatar {cid}")
                            continue
                        LOGGER.info(f"✅ Avatar classified as {label} for {cid}")
                    except Exception as e:
                        LOGGER.warning(f"⚠️ Avatar classification failed for {cid}: {e}")

                try:
                    LOGGER.info(f"🌐 Scraping About page for {cid}...")
                    about_links, subs = await scrape_about_page(context, cid)
                    LOGGER.info(f"📊 Found {len(about_links)} links and {len(subs)} subs for {cid}")
                except Exception as e:
                    LOGGER.warning(f"⚠️ scrape_about_page failed for {cid}: {e}")
                    about_links, subs = [], []
                    await asyncio.sleep(1)

                if not about_links and not subs:
                    LOGGER.info(f"⏭️ Skipping {cid} - no links or subs found")
                    continue

                LOGGER.info(f"💾 Saving {cid} to Firestore...")
                data = {
                    "channel_id": cid,
                    "avatar_url": avatar_url,
                    "avatar_label": label,
                    "avatar_metrics": metrics,
                    "about_links_count": len(about_links),
                    "featured_channels_count": len(subs),
                    "is_screenshot_stored": False,
                    "is_bot_checked": False,
                    "registered_at": datetime.now(),
                    "source": "register-commenters",
                }
                await batcher.set(doc_ref, data, merge=True)
                new_channels.append(cid)  # Track for expansion
                LOGGER.info(f"✅ Successfully registered {cid}")
                total_new += 1
                LOGGER.info(f"✅ Added {cid}")

            manifest_manager.mark_completed(gcs_path)
            LOGGER.info(f"✅ Completed file: {gcs_path}")

    await batcher.flush()
    LOGGER.info(f"🎉 Done! New channels this run: {total_new}")
    
    # Expand newly discovered channels for manual review
    if expand_for_review and new_channels:
        LOGGER.info(f"🔍 Starting expansion for {len(new_channels)} newly discovered channels...")
        await expand_channels_for_review(
            channel_ids=new_channels,
            use_api=use_api_for_expansion
        )


async def _init_channel_doc(
    context: PlaywrightContext,
    batch,
    db: firestore.Client,
    cid: str,
    avatar_url: Optional[str],
    model
) -> bool:
    """Initialize a channel document with avatar classification and About page data.
    
    Helper function for processing individual channels (legacy, kept for compatibility).
    
    Args:
        context: Playwright context for scraping
        batch: Firestore batch for writes
        db: Firestore client
        cid: Channel ID
        avatar_url: URL to channel avatar image
        model: XGBoost model for avatar classification
        
    Returns:
        True if channel was added, False if skipped
    """
    doc_ref = db.collection(COLLECTION_NAME).document(cid)
    if doc_ref.get().exists:
        return False

    # Process avatar
    label = "MISSING"
    metrics = {}
    if avatar_url:
        try:
            label, metrics = classify_avatar_url(avatar_url, size=128, model=model)
            if label == "DEFAULT":
                LOGGER.info(f"🚫 Skipping default avatar {cid}")
                return False
        except Exception as e:
            LOGGER.warning(f"⚠️ Avatar classification failed for {cid}: {e}")

    # Scrape links and featured channels
    about_links, subs = await scrape_about_page(context, cid)

    if not about_links and not subs:
        LOGGER.info(f"⏭️ Skipping https://www.youtube.com/channel/{cid} — no links or featured channels found")
        return False

    # Store channel
    batch.set(doc_ref, {
        "channel_id": cid,
        "avatar_url": avatar_url,
        "avatar_label": label,
        "avatar_metrics": metrics,
        "about_links_count": len(about_links),
        "featured_channels_count": len(subs),
        "is_screenshot_stored": False,
        "is_bot_checked": False,
        "registered_at": datetime.now(),
    })
    return True


def backfill_bot_probabilities(limit: int = 5000) -> None:
    """Recompute bot_probability for existing channels missing it.
    
    Backfills avatar metrics and bot probabilities for channels that
    were registered before the XGBoost model was available.
    
    Args:
        limit: Maximum number of channels to process
    """
    db = firestore.Client()
    model = get_xgb_model()
    snaps = db.collection(COLLECTION_NAME).limit(limit).stream()

    batch = db.batch()
    updated = 0

    for snap in snaps:
        doc = snap.to_dict() or {}
        metrics = doc.get("avatar_metrics", {})
        if not metrics or metrics.get("has_bot_probability"):
            continue

        avatar_url = doc.get("avatar_url")
        if not avatar_url:
            continue

        try:
            label, new_metrics = classify_avatar_url(avatar_url, size=128, model=model)
            metrics.update(new_metrics)
            metrics["has_bot_probability"] = True
            doc_ref = db.collection(COLLECTION_NAME).document(snap.id)
            batch.update(doc_ref, {"avatar_metrics": metrics, "avatar_label": label})
            updated += 1

            if updated % 100 == 0:
                batch.commit()
                batch = db.batch()
                LOGGER.info(f"✅ Updated {updated} so far...")
        except Exception as e:
            LOGGER.warning(f"⚠️ Failed to backfill {snap.id}: {e}")

    if updated:
        batch.commit()
    LOGGER.info(f"🎉 Backfill finished: {updated} channels updated with bot_probability")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Register commenter channels or backfill bot probabilities"
    )
    parser.add_argument("--bucket", help="GCS bucket name")
    parser.add_argument("--gcs_paths", nargs="*", help="Paths to video_comments/raw/*.json")
    parser.add_argument("--backfill", action="store_true", help="Run in backfill mode")

    args = parser.parse_args()

    if args.backfill:
        backfill_bot_probabilities()
    else:
        if not args.bucket or not args.gcs_paths:
            raise SystemExit("❌ Need --bucket and --gcs_paths unless --backfill is used")
        asyncio.run(register_commenter_channels(args.bucket, args.gcs_paths))

