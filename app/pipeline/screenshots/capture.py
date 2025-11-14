#!/usr/bin/env python3
"""
Capture YouTube channel homepage screenshots using Playwright.

Flow:
- Query Firestore: channels with is_screenshot_stored == False
- Visit https://www.youtube.com/channel/{channel_id}
- Take full-page screenshot
- Upload to GCS: gs://<bucket>/channel_screenshots/raw/{channel_id}.png
- Update Firestore: {is_screenshot_stored=True, screenshot_gcs_uri=...}
"""

import argparse
import asyncio
import io
import logging
import os
import uuid
from datetime import datetime
from typing import List

from google.cloud import firestore, storage
from playwright.async_api import async_playwright

from app.pipeline.channels.scraping import PlaywrightContext, get_channel_url
from app.utils.gcs_utils import upload_png

# ───── config ─────
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

COLLECTION_NAME = "channel"
BUCKET_NAME = os.getenv("SCREENSHOT_BUCKET", "yt-bot-screens")
PAGE_TIMEOUT_MS = 25_000

# ───── GCP clients ─────
_db: firestore.Client | None = None
_storage: storage.Client | None = None


def db() -> firestore.Client:
    """Get or create Firestore client."""
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def bucket():
    """Get or create GCS bucket."""
    global _storage
    if _storage is None:
        _storage = storage.Client()
    return _storage.bucket(BUCKET_NAME)


def fetch_channels_needing_screenshots(limit: int) -> List[firestore.DocumentSnapshot]:
    """Fetch Firestore docs for channels missing screenshots."""
    query = (
        db().collection(COLLECTION_NAME)
        .where("is_screenshot_stored", "==", False)
        .limit(limit)
    )
    docs = list(query.stream())
    LOGGER.info(f"Fetched {len(docs)} channels needing screenshots")
    return docs


def upload_png(cid: str, png_bytes: bytes) -> str:
    """Upload PNG to GCS and return its URI."""
    path = f"channel_screenshots/raw/{cid}_{uuid.uuid4().hex}.png"
    blob = bucket().blob(path)
    blob.upload_from_file(io.BytesIO(png_bytes), content_type="image/png")
    return f"gs://{bucket().name}/{path}"


async def wait_for_image(page, selector: str, timeout: int = 15000) -> bool:
    """Wait for an image to fully load."""
    try:
        await page.wait_for_function(
            """(sel) => {
                const img = document.querySelector(sel);
                return !!(img && img.complete && img.naturalWidth > 0);
            }""",
            arg=selector,
            timeout=timeout
        )
        return True
    except Exception as e:
        LOGGER.warning(f"⚠️ Image {selector} not confirmed loaded: {e}")
        return False


async def save_screenshots(
    doc_snaps: List[firestore.DocumentSnapshot],
    parallel_tabs: int = 3
) -> None:
    """Capture screenshots for a list of channels."""
    total = len(doc_snaps)
    if total == 0:
        LOGGER.info("No channels to process")
        return

    LOGGER.info(f"📥 Starting screenshot capture for {total} channels (parallel_tabs={parallel_tabs})")
    success, failed = 0, 0

    async with PlaywrightContext() as ctx:
        sem = asyncio.Semaphore(parallel_tabs)

        async def process_channel(snap, idx: int):
            nonlocal success, failed
            cid = snap.id
            url = get_channel_url(cid)

            async with sem:
                page = None
                try:
                    page = await ctx.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Give YouTube's JavaScript a moment to render the alert or content
                    await asyncio.sleep(2)
                    
                    # Check if channel has been removed/taken down OR if normal content loads
                    # YouTube shows yt-alert-renderer for removed/suspended channels
                    # Wait for whichever appears first: error alert or normal content
                    channel_removed = False
                    try:
                        # Check which element exists on the page
                        alert = await page.query_selector("yt-alert-renderer")
                        contents = await page.query_selector("#contents")
                        
                        if alert and not contents:
                            # Channel has been removed/suspended
                            error_text = await alert.inner_text()
                            LOGGER.warning(f"⛔ [{idx}/{total}] {cid} - Channel unavailable: {error_text.strip()[:100]}")
                            failed += 1
                            channel_removed = True
                        elif contents:
                            # Normal channel, continue to screenshot
                            pass
                        else:
                            # Neither found - unexpected, wait a bit more
                            await asyncio.sleep(3)
                            alert = await page.query_selector("yt-alert-renderer")
                            contents = await page.query_selector("#contents")
                            if alert:
                                error_text = await alert.inner_text()
                                LOGGER.warning(f"⛔ [{idx}/{total}] {cid} - Channel unavailable: {error_text.strip()[:100]}")
                                failed += 1
                                channel_removed = True
                            elif not contents:
                                raise Exception("Neither alert nor contents found after 5 seconds")
                        
                    except Exception as e:
                        # Timeout waiting for either selector
                        failed += 1
                        LOGGER.warning(f"❌ [{idx}/{total}] {cid}: Timeout waiting for page content: {e}")
                        return
                    
                    # Exit early if channel was removed
                    if channel_removed:
                        # Mark as processed so we don't keep trying to screenshot a removed channel
                        snap.reference.update({
                            "is_screenshot_stored": True,
                            "screenshot_gcs_uri": None,  # No screenshot available
                            "channel_status": "removed",
                            "last_checked_at": datetime.utcnow()
                        })
                        return
                    
                    # At this point, #contents is already visible, so continue with screenshot
                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(2)
                    png = await page.screenshot(full_page=True)

                    gcs_uri = upload_png(cid, png)
                    snap.reference.update({
                        "screenshot_gcs_uri": gcs_uri,
                        "is_screenshot_stored": True,
                        "is_bot_checked": False,  # Initialize for review
                        "screenshot_stored_at": datetime.utcnow(),
                        "last_checked_at": datetime.utcnow()
                    })
                    success += 1
                    LOGGER.info(f"📸 [{idx}/{total}] {cid} → {gcs_uri}")

                except Exception as e:
                    failed += 1
                    LOGGER.warning(f"❌ [{idx}/{total}] {cid}: {e}")
                
                finally:
                    if page:
                        try:
                            await page.close()
                        except Exception:
                            pass

        await asyncio.gather(*(process_channel(s, i) for i, s in enumerate(doc_snaps, start=1)))

    LOGGER.info(f"🎉 Finished screenshots: ✅ {success} ok, ❌ {failed} failed")


def main(limit: int, parallel_tabs: int) -> None:
    """Main entry point for screenshot capture."""
    docs = fetch_channels_needing_screenshots(limit=limit)
    asyncio.run(save_screenshots(docs, parallel_tabs=parallel_tabs))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture channel screenshots")
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("SCREENSHOT_LIMIT", "5000")),
        help="Maximum number of screenshots to capture"
    )
    parser.add_argument(
        "--parallel-tabs",
        type=int,
        default=int(os.getenv("PARALLEL_TABS", "5")),
        help="Number of parallel browser tabs"
    )
    
    args = parser.parse_args()
    main(limit=args.limit, parallel_tabs=args.parallel_tabs)
