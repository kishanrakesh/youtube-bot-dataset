#!/usr/bin/env python3
"""Channel graph expansion and scraping with Playwright.

This module provides functionality to:
- Start from seed bot channels (CLI or Firestore)
- Fetch channel metadata and sections via YouTube API
- Take screenshots of channel homepages
- Scrape About pages for external links and subscriptions
- Recursively add featured/subscription channels until exhaustion
- Store raw JSON and screenshots in GCS
- Add complete channel documents with metrics to Firestore
"""

import asyncio
import json
import logging
import random
import re
import tempfile
from datetime import datetime
from typing import List, Set, Tuple, Optional
from urllib.parse import urlparse, unquote, parse_qs

import cv2
import numpy as np
import requests
from google.cloud import firestore
from googleapiclient.errors import HttpError
from playwright.async_api import async_playwright, Page

from app.utils.clients import get_youtube
from app.utils.gcs_utils import write_json_to_gcs, upload_png, upload_file_to_gcs
from app.utils.paths import (
    channel_metadata_raw_path,
    channel_sections_raw_path,
)
from app.utils.image_processing import classify_avatar_url
from app.env import GCS_BUCKET_DATA

__all__ = [
    "PlaywrightContext",
    "get_channel_url",
    "scrape_about_page",
    "expand_bot_graph_async",
]

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

db = firestore.Client()

CHANNEL_PARTS = (
    "id,snippet,statistics,brandingSettings,topicDetails,status,contentDetails"
)

USER_AGENTS = [
    # Chrome (Windows / macOS / Linux)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.140 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.234 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.234 Safari/537.36",
    
    # Safari (macOS / iOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    
    # Firefox (Windows / macOS / Linux)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.4; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    
    # Edge (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.140 Safari/537.36 Edg/121.0.2277.128",
    
    # Android (Chrome Mobile)
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.234 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.140 Mobile Safari/537.36",
    
    # Fallbacks
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
]


# ============================================================================
# Playwright Context Manager
# ============================================================================

class PlaywrightContext:
    """Async context manager for Playwright browser automation.
    
    Manages browser lifecycle with automatic crash recovery for Cloud Run.
    Maintains a persistent browser context across multiple page operations.
    """
    
    def __init__(self) -> None:
        """Initialize the Playwright context manager."""
        self.playwright = None
        self.browser = None
        self.context = None

    async def __aenter__(self) -> "PlaywrightContext":
        """Start Playwright and launch browser on context entry.
        
        Returns:
            Self for use as async context manager
        """
        self.playwright = await async_playwright().start()
        self.browser, self.context = await self._launch_browser()
        return self

    async def _launch_browser(self) -> Tuple:
        """Launch a new Chromium browser instance with anti-detection settings.
        
        Returns:
            Tuple of (browser, context) for reuse
        """
        ua = random.choice(USER_AGENTS)
        browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-first-run",
                "--disable-extensions",
            ],
        )
        context = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/Chicago",
            java_script_enabled=True,
            accept_downloads=False,
            bypass_csp=True,
            extra_http_headers={
                "accept-language": "en-US,en;q=0.9",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "accept-encoding": "gzip, deflate, br",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
                "upgrade-insecure-requests": "1",
            },
        )
        await context.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        }""")
        return browser, context

    async def new_page(self) -> Page:
        """Safely open a new browser tab with automatic crash recovery.
        
        If the browser context is missing or crashed, automatically relaunch.
        
        Returns:
            New Playwright Page instance
        """
        if not self.context:
            LOGGER.warning("⚠️ Browser context missing — relaunching")
            self.browser, self.context = await self._launch_browser()

        try:
            page = await self.context.new_page()
            page.set_default_navigation_timeout(90000)
            page.set_default_timeout(30000)
            return page
        except Exception as e:
            LOGGER.warning(f"⚠️ Browser crashed ({e}), relaunching")
            self.browser, self.context = await self._launch_browser()
            page = await self.context.new_page()
            page.set_default_navigation_timeout(90000)
            page.set_default_timeout(30000)
            return page

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        """Clean up browser and Playwright on context exit.
        
        Args:
            _exc_type: Exception type (if any) - unused
            _exc: Exception instance (if any) - unused
            _tb: Exception traceback (if any) - unused
        """
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        finally:
            if self.playwright:
                await self.playwright.stop()


# ============================================================================
# Helper Functions
# ============================================================================

def get_channel_url(identifier: str, tab: str = "") -> str:
    """Construct a YouTube channel URL from ID or handle.
    
    Args:
        identifier: Channel ID (UCxxx) or handle (@username)
        tab: Optional tab path (e.g., '/about', '/videos')
        
    Returns:
        Full YouTube channel URL
    """
    if identifier.startswith("UC"):
        return f"https://www.youtube.com/channel/{identifier}{tab}"
    else:
        return f"https://www.youtube.com/@{identifier}{tab}"


def store_avatar_to_gcs(cid: str, channel_item: dict) -> Optional[str]:
    """Download channel avatar and save to GCS.
    
    Args:
        cid: Channel ID
        channel_item: YouTube API channel response item
        
    Returns:
        gs:// URI of uploaded avatar, or None if failed
    """
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
            gcs_uri = upload_file_to_gcs(
                GCS_BUCKET_DATA, gcs_path, tmp.name, content_type="image/png"
            )
        return gcs_uri
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to save avatar for {cid}: {e}")
        return None


def store_banner_to_gcs(cid: str, channel_item: dict) -> Optional[str]:
    """Download channel banner image and save to GCS.
    
    Args:
        cid: Channel ID
        channel_item: YouTube API channel response item
        
    Returns:
        gs:// URI of uploaded banner, or None if not available or failed
    """
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


async def capture_home_screenshot(
    context: PlaywrightContext, 
    identifier: str
) -> Optional[str]:
    """Capture a screenshot of the channel's homepage.
    
    Args:
        context: Active PlaywrightContext
        identifier: Channel ID or handle
        
    Returns:
        gs:// URI of uploaded screenshot, or None if failed
    """
    url = get_channel_url(identifier)
    page = await context.new_page()
    try:
        await page.goto(url, timeout=60000)
        
        # Give YouTube's JavaScript a moment to render the alert or content
        await asyncio.sleep(2)
        
        # Check if channel has been removed/taken down OR if normal content loads
        # YouTube shows yt-alert-renderer for removed/suspended channels
        channel_removed = False
        try:
            alert = await page.query_selector("yt-alert-renderer")
            contents = await page.query_selector("#contents")
            
            if alert and not contents:
                error_text = await alert.inner_text()
                LOGGER.warning(f"⛔ Channel {identifier} unavailable: {error_text.strip()[:100]}")
                channel_removed = True
            elif not contents:
                # Neither found - wait a bit more
                await asyncio.sleep(3)
                alert = await page.query_selector("yt-alert-renderer")
                contents = await page.query_selector("#contents")
                if alert:
                    error_text = await alert.inner_text()
                    LOGGER.warning(f"⛔ Channel {identifier} unavailable: {error_text.strip()[:100]}")
                    channel_removed = True
                elif not contents:
                    raise Exception("Neither alert nor contents found")
        except Exception as e:
            LOGGER.warning(f"⚠️ Timeout waiting for page content on {identifier}: {e}")
            return None
        
        # Exit early if channel was removed
        if channel_removed:
            return None
        
        # At this point, #contents is already visible
        await page.evaluate("window.scrollBy(0, 800)")  # Force load more elements
        await asyncio.sleep(3)  # Give time for thumbnails to render
        png = await page.screenshot(full_page=True)
        return upload_png(GCS_BUCKET_DATA, identifier, png)
    except Exception as e:
        LOGGER.warning(f"⚠️ Screenshot failed for {identifier}: {e}")
        return None
    finally:
        await page.close()


def _normalize_handle(identifier: str) -> Optional[str]:
    """Extract bare handle text (@foo → foo)."""
    if not identifier or identifier.startswith("UC"):
        return None
    handle = identifier.lstrip("@")
    return handle or None


def fetch_channel_item(youtube, identifier: str) -> Optional[dict]:
    """Fetch full channel metadata for an identifier (UC ID or handle)."""
    if not youtube or not identifier:
        return None

    try:
        if identifier.startswith("UC"):
            resp = (
                youtube.channels()
                .list(part=CHANNEL_PARTS, id=identifier, maxResults=1)
                .execute()
            )
        else:
            handle = _normalize_handle(identifier)
            if not handle:
                return None
            resp = (
                youtube.channels()
                .list(part=CHANNEL_PARTS, forHandle=handle, maxResults=1)
                .execute()
            )
            if not resp.get("items"):
                # Fallback to search if handle lookup fails (edge cases)
                search = (
                    youtube.search()
                    .list(part="snippet", q=handle, type="channel", maxResults=1)
                    .execute()
                )
                items = search.get("items", [])
                if not items:
                    return None
                channel_id = items[0]["snippet"].get("channelId")
                if not channel_id:
                    return None
                resp = (
                    youtube.channels()
                    .list(part=CHANNEL_PARTS, id=channel_id, maxResults=1)
                    .execute()
                )

        items = resp.get("items", [])
        return items[0] if items else None
    except Exception as exc:
        LOGGER.warning(f"⚠️ fetch_channel_item failed for {identifier}: {exc}")
        return None


def resolve_handle_to_id(youtube, handle: str) -> Optional[str]:
    """Resolve @handle to channel ID using YouTube API."""
    item = fetch_channel_item(youtube, handle)
    return item.get("id") if item else None


# ============================================================================
# Page Scraping Functions
# ============================================================================

async def scrape_about_page(
    context: PlaywrightContext,
    identifier: str,
    sub_limit: int = 50
) -> Tuple[List[str], List[str]]:
    """Scrape external links and subscriptions from channel About page.
    
    Args:
        context: Active PlaywrightContext
        identifier: Channel ID or handle
        sub_limit: Maximum number of subscriptions to scrape
        
    Returns:
        Tuple of (about_links, subscriptions) where:
            - about_links: List of external URLs from the links section
            - subscriptions: List of channel IDs/handles from subscribed channels
    """
    url = get_channel_url(identifier, "/about")
    about_links, subscriptions = [], []
    page = None

    try:
        # Open page safely
        page = await context.new_page()

        # Try navigating with retry logic
        for attempt in range(3):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=90000)
                
                # Give YouTube's JavaScript a moment to render
                await asyncio.sleep(3)
                
                # Check if channel has been removed/taken down
                # YouTube shows yt-alert-renderer for removed/suspended channels
                channel_removed = False
                alert = await page.query_selector("yt-alert-renderer")
                if alert:
                    try:
                        error_text = await alert.inner_text()
                        LOGGER.warning(f"⛔ Channel {identifier} unavailable: {error_text.strip()[:100]}")
                        channel_removed = True
                    except Exception:
                        pass
                
                # Exit early if channel was removed
                if channel_removed:
                    return about_links, subscriptions
                
                # Wait for About page specific content to appear
                # Try multiple possible selectors
                page_loaded = False
                for selector in ["ytd-channel-about-metadata-renderer", "#description-container", "ytd-about-channel-renderer", "#page-header"]:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            page_loaded = True
                            break
                    except Exception:
                        continue
                
                if not page_loaded:
                    # Debug: save page HTML to see what's actually there
                    try:
                        html_content = await page.content()
                        debug_file = f"/tmp/debug_{identifier}_attempt{attempt+1}.html"
                        with open(debug_file, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        # Print first 2000 chars to log
                        LOGGER.warning(f"⚠️ About page content not loaded for {identifier} (attempt {attempt+1}/3)")
                        LOGGER.warning(f"📄 Debug HTML saved to: {debug_file}")
                        LOGGER.warning(f"📄 Page start:\n{html_content[:2000]}")
                    except Exception as e:
                        LOGGER.warning(f"⚠️ Could not save debug HTML: {e}")
                    
                    if attempt == 2:
                        # Last attempt failed, return empty results
                        return about_links, subscriptions
                    await asyncio.sleep(3)
                    continue
                
                # Give extra time for dynamic content
                await humanize_page(page)
                await asyncio.sleep(2)
                break
                
            except Exception as e:
                LOGGER.warning(f"⚠️ Navigation error for {identifier} (attempt {attempt+1}/3): {e}")
                if attempt == 2:
                    return about_links, subscriptions
                await asyncio.sleep(3)

        # Scrape external links
        anchors = await page.query_selector_all("#link-list-container a")
        for a in anchors:
            href = await a.get_attribute("href")
            if href and "youtube.com/redirect" in href:
                parsed = parse_qs(urlparse(href).query)
                href = parsed.get("q", [href])[0]
            if href:
                about_links.append(href)

        # Scrape subscriptions
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
        LOGGER.warning(f"⚠️ Error scraping About tab for {identifier}: {e}")

    finally:
        # Always close page safely
        if page:
            try:
                await page.close()
            except Exception as e:
                LOGGER.debug(f"⚠️ Error closing page for {identifier}: {e}")

    return about_links, subscriptions


async def humanize_page(page: Page, min_wait: float = 0.5, max_wait: float = 2.0) -> None:
    """Simulate human-like behavior on the page to avoid bot detection.
    
    Performs random scrolling, mouse movements, and pauses.
    
    Args:
        page: Playwright Page instance
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
    """
    # Small pause
    await asyncio.sleep(random.uniform(min_wait, max_wait))

    # Gentle scrolls
    try:
        height = await page.evaluate("() => document.body.scrollHeight")
        for y in range(0, height, random.randint(250, 800)):
            try:
                await page.evaluate(f"window.scrollTo(0, {y})")
                await asyncio.sleep(random.uniform(0.1, 0.6))
            except Exception:
                break
    except Exception:
        pass  # Page not ready for scrolling yet

    # Small mouse movement
    try:
        viewport = page.viewport_size
        w, h = viewport["width"], viewport["height"]
        for _ in range(random.randint(2, 6)):
            await page.mouse.move(
                random.randint(50, w - 50),
                random.randint(50, h - 50),
                steps=random.randint(10, 40)
            )
            await asyncio.sleep(random.uniform(0.05, 0.2))
    except Exception:
        pass

    # Extra pause for content to settle
    await asyncio.sleep(random.uniform(0.2, 0.8))


def store_channel_domains(cid: str, urls: List[str]) -> None:
    """Store channel About section URLs to Firestore channel_domains collection.
    
    Args:
        cid: Channel ID
        urls: List of external URLs from channel About page
    """
    for url in urls:
        parsed = urlparse(url)
        hostname = parsed.hostname or url
        normalized_domain = hostname.lower().lstrip("www.") if hostname else None

        db.collection("channel_domains").add({
            "from_channel_id": cid,
            "url": url,
            "normalized_domain": normalized_domain,
            "discovered_at": datetime.now(),
            "source": "about_section",
        })


async def scrape_featured_channels(
    context: PlaywrightContext,
    identifier: str,
    limit: int = 50
) -> List[str]:
    """Scrape featured channels from the channel's Channels tab.
    
    Args:
        context: Active PlaywrightContext
        identifier: Channel ID or handle
        limit: Maximum number of featured channels to scrape
        
    Returns:
        List of channel IDs/handles
    """
    url = get_channel_url(identifier)
    featured = []
    page = None
    
    try:
        page = await context.new_page()
        await page.goto(url, timeout=30000)

        # Featured channels tiles
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
        if page:
            await page.close()
    return featured


async def scrape_avatar_url(context: PlaywrightContext, identifier: str) -> Optional[str]:
    """Scrape channel avatar image URL from homepage.
    
    Args:
        context: Active PlaywrightContext
        identifier: Channel ID or handle
        
    Returns:
        Avatar image URL, or None if not found
    """
    url = get_channel_url(identifier)
    page = None
    
    try:
        page = await context.new_page()
        await page.goto(url, timeout=30000)
        img = await page.query_selector("img.ytCoreImageHost")
        if img:
            return await img.get_attribute("src")
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to scrape avatar for {identifier}: {e}")
    finally:
        if page:
            await page.close()
    return None


def upgrade_avatar_url(url: str, target_size: int = 256) -> str:
    """Replace size component (=sXX-) in YouTube avatar URL.
    
    Args:
        url: Original avatar URL
        target_size: Desired image size in pixels
        
    Returns:
        URL with updated size parameter
    """
    if not url:
        return url
    return re.sub(r"=s\d+-", f"=s{target_size}-", url)


def download_and_store_avatar(cid: str, avatar_url: str) -> Optional[str]:
    """Download avatar image from URL and save to GCS.
    
    Args:
        cid: Channel ID
        avatar_url: Avatar image URL
        
    Returns:
        gs:// URI of uploaded avatar, or None if failed
    """
    try:
        resp = requests.get(upgrade_avatar_url(avatar_url, 800), timeout=10)
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cv2.imwrite(tmp.name, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            gcs_path = f"channel_avatars/{cid}.png"
            return upload_file_to_gcs(
                GCS_BUCKET_DATA, gcs_path, tmp.name, content_type="image/png"
            )
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to download avatar {cid}: {e}")
        return None


async def scrape_banner_url(context: PlaywrightContext, identifier: str) -> Optional[str]:
    """Scrape channel banner image URL from homepage.
    
    Args:
        context: Active PlaywrightContext
        identifier: Channel ID or handle
        
    Returns:
        Banner image URL, or None if not found
    """
    url = get_channel_url(identifier)
    page = None
    
    try:
        page = await context.new_page()
        await page.goto(url, timeout=30000)
        img = await page.query_selector("yt-image-banner-view-model img")
        if img:
            return await img.get_attribute("src")
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to scrape banner for {identifier}: {e}")
    finally:
        if page:
            await page.close()
    return None


def download_and_store_banner(cid: str, banner_url: str) -> Optional[str]:
    """Download banner image from URL and save to GCS.
    
    Args:
        cid: Channel ID
        banner_url: Banner image URL
        
    Returns:
        gs:// URI of uploaded banner, or None if failed
    """
    try:
        resp = requests.get(banner_url, timeout=10)
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            gcs_path = f"channel_banners/{cid}.jpg"
            return upload_file_to_gcs(
                GCS_BUCKET_DATA, gcs_path, tmp.name, content_type="image/jpeg"
            )
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to download banner {cid}: {e}")
        return None


# ============================================================================
# Firestore Document Management
# ============================================================================

def _init_channel_doc(
    batch,
    cid: str,
    channel_item: Optional[dict],
    screenshot_uri: Optional[str],
    scraped_only: bool = False,
    is_bot: bool = True,
    bot_check_type: str = "propagated"
) -> None:
    """Initialize a channel Firestore document with metadata and metrics.
    
    Args:
        batch: Firestore batch write
        cid: Channel ID
        channel_item: YouTube API channel response item (or None)
        screenshot_uri: gs:// URI of screenshot (or None)
        scraped_only: If True, store skeleton doc with is_metadata_missing=True
        is_bot: Bot status (True=confirmed bot, False=pending review)
        bot_check_type: How bot status was determined (e.g., "propagated", "pending_review", "manual")
    """
    doc_ref = db.collection("channel").document(cid)
    if doc_ref.get().exists:
        return

    avatar_url, avatar_gcs_uri, banner_gcs_uri, metrics = None, None, None, {}

    if channel_item and not scraped_only:
        # Extract avatar URL from snippet
        snippet = channel_item.get("snippet", {})
        if "thumbnails" in snippet:
            avatar_url = (
                snippet.get("thumbnails", {}).get("high", {}).get("url")
                or snippet.get("thumbnails", {}).get("default", {}).get("url")
            )

        # Save avatar and banner to GCS
        avatar_gcs_uri = store_avatar_to_gcs(cid, channel_item)
        banner_gcs_uri = store_banner_to_gcs(cid, channel_item)

        # Classify avatar
        if avatar_url:
            try:
                _, metrics = classify_avatar_url(avatar_url, size=128)
            except Exception as e:
                LOGGER.warning(f"⚠️ Failed to classify avatar {cid}: {e}")

    data = {
        "channel_id": cid,
        "registered_at": datetime.now(),
        "last_checked_at": datetime.now(),
        "is_bot": is_bot,
        "is_bot_check_type": bot_check_type,
        "is_bot_checked": is_bot,  # Only mark as checked if is_bot is True
        "is_screenshot_stored": bool(screenshot_uri),
        "screenshot_gcs_uri": screenshot_uri,
        "avatar_url": avatar_url,
        "avatar_gcs_uri": avatar_gcs_uri,
        "banner_gcs_uri": banner_gcs_uri,
        "avatar_metrics": metrics,
        "is_metadata_missing": scraped_only,
    }

    batch.set(doc_ref, data)


# ============================================================================
# Bot Graph Expansion
# ============================================================================

# ═══════════════════════════════════════════════════════════════════
# Bot Graph Expansion - Refactored for Clarity
# ═══════════════════════════════════════════════════════════════════

async def _process_channel_with_api(
    youtube, 
    context: PlaywrightContext, 
    identifier: str, 
    batch,
    seen: set,
    queue: list,
    is_bot: bool = True,
    bot_check_type: str = "propagated"
) -> list[str]:
    """Process a channel using YouTube API.
    
    Args:
        is_bot: Bot status for this channel
        bot_check_type: How bot status was determined
        
    Returns:
        List of subscription channel IDs/handles
    """
    # Fetch channel metadata via API
    channel_item = fetch_channel_item(youtube, identifier)
    if not channel_item:
        LOGGER.warning(f"⚠️ No channel data for {identifier}")
        return []

    channel_id = channel_item.get("id", identifier)
    if channel_id not in seen:
        seen.add(channel_id)
    if channel_id != identifier:
        LOGGER.info(f"🔁 Resolved {identifier} → {channel_id}")
    identifier = channel_id

    write_json_to_gcs(GCS_BUCKET_DATA, channel_metadata_raw_path(identifier), channel_item)

    # Capture screenshot
    screenshot_uri = await capture_home_screenshot(context, identifier)
    
    # Initialize channel doc or pending doc
    if identifier.startswith("UC"):
        _init_channel_doc(batch, identifier, channel_item, screenshot_uri, 
                         scraped_only=False, is_bot=is_bot, bot_check_type=bot_check_type)
    else:
        db.collection("channel_pending").document(identifier).set({
            "handle": identifier,
            "screenshot_gcs_uri": screenshot_uri,
            "is_metadata_missing": True,
            "is_bot": is_bot,
            "is_bot_check_type": bot_check_type,
            "discovered_at": datetime.now(),
            "last_checked_at": datetime.now(),
        }, merge=True)
    
    # Fetch channel sections
    sec = (
        youtube.channelSections()
    .list(part="snippet,contentDetails", channelId=identifier)
        .execute()
    )
    write_json_to_gcs(GCS_BUCKET_DATA, channel_sections_raw_path(identifier), sec)

    # Scrape about page
    about_links, subs = await scrape_about_page(context, identifier)
    if about_links:
        store_channel_domains(identifier, about_links)
        LOGGER.info(f"🔗 Stored {len(about_links)} About links for {identifier}")

    # Process featured channels from API
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
                        "discovered_at": datetime.now(),
                        "source": "channelSections",
                    })
    
    return subs


async def _process_channel_without_api(
    context: PlaywrightContext,
    identifier: str,
    batch,
    seen: set,
    queue: list,
    is_bot: bool = True,
    bot_check_type: str = "propagated"
) -> list[str]:
    """Process a channel without YouTube API (scraping only).
    
    Args:
        is_bot: Bot status for this channel
        bot_check_type: How bot status was determined
        
    Returns:
        List of subscription channel IDs/handles
    """
    # Capture screenshot
    screenshot_uri = await capture_home_screenshot(context, identifier)

    # Scrape avatar
    avatar_url = await scrape_avatar_url(context, identifier)
    avatar_gcs_uri = download_and_store_avatar(identifier, avatar_url) if avatar_url else None

    # Scrape banner
    banner_url = await scrape_banner_url(context, identifier)
    banner_gcs_uri = download_and_store_banner(identifier, banner_url) if banner_url else None

    # Store channel or pending doc
    if identifier.startswith("UC"):
        data = {
            "channel_id": identifier,
            "registered_at": datetime.now(),
            "last_checked_at": datetime.now(),
            "is_bot": is_bot,
            "is_bot_check_type": bot_check_type,
            "is_bot_checked": is_bot,
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
        db.collection("channel_pending").document(identifier).set({
            "handle": identifier,
            "screenshot_gcs_uri": screenshot_uri,
            "avatar_url": avatar_url,
            "avatar_gcs_uri": avatar_gcs_uri,
            "banner_url": banner_url,
            "banner_gcs_uri": banner_gcs_uri,
            "is_bot": is_bot,
            "is_bot_check_type": bot_check_type,
            "is_metadata_missing": True,
            "discovered_at": datetime.now(),
            "last_checked_at": datetime.now(),
        }, merge=True)

    # Scrape featured channels
    featured = await scrape_featured_channels(context, identifier)
    for f in featured:
        if f.startswith("UC"):
            # Real channel ID
            if f not in seen:
                seen.add(f)
                queue.append(f)
                LOGGER.info(f"➕ Queued (scraped) featured channel {f}")
                db.collection("channel_links").add({
                    "from_channel_id": identifier,
                    "to_channel_id": f,
                    "discovered_at": datetime.now(),
                    "source": "featured_scrape",
                    "needs_resolution": False,
                })
                fb = db.batch()
                _init_channel_doc(fb, f, None, None, scraped_only=True, 
                                is_bot=is_bot, bot_check_type=bot_check_type)
                fb.commit()
        else:
            # Handle - needs resolution
            if f not in seen:
                seen.add(f)
                queue.append(f)
            LOGGER.info(f"➕ Queued (scraped) handle {f} (needs API resolution)")
            db.collection("channel_links").add({
                "from_channel_id": identifier,
                "to_channel_handle": f,
                "discovered_at": datetime.now(),
                "source": "featured_scrape",
                "needs_resolution": True,
            })
            db.collection("channel_pending").document(f).set({
                "handle": f,
                "discovered_at": datetime.now(),
                "source": "featured_scrape",
                "needs_resolution": True,
            })

    # Scrape about page
    about_links, subs = await scrape_about_page(context, identifier)
    if about_links:
        store_channel_domains(identifier, about_links)
        LOGGER.info(f"🔗 Stored {len(about_links)} About links for {identifier}")
    
    return subs


def _process_subscriptions(
    subs: list[str],
    identifier: str,
    youtube,
    seen: set,
    queue: list,
    use_api: bool,
    is_bot: bool = True,
    bot_check_type: str = "propagated"
) -> None:
    """Process subscription channels and add to queue.
    
    Args:
        subs: List of channel IDs or handles from subscriptions
        identifier: Parent channel ID or handle
        youtube: YouTube API client (or None if not using API)
        seen: Set of already-processed channel identifiers
        queue: Queue of channels to process
        use_api: Whether to use YouTube API for handle resolution
        is_bot: Bot status to assign to discovered channels
        bot_check_type: How bot status was determined
    """
    for sub in subs:
        if sub.startswith("UC"):
            sub_id = sub
        else:
            if use_api:
                sub_id = resolve_handle_to_id(youtube, sub) or sub
            else:
                # Handle without API - enqueue for recursive processing
                if sub not in seen:
                    seen.add(sub)
                    queue.append(sub)
                db.collection("channel_links").add({
                    "from_channel_id": identifier,
                    "to_channel_handle": sub,
                    "discovered_at": datetime.now(),
                    "source": "subscriptions",
                    "needs_resolution": True,
                })
                db.collection("channel_pending").document(sub).set({
                    "handle": sub,
                    "discovered_at": datetime.now(),
                    "source": "subscriptions",
                    "needs_resolution": True,
                })
                continue

        # Only enqueue if we have a usable UC ID
        if sub_id not in seen and sub_id.startswith("UC"):
            seen.add(sub_id)
            queue.append(sub_id)
            LOGGER.info(f"➕ Queued subscription channel {sub_id}")
            db.collection("channel_links").add({
                "from_channel_id": identifier,
                "to_channel_id": sub_id,
                "discovered_at": datetime.now(),
                "source": "subscriptions",
                "needs_resolution": False,
            })


async def expand_bot_graph_async(
    seed_channels: List[str],
    use_api: bool = False,
    is_bot: bool = True,
    bot_check_type: str = "propagated",
) -> None:
    """Expand the bot graph by recursively discovering channels.
    
    Starting from seed channels, recursively discovers and processes:
    - Channel metadata via YouTube API
    - Featured channels and subscriptions
    - About page external links
    - Screenshots and avatars
    
    Stores all data to Firestore and GCS.
    
    Args:
        seed_channels: Initial list of channel IDs or handles to start expansion from
        use_api: Whether to fetch channel metadata via the YouTube API (True) or rely on scraping only (False)
        is_bot: Bot status for discovered channels (True=confirmed, False=pending review)
        bot_check_type: How bot status was determined (e.g., "propagated", "pending_review", "manual")
    """
    if not seed_channels:
        LOGGER.info("No seed channels passed")
        return
    
    youtube = get_youtube() if use_api else None
    seen, queue = set(seed_channels), list(seed_channels)

    LOGGER.info(f"🚀 Starting expansion with {len(queue)} seeds")

    async with PlaywrightContext() as context:
        while queue:
            identifier = queue.pop(0)
            
            try:
                batch = db.batch()
                subs: list[str] = []
                
                # Process channel with or without API
                if use_api:
                    subs = await _process_channel_with_api(
                        youtube, context, identifier, batch, seen, queue,
                        is_bot=is_bot, bot_check_type=bot_check_type
                    )
                else:
                    subs = await _process_channel_without_api(
                        context, identifier, batch, seen, queue,
                        is_bot=is_bot, bot_check_type=bot_check_type
                    )
                
                # Process subscriptions from about page
                _process_subscriptions(subs, identifier, youtube, seen, queue, use_api,
                                     is_bot=is_bot, bot_check_type=bot_check_type)
                
                # Commit batch
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
    parser.add_argument("seed_channels", nargs="*", help="Seed channel IDs or handles")
    parser.add_argument(
        "--use-api",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use the YouTube Data API for channel metadata (default: scrape only)",
    )
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

    asyncio.run(expand_bot_graph_async(seeds, use_api=args.use_api))
