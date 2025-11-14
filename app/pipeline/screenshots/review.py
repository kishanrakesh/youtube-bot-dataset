#!/usr/bin/env python3
"""
Step 3: Manual review of channel screenshots (OpenCV UI).
"""

import logging, os, asyncio
from dotenv import load_dotenv; load_dotenv()
from app.pipeline.channels.scraping import expand_bot_graph_async

from app.pipeline.screenshots.review_ui import fetch_docs, review_docs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    limit = int(os.getenv("REVIEW_LIMIT", "2000"))
    asyncio.run(expand_bot_graph_async(review_docs(fetch_docs(limit=limit))))
