#!/usr/bin/env python3
"""
Step 2: Capture homepage screenshots for channels without screenshots.
"""

import logging, os, asyncio
from dotenv import load_dotenv; load_dotenv()

from app.screenshots.capture_channel_screenshots import fetch_channels_needing_screenshots, save_screenshots

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    limit = int(os.getenv("SCREENSHOT_LIMIT", "5000"))
    parallel_tabs = int(os.getenv("PARALLEL_TABS", "5"))

    docs = fetch_channels_needing_screenshots(limit=limit)
    asyncio.run(save_screenshots(docs, parallel_tabs=parallel_tabs))
