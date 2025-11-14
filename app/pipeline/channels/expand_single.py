#!/usr/bin/env python3
"""Expand the bot graph for one or more specific channels.

This entrypoint is designed to run immediately after manual review/annotation
so newly discovered channels (IDs or handles) can be expanded and backfilled
without waiting for the nightly job.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import List

from app.pipeline.channels.scraping import (
    expand_bot_graph_async,
    resolve_handle_to_id,
)
from app.utils.clients import get_youtube

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def _normalize_identifiers(identifiers: List[str], use_api: bool) -> List[str]:
    """Normalize identifiers, resolving handles when API mode is enabled."""
    cleaned: List[str] = []
    if not identifiers:
        return cleaned

    youtube = get_youtube() if use_api else None

    for raw_identifier in identifiers:
        identifier = raw_identifier.strip()
        if not identifier:
            continue

        if identifier.startswith("@") and use_api and youtube:
            resolved = resolve_handle_to_id(youtube, identifier)
            if resolved:
                LOGGER.info("🔁 Resolved handle %s → %s", identifier, resolved)
                cleaned.append(resolved)
                continue
            LOGGER.warning(
                "⚠️ Unable to resolve handle %s via API; falling back to scraping",
                identifier,
            )
            cleaned.append(identifier)
        else:
            cleaned.append(identifier)

    return cleaned


def main(identifiers: List[str], use_api: bool) -> None:
    """Expand the bot graph for the provided identifiers."""
    seeds = _normalize_identifiers(identifiers, use_api=use_api)
    if not seeds:
        LOGGER.error("❌ No valid identifiers supplied")
        return

    LOGGER.info(
        "🚀 Starting targeted expansion for %d identifier(s) (API mode=%s)",
        len(seeds),
        use_api,
    )
    asyncio.run(expand_bot_graph_async(seeds, use_api=use_api))


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Expand the bot graph for specific channel IDs or handles",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "identifiers",
        nargs="+",
        help="Channel IDs (UC...) or handles (@username) to seed the expansion",
    )
    parser.add_argument(
        "--use-api",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the YouTube Data API for metadata (disable to scrape only)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = _parse_args()
    main(cli_args.identifiers, cli_args.use_api)
