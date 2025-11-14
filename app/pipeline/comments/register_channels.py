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
import json
import logging
from datetime import datetime
from typing import Optional, Set, List

import ijson
from google.cloud import firestore, storage

from app.utils.image_processing import classify_avatar_url, get_xgb_model
from app.pipeline.channels.scraping import PlaywrightContext, scrape_about_page

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

COLLECTION_NAME = "channel"


# ============================================================================
# Manifest Helpers
# ============================================================================

def _storage_client() -> storage.Client:
    """Get Google Cloud Storage client.
    
    Returns:
        Initialized storage client
    """
    return storage.Client()


def _manifest_load(bucket: str, manifest_path: str) -> dict:
    """Load manifest JSON from GCS or return default structure.
    
    Args:
        bucket: GCS bucket name
        manifest_path: Path to manifest file in bucket
        
    Returns:
        Manifest dictionary with completed, in_progress, and last_run fields
    """
    client = _storage_client()
    blob = client.bucket(bucket).blob(manifest_path)
    if not blob.exists():
        return {"completed": [], "in_progress": None, "last_run": None}
    try:
        return json.loads(blob.download_as_bytes())
    except Exception:
        return {"completed": [], "in_progress": None, "last_run": None}


def _manifest_save(bucket: str, manifest_path: str, manifest: dict) -> None:
    """Save manifest JSON to GCS with updated timestamp.
    
    Args:
        bucket: GCS bucket name
        manifest_path: Path to manifest file in bucket
        manifest: Manifest dictionary to save
    """
    client = _storage_client()
    blob = client.bucket(bucket).blob(manifest_path)
    manifest["last_run"] = datetime.now().isoformat(timespec="seconds") + "Z"
    blob.upload_from_string(json.dumps(manifest, ensure_ascii=False))


def _manifest_mark_in_progress(bucket: str, manifest_path: str, gcs_path: str) -> None:
    """Mark a file as currently being processed in the manifest.
    
    Args:
        bucket: GCS bucket name
        manifest_path: Path to manifest file in bucket
        gcs_path: Path to file being processed
    """
    m = _manifest_load(bucket, manifest_path)
    m["in_progress"] = gcs_path
    _manifest_save(bucket, manifest_path, m)


def _manifest_mark_completed(bucket: str, manifest_path: str, gcs_path: str) -> None:
    """Mark a file as completed in the manifest.
    
    Args:
        bucket: GCS bucket name
        manifest_path: Path to manifest file in bucket
        gcs_path: Path to completed file
    """
    m = _manifest_load(bucket, manifest_path)
    if gcs_path not in m.get("completed", []):
        m.setdefault("completed", []).append(gcs_path)
    m["in_progress"] = None
    _manifest_save(bucket, manifest_path, m)


# ============================================================================
# Streaming JSON Parser
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
    """
    db = firestore.Client()
    model = get_xgb_model()

    manifest = _manifest_load(bucket, manifest_path) if (resume and not force) else {"completed": [], "in_progress": None}
    completed = set(manifest.get("completed", []))
    remaining = [p for p in gcs_paths if (force or p not in completed)]
    if limit_files is not None:
        remaining = remaining[: max(0, limit_files)]

    LOGGER.info(
        "🧭 Files to process: %d (completed skipped: %d, force=%s, resume=%s)",
        len(remaining), len(completed), force, resume
    )

    total_new = 0
    seen_this_run: Set[str] = set()
    batcher = _Batcher(db, batch_size=100)

    async with PlaywrightContext() as context:
        for idx, gcs_path in enumerate(remaining, start=1):
            LOGGER.info(f"📥 [{idx}/{len(remaining)}] Processing file: {gcs_path}")
            _manifest_mark_in_progress(bucket, manifest_path, gcs_path)

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
                exists = await asyncio.to_thread(lambda: doc_ref.get().exists)
                if exists:
                    continue

                avatar_url = (
                    thread.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                    .get("authorProfileImageUrl")
                )

                label, metrics = "MISSING", {}
                if avatar_url:
                    try:
                        label, metrics = classify_avatar_url(avatar_url, size=128, model=model)
                        if label == "DEFAULT":
                            LOGGER.info(f"🚫 Skipping default avatar {cid}")
                            continue
                    except Exception as e:
                        LOGGER.warning(f"⚠️ Avatar classification failed for {cid}: {e}")

                try:
                    about_links, subs = await asyncio.wait_for(
                        scrape_about_page(context, cid),
                        timeout=20
                    )
                except asyncio.TimeoutError:
                    LOGGER.warning(f"⏰ scrape_about_page timeout for {cid}")
                    about_links, subs = [], []
                except Exception as e:
                    LOGGER.warning(f"⚠️ scrape_about_page failed for {cid}: {e}")
                    about_links, subs = [], []

                if not about_links and not subs:
                    continue

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
                total_new += 1
                LOGGER.info(f"✅ Added {cid}")

            _manifest_mark_completed(bucket, manifest_path, gcs_path)
            LOGGER.info(f"✅ Completed file: {gcs_path}")

    await batcher.flush()
    LOGGER.info(f"🎉 Done! New channels this run: {total_new}")


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

