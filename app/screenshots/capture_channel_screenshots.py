#capture_channel_screenshots

#!/usr/bin/env python3
"""
Capture YouTube channel homepage screenshots using Playwright,
store them in GCS, and update Firestore channel docs.

Flow:
- Query Firestore: channels with is_screenshot_stored == False
- Visit https://www.youtube.com/channel/{channel_id}
- Take full-page screenshot
- Upload to GCS: gs://<bucket>/channel_screenshots/raw/{channel_id}.png
- Update Firestore: {is_screenshot_stored=True, screenshot_gcs_uri=...}
"""

import io, os, uuid, logging
from typing import List
from datetime import datetime
from itertools import cycle

from google.cloud import firestore, storage
# from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from app.pipeline.expand_bot_graph import PlaywrightContext, get_channel_url
from app.utils.gcs_utils import upload_png  # reuse your existing GCS helper

# ───── config ─────
LOGGER = logging.getLogger("screenshot")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

COLLECTION_NAME = "channel"
BUCKET_NAME     = os.getenv("SCREENSHOT_BUCKET", "yt-bot-screens")
PAGE_TIMEOUT_MS = 25_000
FETCH_LIMIT     = 200   # number of channels to capture per run

# ───── GCP clients ─────
_db: firestore.Client | None = None
_storage: storage.Client | None = None

def db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db

def bucket():
    global _storage
    if _storage is None:
        _storage = storage.Client()
    return _storage.bucket(BUCKET_NAME)

# ───── Firestore query ─────
def fetch_channels_needing_screenshots(limit: int = FETCH_LIMIT):
    """Fetch Firestore docs for channels missing screenshots."""
    query = (
        db().collection(COLLECTION_NAME)
        .where("is_screenshot_stored", "==", False)
        .limit(limit)
    )
    docs = list(query.stream())
    LOGGER.info("Fetched %d channels needing screenshots", len(docs))
    return docs

# ───── GCS upload helper ─────
def upload_png(cid: str, png_bytes: bytes) -> str:
    """Upload PNG to GCS and return its URI."""
    path = f"channel_screenshots/raw/{cid}_{uuid.uuid4().hex}.png"
    blob = bucket().blob(path)
    blob.upload_from_file(io.BytesIO(png_bytes), content_type="image/png")
    return f"gs://{bucket().name}/{path}"

async def wait_for_image(page, selector: str, timeout: int = 15000):
    try:
        await page.wait_for_function(
            """(sel) => {
                const img = document.querySelector(sel);
                return !!(img && img.complete && img.naturalWidth > 0);
            }""",
            arg=selector,     # must be passed as keyword, not positional
            timeout=timeout
        )
        return True
    except Exception as e:
        LOGGER.warning(f"⚠️ Image {selector} not confirmed loaded: {e}")
        return False


# ───── main capture ─────
async def save_screenshots(doc_snaps: List[firestore.DocumentSnapshot], parallel_tabs: int = 3):
    total = len(doc_snaps)
    if total == 0:
        LOGGER.info("No channels to process.")
        return

    LOGGER.info(f"📥 Starting screenshot capture for {total} channels (parallel_tabs={parallel_tabs})")
    success, failed = 0, 0

    async with PlaywrightContext() as ctx:  # ✅ use shared context
        sem = asyncio.Semaphore(parallel_tabs)

        async def process_channel(snap, idx: int):
            nonlocal success, failed
            cid = snap.id
            url = get_channel_url(cid)

            async with sem:
                try:
                    page = await ctx.new_page()
                    await page.goto(url, timeout=60000)
                    await page.wait_for_selector("#contents", timeout=20000)
                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(2)
                    png = await page.screenshot(full_page=True)
                    await page.close()

                    gcs_uri = upload_png(cid, png)
                    snap.reference.update({
                        "screenshot_gcs_uri": gcs_uri,
                        "is_screenshot_stored": True,
                        "screenshot_stored_at": datetime.utcnow(),
                        "last_checked_at": datetime.utcnow()
                    })
                    success += 1
                    LOGGER.info(f"📸 [{idx}/{total}] {cid} → {gcs_uri}")

                except Exception as e:
                    failed += 1
                    LOGGER.warning(f"❌ [{idx}/{total}] {cid}: {e}")

        await asyncio.gather(*(process_channel(s, i) for i, s in enumerate(doc_snaps, start=1)))

    LOGGER.info(f"🎉 Finished screenshots: ✅ {success} ok, ❌ {failed} failed")


# ───── driver ─────
if __name__ == "__main__":
    docs = fetch_channels_needing_screenshots()
    asyncio.run(save_screenshots(docs))
