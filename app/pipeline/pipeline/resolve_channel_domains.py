# app/pipeline/resolve_channel_domains.py

import asyncio
from datetime import datetime
from urllib.parse import urlparse

from google.cloud import firestore
from playwright.async_api import async_playwright

from app.utils.logging import get_logger

logger = get_logger()
db = firestore.Client()

def normalize_url(url: str) -> str:
    """
    Normalize a URL into just scheme://host
    (you can make this stricter/looser depending on your needs).
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return url

async def resolve_url(playwright, original_url: str) -> str | None:
    """
    Open the URL with Playwright, wait for navigation,
    return the final resolved URL.
    """
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    try:
        await page.goto(original_url, timeout=15000, wait_until="domcontentloaded")
        final_url = page.url
        return final_url
    except Exception as e:
        logger.warning(f"⚠️ Failed to resolve {original_url}: {e}")
        return None
    finally:
        await context.close()
        await browser.close()

async def main(limit: int = 200):
    """
    Iterate over channel_domains docs, resolve shorteners,
    update Firestore with resolved + normalized URLs.
    """
    snaps = list(db.collection("channel_domains").stream())
    logger.info(f"🔍 Found {len(snaps)} candidate domain docs")

    async with async_playwright() as pw:
        for snap in snaps:
            doc_id, doc = snap.id, snap.to_dict() or {}

            # skip if already resolved
            if "resolved_url" in doc:
                continue

            orig_url = doc.get("url")
            if not orig_url:
                continue

            final_url = await resolve_url(pw, orig_url)
            if not final_url:
                continue

            normalized = normalize_url(final_url)
            snap.reference.set({
                "resolved_url": final_url,
                "resolved_domain": normalized,
                "resolved_at": datetime.utcnow()
            }, merge=True)
            logger.info(f"✅ {orig_url} → {final_url} ({normalized})")


if __name__ == "__main__":
    asyncio.run(main(limit=50))
