#!/usr/bin/env python3
"""Manual review of channel screenshots using OpenCV UI."""

import argparse
import asyncio
import logging
import os
from dotenv import load_dotenv

from app.pipeline.channels.scraping import expand_bot_graph_async
from app.pipeline.screenshots.review_ui import fetch_docs, review_docs

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def main(limit: int) -> None:
    """Launch the manual review UI for channel screenshots."""
    LOGGER.info(f"👀 Launching manual review UI with limit={limit}")
    asyncio.run(expand_bot_graph_async(review_docs(fetch_docs(limit=limit))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review channel screenshots manually")
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("REVIEW_LIMIT", "2000")),
        help="Maximum number of screenshots to review"
    )
    
    args = parser.parse_args()
    main(limit=args.limit)
