#app/pipeline/backfill_channels.py

#!/usr/bin/env python3
"""
Backfill Firestore channel docs for bots:
- Fetch YouTube channel metadata (snippet, stats, etc.)
- Save raw JSON to GCS
- Ensure high-quality avatar is stored in GCS (PNG)
- Update Firestore with avatar fields, metrics, screenshot, timestamps
"""

import argparse
import os
import tempfile
from datetime import datetime

import cv2
from google.cloud import firestore

from app.utils.clients import get_youtube
from app.utils.gcs_utils import write_json_to_gcs, upload_file_to_gcs
from app.utils.paths import channel_metadata_raw_path
from app.utils.image_processing import (
    classify_avatar_url,
    download_avatar,
    upgrade_avatar_url,
)
from app.utils.logging import get_logger
import re
from typing import Optional, Tuple

HANDLE_RE = re.compile(r"^@?(?P<h>[-_.A-Za-z0-9]{2,64})$")

logger = get_logger()
db = firestore.Client()

GCS_BUCKET_DATA = os.getenv("GCS_BUCKET_DATA")  # required by write_json_to_gcs


# ---------- helpers ----------

def fetch_and_store_channel_metadata(channel_id: str):
    """Fetch channel metadata from YouTube API, store raw JSON in GCS + Firestore."""
    youtube = get_youtube()
    try:
        resp = youtube.channels().list(
            part="id,snippet,statistics,brandingSettings,topicDetails,status,contentDetails",
            id=channel_id,
            maxResults=1
        ).execute()

        items = resp.get("items", [])
        if not items:
            logger.warning(f"⚠️ No channel data for {channel_id}")
            return None
        item = items[0]

        # Save raw JSON to GCS
        if not GCS_BUCKET_DATA:
            logger.error("❌ GCS_BUCKET_DATA not set in env.")
        else:
            write_json_to_gcs(GCS_BUCKET_DATA, channel_metadata_raw_path(channel_id), item)

        # Update Firestore with raw channel data
        db.collection("channel").document(channel_id).set({
            "channel_id": channel_id,
            "channel_data": item,
            "metadata_fetched_at": datetime.utcnow()
        }, merge=True)

        return item
    except Exception as e:
        logger.error(f"❌ Failed to fetch metadata for {channel_id}: {e}")
        return None


def store_avatar_hq(channel_id: str, avatar_url: str) -> tuple[str | None, str | None, int | None]:
    """
    Download avatar at highest practical size, save PNG to GCS.
    Returns (avatar_gcs_uri, avatar_url_used, size_px) or (None, None, None) on failure.
    """
    if not avatar_url:
        return None, None, None

    # Try descending sizes; first successful download wins
    candidate_sizes = [800, 512, 256]
    for size in candidate_sizes:
        try_url = upgrade_avatar_url(avatar_url, size=size)
        img = download_avatar(try_url)
        if img is None:
            continue

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            ok = cv2.imwrite(tmp.name, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if not ok:
                os.unlink(tmp.name)
                continue

            gcs_path = f"channel_avatars/{channel_id}_s{size}.png"
            gcs_uri = upload_file_to_gcs(
                GCS_BUCKET_DATA,   # bucket
                gcs_path,          # remote path in GCS
                tmp.name,          # local file to upload
                content_type="image/png"
            )

        os.unlink(tmp.name)
        logger.info(f"🖼️ Saved HQ avatar → {gcs_uri}")
        return gcs_uri, try_url, size

    # Fallback: try original URL
    img = download_avatar(avatar_url)
    if img is not None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            ok = cv2.imwrite(tmp.name, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if ok:
                gcs_path = f"channel_avatars/{channel_id}_orig.png"
                gcs_uri = upload_file_to_gcs(
                    GCS_BUCKET_DATA,
                    gcs_path,
                    tmp.name,
                    content_type="image/png"
                )

                os.unlink(tmp.name)
                logger.info(f"🖼️ Saved fallback avatar → {gcs_uri}")
                return gcs_uri, avatar_url, int(max(img.shape[:2]))
        os.unlink(tmp.name)

    logger.warning(f"⚠️ Could not download avatar for {channel_id}")
    return None, None, None

def store_banner(channel_id: str, banner_url: str) -> str | None:
    """
    Download banner image and save PNG to GCS.
    Returns GCS URI or None.
    """
    if not banner_url:
        return None
    try:
        img = download_avatar(banner_url)  # reuse your downloader
        if img is None:
            return None

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            ok = cv2.imwrite(tmp.name, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if not ok:
                os.unlink(tmp.name)
                return None

            gcs_path = f"channel_banners/{channel_id}.png"
            gcs_uri = upload_file_to_gcs(
                GCS_BUCKET_DATA,
                gcs_path,
                tmp.name,
                content_type="image/png"
            )

        os.unlink(tmp.name)
        logger.info(f"🖼️ Saved banner → {gcs_uri}")
        return gcs_uri
    except Exception as e:
        logger.error(f"❌ Failed to store banner for {channel_id}: {e}")
        return None


def normalize_handle(identifier: str) -> Optional[str]:
    """Return handle text (without @) if identifier looks like a handle; else None."""
    if not identifier or identifier.startswith("UC"):
        return None
    m = HANDLE_RE.match(identifier)
    return m.group("h") if m else None

def fetch_channel_by_identifier(identifier: str) -> Optional[dict]:
    """
    Fetch channel metadata either by UC id or by handle.
    - If identifier starts with 'UC', use channels.list(id=...)
    - Otherwise, use channels.list(forHandle=...) (fallback to search if needed)
    Returns the channel item dict, or None.
    """
    youtube = get_youtube()
    try:
        if identifier.startswith("UC"):
            resp = youtube.channels().list(
                part="id,snippet,statistics,brandingSettings,topicDetails,status,contentDetails",
                id=identifier, maxResults=1
            ).execute()
        else:
            handle = normalize_handle(identifier)
            if not handle:
                return None
            # Prefer forHandle (more precise & cheaper than search)
            resp = youtube.channels().list(
                part="id,snippet,statistics,brandingSettings,topicDetails,status,contentDetails",
                forHandle=handle, maxResults=1
            ).execute()
            if not resp.get("items"):
                # Fallback: search (some older/edge cases)
                sr = youtube.search().list(
                    part="snippet", q=handle, type="channel", maxResults=1
                ).execute()
                items = sr.get("items", [])
                if not items:
                    return None
                ch_id = items[0]["snippet"]["channelId"]
                resp = youtube.channels().list(
                    part="id,snippet,statistics,brandingSettings,topicDetails,status,contentDetails",
                    id=ch_id, maxResults=1
                ).execute()

        items = resp.get("items", [])
        return items[0] if items else None
    except Exception as e:
        logger.error(f"❌ fetch_channel_by_identifier({identifier}) failed: {e}")
        return None

def merge_scraped_fields(dest: dict, src: dict, keys=("screenshot_gcs_uri","avatar_url","avatar_gcs_uri")):
    """Copy over known scraped fields if present."""
    for k in keys:
        if src.get(k) and k not in dest:
            dest[k] = src[k]

def capture_screenshot(channel_id: str, avatar_url: str) -> str | None:
    """
    Save the avatar as a 'screenshot' (JPEG) in GCS.
    """
    try:
        img = download_avatar(avatar_url)
        if img is None:
            logger.warning(f"⚠️ Could not download avatar for {channel_id}")
            return None

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            gcs_uri = upload_file_to_gcs(
                GCS_BUCKET_DATA,
                f"screenshots/{channel_id}.jpg",  # remote path
                tmp.name,                         # local file
                content_type="image/jpeg"
            )

        os.unlink(tmp.name)
        return gcs_uri
    except Exception as e:
        logger.error(f"❌ Failed to capture screenshot for {channel_id}: {e}")
        return None

def fill_missing_metadata_in_channel(limit: int = 500):
    q = db.collection("channel").where("channel_data", "==", None).limit(limit)
    docs = list(q.stream())
    logger.info(f"🔧 Found {len(docs)} channel docs missing metadata")
    for snap in docs:
        doc_id, doc = snap.id, snap.to_dict() or {}
        item = fetch_channel_by_identifier(doc_id)
        if not item: 
            continue
        if GCS_BUCKET_DATA:
            write_json_to_gcs(GCS_BUCKET_DATA, channel_metadata_raw_path(doc_id), item)
        snap.reference.set({
            "channel_id": doc_id,
            "channel_data": item,
            "metadata_fetched_at": datetime.utcnow()
        }, merge=True)
        backfill_channel(doc_id, {**doc, "channel_data": item})


def migrate_collection_identifiers(collection_name: str, *, limit: int = 1000, force_avatars: bool = False):
    """
    Scan {collection_name} for docs whose id is a *handle* (not UC…),
    fetch channel by handle, then write a canonical channel doc under the UC id.
    Copies scraped fields, saves raw JSON, then calls backfill_channel(..).
    """
    col = db.collection(collection_name)
    docs = list(col.limit(limit).stream())
    logger.info(f"🔎 Scanning {collection_name} ({len(docs)}) for handle-ids…")

    promoted = 0
    for snap in docs:
        doc_id = snap.id
        if doc_id.startswith("UC"):
            continue  # already canonical

        doc = snap.to_dict() or {}
        # 1) fetch by identifier (handle or UC)
        item = fetch_channel_by_identifier(doc_id)
        if not item:
            logger.info(f"   ⚠️ No API data for '{doc_id}' (skip)")
            continue

        uc_id = item["id"]
        # 2) save raw json in GCS + merge to canonical channel doc
        if GCS_BUCKET_DATA:
            write_json_to_gcs(GCS_BUCKET_DATA, channel_metadata_raw_path(uc_id), item)

        updates = {
            "channel_id": uc_id,
            "channel_data": item,
            "metadata_fetched_at": datetime.utcnow(),
            "is_metadata_missing": False,
            "registered_at": doc.get("registered_at", datetime.utcnow()),
            "last_checked_at": datetime.utcnow(),
        }
        merge_scraped_fields(updates, doc)

        db.collection("channel").document(uc_id).set(updates, merge=True)
        logger.info(f"⬆️  Promoted {collection_name}/{doc_id} → channel/{uc_id}")

        # 3) run the usual backfill to ensure avatar HQ, metrics, screenshot, etc.
        backfill_channel(uc_id, db.collection("channel").document(uc_id).get().to_dict(), force_avatars=force_avatars)

        # 4) mark original doc as migrated (don’t delete automatically)
        snap.reference.set({
            "migrated_to": uc_id,
            "migrated_at": datetime.utcnow()
        }, merge=True)

        promoted += 1

    logger.info(f"✅ Migrated {promoted} doc(s) from {collection_name}")


# ---------- main backfill ----------

def backfill_channel(doc_id: str, doc: dict, *, force_avatars: bool = False):
    """Fill missing fields for a bot channel (including high-quality avatar in GCS)."""
    logger.info(f"🔄 Backfilling {doc_id}...")

    updates = {}
    now = datetime.utcnow()

    # Step 1: fetch metadata if missing
    channel_data = doc.get("channel_data")
    if not channel_data:
        channel_data = fetch_and_store_channel_metadata(doc_id)
    if not channel_data:
        return

    # Step 2: ensure avatar_url
    avatar_url = doc.get("avatar_url")
    if not avatar_url:
        # Prefer 'high' then 'medium' then 'default'
        thumbs = channel_data.get("snippet", {}).get("thumbnails", {})
        avatar_url = (
            thumbs.get("high", {}).get("url") or
            thumbs.get("medium", {}).get("url") or
            thumbs.get("default", {}).get("url")
        )
        if avatar_url:
            updates["avatar_url"] = avatar_url

    # Step 3: ensure HQ avatar is stored to GCS (+ fields)
    need_hq = force_avatars or (not doc.get("avatar_gcs_uri"))
    if avatar_url and need_hq:
        avatar_gcs_uri, avatar_url_used, size_px = store_avatar_hq(doc_id, avatar_url)
        if avatar_gcs_uri:
            updates["avatar_gcs_uri"] = avatar_gcs_uri
            if avatar_url_used:
                updates["avatar_url_hq"] = avatar_url_used
            if size_px:
                updates["avatar_size_px"] = size_px
    
    banner_url = channel_data.get("brandingSettings", {}).get("image", {}).get("bannerExternalUrl")
    if banner_url and not doc.get("banner_gcs_uri"):
        gcs_uri = store_banner(doc_id, banner_url)
        if gcs_uri:
            updates["banner_url"] = banner_url
            updates["banner_gcs_uri"] = gcs_uri

    # Step 4: metrics (compute once; uses avatar_url; you can switch to avatar_url_hq if you prefer)
    if (avatar_url or updates.get("avatar_url")) and not doc.get("metrics"):
        try:
            url_for_metrics = updates.get("avatar_url_hq") or avatar_url
            print(url_for_metrics)
            _, metrics = classify_avatar_url(url_for_metrics, size=256)
            print(metrics)
            updates["metrics"] = metrics
        except Exception as e:
            logger.warning(f"⚠️ Could not compute metrics for {doc_id}: {e}")

    # Step 5: (Optional) legacy screenshot path populated from avatar
    if (avatar_url or updates.get("avatar_url")) and not doc.get("screenshot_gcs_uri"):
        url_for_shot = updates.get("avatar_url_hq") or avatar_url
        gcs_uri = capture_screenshot(doc_id, url_for_shot)
        if gcs_uri:
            updates["screenshot_gcs_uri"] = gcs_uri

    # Step 6: timestamps
    updates["is_bot_set_at"] = doc.get("is_bot_set_at", now)
    updates["last_checked_at"] = now
    updates["registered_at"] = doc.get("registered_at", now)

    if updates:
        db.collection("channel").document(doc_id).set(updates, merge=True)
        logger.info(f"✅ Updated {doc_id} with {list(updates.keys())}")
    else:
        logger.info(f"ℹ️ Nothing to update for {doc_id}")


def backfill_all_bots(force_avatars: bool = False):
    """Iterate over all bots in Firestore and backfill missing data."""
    bots = db.collection("channel").where("is_bot", "==", True).stream()
    for i, snap in enumerate(bots, 1):
        backfill_channel(snap.id, snap.to_dict(), force_avatars=force_avatars)
        if i % 20 == 0:
            logger.info(f"⏳ Processed {i} bots...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill Firestore bot channels with metadata, screenshots, metrics, HQ avatars.")
    parser.add_argument("--one", help="Backfill a single channel ID instead of all bots")
    parser.add_argument("--force-avatars", action="store_true", help="Re-download and overwrite avatar_gcs_uri even if present")

    # NEW: migrate handle-ids from both collections
    parser.add_argument("--migrate-handles", action="store_true", help="Promote handle-id docs in channel and channel_pending to canonical UC channel docs")
    parser.add_argument("--migrate-limit", type=int, default=1000, help="Max docs to scan per collection during migration")
    parser.add_argument("--fill-missing-meta", action="store_true", help="Fill channel_data for UC docs that lack it")

    args = parser.parse_args()

    if args.migrate_handles:
        migrate_collection_identifiers("channel", limit=args.migrate_limit, force_avatars=args.force_avatars)
        migrate_collection_identifiers("channel_pending", limit=args.migrate_limit, force_avatars=args.force_avatars)

    if args.fill_missing_meta:
        fill_missing_metadata_in_channel()

    if args.one:
        snap = db.collection("channel").document(args.one).get()
        if snap.exists:
            backfill_channel(snap.id, snap.to_dict(), force_avatars=args.force_avatars)
        else:
            logger.error(f"❌ Channel {args.one} not found in Firestore")
    else:
        backfill_all_bots(force_avatars=args.force_avatars)
