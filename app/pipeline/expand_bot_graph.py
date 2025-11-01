#!/usr/bin/env python3
"""
Expand the bot graph:
- Start from seed bots (CLI or Firestore)
- Fetch channel + channelSections
- Take screenshot of homepage
- Scrape About page for external links + subscriptions
- Add featured/subscription channels recursively until exhaustion
- Store raw JSON + screenshots in GCS
- Add full channel docs with metrics, timestamps, screenshot URI in Firestore
"""

import logging
from datetime import datetime
from typing import List, Set, Tuple
import asyncio, re
from urllib.parse import urlparse, unquote, parse_qs

from google.cloud import firestore
from googleapiclient.errors import HttpError
from playwright.async_api import async_playwright

from app.utils.clients import get_youtube
from app.utils.gcs_utils import write_json_to_gcs, upload_png
from app.utils.paths import (
    channel_metadata_raw_path,
    channel_sections_raw_path,
)
from app.utils.image_processing import classify_avatar_url
from app.env import GCS_BUCKET_DATA

import cv2, requests, tempfile
import numpy as np
from app.utils.gcs_utils import upload_file_to_gcs

LOGGER = logging.getLogger("expand_bot_graph")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

db = firestore.Client()
USE_API = False

# ───── Playwright context manager ─────
class PlaywrightContext:
    def __init__(self):
        self.browser = None
        self.playwright = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def new_page(self):
        return await self.browser.new_page()

def get_channel_url(identifier: str, tab: str = "") -> str:
    if identifier.startswith("UC"):
        return f"https://www.youtube.com/channel/{identifier}{tab}"
    else:
        return f"https://www.youtube.com/@{identifier}{tab}"


def store_avatar_to_gcs(cid: str, channel_item: dict) -> str | None:
    """Download the highest-quality avatar and save to GCS. Return gs:// URI."""
    thumbs = channel_item.get("snippet", {}).get("thumbnails", {})
    avatar_url = (
        thumbs.get("maxres", {}).get("url") or
        thumbs.get("high", {}).get("url") or
        thumbs.get("medium", {}).get("url") or
        thumbs.get("default", {}).get("url")
    )
    if not avatar_url:
        return None

    try:
        resp = requests.get(avatar_url, timeout=10)
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cv2.imwrite(tmp.name, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            gcs_path = f"channel_avatars/{cid}.png"
            gcs_uri = upload_file_to_gcs(GCS_BUCKET_DATA, gcs_path, tmp.name, content_type="image/png")
        return gcs_uri
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to save avatar for {cid}: {e}")
        return None

def store_banner_to_gcs(cid: str, channel_item: dict) -> str | None:
    """Download the channel banner image (if available) and save to GCS."""
    banner_url = (
        channel_item.get("brandingSettings", {})
        .get("image", {})
        .get("bannerExternalUrl")
    )
    if not banner_url:
        return None

    try:
        resp = requests.get(banner_url, timeout=10)
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            gcs_path = f"channel_banners/{cid}.jpg"
            gcs_uri = upload_file_to_gcs(
                GCS_BUCKET_DATA, gcs_path, tmp.name, content_type="image/jpeg"
            )
        return gcs_uri
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to save banner for {cid}: {e}")
        return None


# ───── Screenshot helper ─────
async def capture_home_screenshot(context: PlaywrightContext, identifier: str) -> str | None:
    """Take screenshot of the channel's homepage, upload to GCS, return gs:// URI."""
    url = get_channel_url(identifier)
    page = await context.new_page()
    try:
        await page.goto(url, timeout=30000, wait_until="networkidle")
        png = await page.screenshot(full_page=False)   # 👈 change (see #2)
        return upload_png(GCS_BUCKET_DATA, identifier, png)
    except Exception as e:
        LOGGER.warning(f"⚠️ Screenshot failed for {identifier}: {e}")
        return None
    finally:
        await page.close()   # 👈 ensures memory is freed



def resolve_handle_to_id(youtube, handle: str) -> str | None:
    """Resolve @handle to channel ID (UCxxxx)."""
    try:
        q = handle.lstrip("@")
        resp = youtube.search().list(
            part="snippet", q=q, type="channel", maxResults=1
        ).execute()
        print(resp)
        items = resp.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to resolve handle {handle}: {e}")
    return None


# ───── About page scrape (links + subscriptions) ─────
async def scrape_about_page(
    context: PlaywrightContext, identifier: str, sub_limit: int = 50
) -> Tuple[list[str], list[str]]:
    """Scrape external links + subscriptions from the channel's About tab."""
    url = get_channel_url(identifier, "/about")
    print(url)
    about_links, subscriptions = [], []
    try:
        page = await context.new_page()
        await page.goto(url, timeout=30000)

        # External links
        try:
            anchors = await page.query_selector_all("#link-list-container a")
            for a in anchors:
                href = await a.get_attribute("href")
                if href and "youtube.com/redirect" in href:
                    parsed = parse_qs(urlparse(href).query)
                    href = parsed.get("q", [href])[0]
                if href:
                    about_links.append(href)
        except Exception as e:
            LOGGER.warning(f"⚠️ Failed to scrape About tab for {identifier}: {e}")

        # Subscriptions (appear on About page too, multiple patterns)
        subs = await page.query_selector_all(
            "ytd-grid-channel-renderer a#channel-info, ytd-channel-renderer a.channel-link"
        )
        for ch in subs[:sub_limit]:
            href = await ch.get_attribute("href")
            if href:
                if href.startswith("/@"):
                    subscriptions.append(unquote(href[2:]))
                elif href.startswith("/channel/"):
                    subscriptions.append(href.split("/channel/")[1])


    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to scrape About tab for {identifier}: {e}")
    finally:
        await page.close()   # 👈 ensures memory is freed
    return about_links, subscriptions


# ───── Domain storage ─────
def store_channel_domains(cid: str, urls: list[str]) -> None:
    """Store About-section URLs in a separate collection."""
    for url in urls:
        parsed = urlparse(url)
        hostname = parsed.hostname or url
        normalized_domain = hostname.lower().lstrip("www.") if hostname else None

        db.collection("channel_domains").add({
            "from_channel_id": cid,
            "url": url,
            "normalized_domain": normalized_domain,
            "discovered_at": datetime.utcnow(),
            "source": "about_section",
        })

async def scrape_featured_channels(context: PlaywrightContext, identifier: str, limit: int = 50) -> list[str]:
    """Scrape featured channels from the channel's 'Channels' tab (UI fallback)."""
    url = get_channel_url(identifier)
    featured = []
    try:
        page = await context.new_page()
        await page.goto(url, timeout=30000)

        # Featured channels (same tiles as subscriptions, different section header)
        tiles = await page.query_selector_all(
            "ytd-grid-channel-renderer a#channel-info, ytd-channel-renderer a.channel-link"
        )
        for t in tiles[:limit]:
            href = await t.get_attribute("href")
            if href:
                if href.startswith("/@"):
                    featured.append(unquote(href[2:]))
                elif href.startswith("/channel/"):
                    featured.append(href.split("/channel/")[1])
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to scrape featured channels for {identifier}: {e}")
    finally:
        await page.close()   # 👈 ensures memory is freed
    return featured

async def scrape_avatar_url(context: PlaywrightContext, identifier: str) -> str | None:
    """Scrape the channel avatar image URL from the homepage."""
    url = get_channel_url(identifier)
    page = await context.new_page()
    try:
        await page.goto(url, timeout=30000)
        img = await page.query_selector("img.ytCoreImageHost")
        if img:
            return await img.get_attribute("src")
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to scrape avatar for {identifier}: {e}")
    finally:
        await page.close()
    return None

def upgrade_avatar_url(url: str, target_size: int = 256) -> str:
    """
    Replace the size component (=sXX-) in a YouTube avatar URL with =s{target_size}-.
    """
    if not url:
        return url
    return re.sub(r"=s\d+-", f"=s{target_size}-", url)

def download_and_store_avatar(cid: str, avatar_url: str) -> str | None:
    """Download avatar image directly from URL and save to GCS."""
    try:
        resp = requests.get(upgrade_avatar_url(avatar_url,800), timeout=10)
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cv2.imwrite(tmp.name, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            gcs_path = f"channel_avatars/{cid}.png"
            return upload_file_to_gcs(GCS_BUCKET_DATA, gcs_path, tmp.name, content_type="image/png")
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to download avatar {cid}: {e}")
        return None

async def scrape_banner_url(context: PlaywrightContext, identifier: str) -> str | None:
    """Scrape the channel banner image URL from the homepage."""
    url = get_channel_url(identifier)
    page = await context.new_page()
    try:
        await page.goto(url, timeout=30000)
        img = await page.query_selector("yt-image-banner-view-model img")
        if img:
            return await img.get_attribute("src")
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to scrape banner for {identifier}: {e}")
    finally:
        await page.close()
    return None


def download_and_store_banner(cid: str, banner_url: str) -> str | None:
    """Download banner image directly from URL and save to GCS."""
    try:
        resp = requests.get(banner_url, timeout=10)
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            gcs_path = f"channel_banners/{cid}.jpg"
            return upload_file_to_gcs(GCS_BUCKET_DATA, gcs_path, tmp.name, content_type="image/jpeg")
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to download banner {cid}: {e}")
        return None


# ───── Channel doc helper ─────
def _init_channel_doc(
    batch, cid: str, channel_item: dict | None, screenshot_uri: str | None, scraped_only: bool = False
) -> None:
    """Initialize a channel Firestore doc with metadata, metrics, timestamps.
       scraped_only=True → store skeleton doc with is_metadata_missing=True.
    """
    doc_ref = db.collection("channel").document(cid)
    if doc_ref.get().exists:
        return

    avatar_url, avatar_gcs_uri, banner_gcs_uri, metrics = None, None, None, {}

    if channel_item and not scraped_only:
        # avatar URL from snippet
        snippet = channel_item.get("snippet", {})
        if "thumbnails" in snippet:
            avatar_url = (
                snippet.get("thumbnails", {}).get("high", {}).get("url")
                or snippet.get("thumbnails", {}).get("default", {}).get("url")
            )

        # save avatar + banner to GCS
        avatar_gcs_uri = store_avatar_to_gcs(cid, channel_item)
        banner_gcs_uri = store_banner_to_gcs(cid, channel_item)

        # classify avatar
        if avatar_url:
            try:
                _, metrics = classify_avatar_url(avatar_url, size=128)
            except Exception as e:
                LOGGER.warning(f"⚠️ Failed to classify avatar {cid}: {e}")

    data = {
        "channel_id": cid,
        "registered_at": datetime.utcnow(),
        "last_checked_at": datetime.utcnow(),
        "is_bot": True,
        "is_bot_check_type": "propagated",
        "is_bot_checked": True,
        "is_screenshot_stored": bool(screenshot_uri),
        "screenshot_gcs_uri": screenshot_uri,
        # always include these fields, even if None
        "avatar_url": avatar_url,
        "avatar_gcs_uri": avatar_gcs_uri,
        "banner_gcs_uri": banner_gcs_uri,
        "avatar_metrics": metrics,
        "is_metadata_missing": scraped_only,
    }

    batch.set(doc_ref, data)



# ───── Expansion ─────
async def expand_bot_graph_async(seed_channels: List[str]) -> None:
    if not seed_channels:
        LOGGER.info("No seed channels passed")
        return
    
    youtube = get_youtube()
    seen, queue = set(seed_channels), list(seed_channels)

    LOGGER.info(f"🚀 Starting expansion with {len(queue)} seeds")

    async with PlaywrightContext() as context:
        while queue:
            identifier = queue.pop(0)
            try:
                subs: list[str] = []  # <-- always initialize here
                batch = db.batch()
                if USE_API:
                    resp = (
                        youtube.channels()
                        .list(
                            part="id,snippet,statistics,brandingSettings,topicDetails,status,contentDetails",
                            id=identifier,
                            maxResults=1,
                        )
                        .execute()
                    )
                    if not resp.get("items"):
                        LOGGER.warning(f"⚠️ No channel data for {identifier}")
                        continue
                    channel_item = resp["items"][0]
                    write_json_to_gcs(GCS_BUCKET_DATA, channel_metadata_raw_path(identifier), channel_item)

                    screenshot_uri = await capture_home_screenshot(context, identifier)
                    
                    if identifier.startswith("UC"):
                        _init_channel_doc(batch, identifier, channel_item, screenshot_uri, scraped_only=not USE_API)
                    else:
                        # Store handle in pending, but still capture screenshot + timestamp
                        db.collection("channel_pending").document(identifier).set({
                            "handle": identifier,
                            "screenshot_gcs_uri": screenshot_uri,
                            "is_metadata_missing": True,
                            "discovered_at": datetime.utcnow(),
                            "last_checked_at": datetime.utcnow(),
                        }, merge=True)
                
                    sec = (
                        youtube.channelSections()
                        .list(part="snippet,contentDetails", channelId=identifier)
                        .execute()
                    )
                    write_json_to_gcs(GCS_BUCKET_DATA, channel_sections_raw_path(identifier), sec)

                    about_links, subs = await scrape_about_page(context, identifier)
                    if about_links:
                        store_channel_domains(identifier, about_links)
                        LOGGER.info(f"🔗 Stored {len(about_links)} About links for {identifier}")

                    for item in sec.get("items", []):
                        if item.get("snippet", {}).get("type") == "multiplechannels":
                            for featured in item.get("contentDetails", {}).get("channels", []):
                                if featured not in seen:
                                    seen.add(featured)
                                    queue.append(featured)
                                    LOGGER.info(f"➕ Queued featured channel {featured}")
                                    db.collection("channel_links").add({
                                        "from_channel_id": identifier,
                                        "to_channel_id": featured,
                                        "discovered_at": datetime.utcnow(),
                                        "source": "channelSections",
                                    })

                else:
                    # Always capture a screenshot of the current channel (UC or handle)
                    screenshot_uri = await capture_home_screenshot(context, identifier)

                    # Try scraping avatar
                    avatar_url = await scrape_avatar_url(context, identifier)
                    avatar_gcs_uri = None
                    if avatar_url:
                        avatar_gcs_uri = download_and_store_avatar(identifier, avatar_url)

                    # Try scraping banner
                    banner_url = await scrape_banner_url(context, identifier)
                    banner_gcs_uri = None
                    if banner_url:
                        banner_gcs_uri = download_and_store_banner(identifier, banner_url)

                    if identifier.startswith("UC"):
                        # Store skeleton doc since no API metadata
                        data = {
                            "channel_id": identifier,
                            "registered_at": datetime.utcnow(),
                            "last_checked_at": datetime.utcnow(),
                            "is_bot": True,
                            "is_bot_check_type": "propagated",
                            "is_bot_checked": True,
                            "is_screenshot_stored": bool(screenshot_uri),
                            "screenshot_gcs_uri": screenshot_uri,
                            "avatar_url": avatar_url,
                            "avatar_gcs_uri": avatar_gcs_uri,
                            "banner_url": banner_url,
                            "banner_gcs_uri": banner_gcs_uri,
                            "is_metadata_missing": True,
                        }

                        batch.set(db.collection("channel").document(identifier), data)
                    else:
                        # Store pending doc for handle, but still record screenshot + avatar
                        db.collection("channel_pending").document(identifier).set({
                            "handle": identifier,
                            "screenshot_gcs_uri": screenshot_uri,
                            "avatar_url": avatar_url,
                            "avatar_gcs_uri": avatar_gcs_uri,
                            "banner_url": banner_url,
                            "banner_gcs_uri": banner_gcs_uri,
                            "is_metadata_missing": True,
                            "discovered_at": datetime.utcnow(),
                            "last_checked_at": datetime.utcnow(),
                        }, merge=True)

                    if identifier.startswith("UC"):
                        # Store skeleton doc since no API metadata
                        _init_channel_doc(batch, identifier, None, screenshot_uri, scraped_only=True)
                    else:
                        # Store pending doc for handle, but still record screenshot
                        db.collection("channel_pending").document(identifier).set({
                            "handle": identifier,
                            "screenshot_gcs_uri": screenshot_uri,
                            "is_metadata_missing": True,
                            "discovered_at": datetime.utcnow(),
                            "last_checked_at": datetime.utcnow(),
                        }, merge=True)

                    featured = await scrape_featured_channels(context, identifier)
                    for f in featured:
                        if f.startswith("UC"):  
                            # We have a real channel ID
                            f_id = f
                            if f_id not in seen:
                                seen.add(f_id)
                                queue.append(f_id)
                                LOGGER.info(f"➕ Queued (scraped) featured channel {f_id}")
                                db.collection("channel_links").add({
                                    "from_channel_id": identifier,
                                    "to_channel_id": f_id,
                                    "discovered_at": datetime.utcnow(),
                                    "source": "featured_scrape",
                                    "needs_resolution": False,
                                })
                                fb = db.batch()
                                _init_channel_doc(fb, f_id, None, None, scraped_only=True)
                                fb.commit()
                        else:
                            # enqueue handle for recursive scrape
                            handle = f
                            if handle not in seen:
                                seen.add(handle)
                                queue.append(handle)
                            LOGGER.info(f"➕ Queued (scraped) handle {handle} (needs API resolution)")
                            db.collection("channel_links").add({
                                "from_channel_id": identifier,
                                "to_channel_handle": handle,
                                "discovered_at": datetime.utcnow(),
                                "source": "featured_scrape",
                                "needs_resolution": True,
                            })
                            db.collection("channel_pending").document(handle).set({
                                "handle": handle,
                                "discovered_at": datetime.utcnow(),
                                "source": "featured_scrape",
                                "needs_resolution": True,
                            })


                    # also scrape About page in fallback mode
                    about_links, subs = await scrape_about_page(context, identifier)
                    if about_links:
                        store_channel_domains(identifier, about_links)
                        LOGGER.info(f"🔗 Stored {len(about_links)} About links for {identifier}")

                # enqueue subscriptions (always runs, with subs defined)
                for sub in subs:
                    if sub.startswith("UC"):
                        sub_id = sub
                    else:
                        if USE_API:
                            sub_id = resolve_handle_to_id(youtube, sub) or sub
                        else:
                            handle = sub
                            if handle not in seen:
                                seen.add(handle)
                                queue.append(handle)  # 👈 enqueue handle for recursion
                            db.collection("channel_links").add({
                                "from_channel_id": identifier,
                                "to_channel_handle": handle,
                                "discovered_at": datetime.utcnow(),
                                "source": "subscriptions",
                                "needs_resolution": True,
                            })
                            db.collection("channel_pending").document(handle).set({
                                "handle": handle,
                                "discovered_at": datetime.utcnow(),
                                "source": "subscriptions",
                                "needs_resolution": True,
                            })
                            continue   # no UC ID yet, but recursion continues with handle


                    # only enqueue if we have a usable UC ID
                    if sub_id not in seen and sub_id.startswith("UC"):
                        seen.add(sub_id)
                        queue.append(sub_id)
                        LOGGER.info(f"➕ Queued subscription channel {sub_id}")
                        db.collection("channel_links").add({
                            "from_channel_id": identifier,
                            "to_channel_id": sub_id,
                            "discovered_at": datetime.utcnow(),
                            "source": "subscriptions",
                            "needs_resolution": False,
                        })

                batch.commit()


            except HttpError as e:
                LOGGER.error(f"❌ API error for {identifier}: {e}")
            except Exception as e:
                LOGGER.exception(f"💥 Unexpected error for {identifier}: {e}")

    LOGGER.info(f"🎉 Expansion complete. Total channels discovered: {len(seen)}")


# ───── Entrypoint ─────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Expand bot graph recursively")
    parser.add_argument("seed_channels", nargs="*", help="Seed channel IDs")
    args = parser.parse_args()

    if not args.seed_channels:
        LOGGER.info("📂 No seeds provided → querying Firestore for all known bots")
        seeds = [
            d.id
            for d in db.collection("channel")
            .where("is_bot_checked", "==", True)
            .where("is_bot", "==", True)
            .stream()
        ]
        additional_seeds = [
            d.id
            for d in db.collection("channel_pending")
            .where("needs_resolution", "==", True)
            .stream()
        ]
        seeds = seeds + additional_seeds
        LOGGER.info(f"   → Got {len(seeds)} seeds from Firestore")
    else:
        seeds = args.seed_channels

    asyncio.run(expand_bot_graph_async(seeds))
