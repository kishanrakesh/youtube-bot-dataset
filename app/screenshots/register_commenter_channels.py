#!/usr/bin/env python3
"""
Register commenter channels OR backfill bot probabilities for existing channels.
"""

import logging
from datetime import datetime
from typing import Optional, Set
import os

from google.cloud import firestore
from app.utils.gcs_utils import read_json_from_gcs
from app.utils.image_processing import classify_avatar_url, get_xgb_model

LOGGER = logging.getLogger("register_commenters")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

COLLECTION_NAME = "channel"
LIKE_THRESHOLD  = 5  # only include commenters with >=10 likes


from app.pipeline.expand_bot_graph import PlaywrightContext, scrape_about_page

import asyncio

async def register_commenter_channels(bucket: str, gcs_paths: list[str], limit: int = None, concurrency: int = 10) -> None:
    db = firestore.Client()
    seen: Set[str] = set()
    total_new = 0
    model = get_xgb_model()

    async with PlaywrightContext() as context:
        sem = asyncio.Semaphore(concurrency)  # limit concurrent scrapes

        for path_idx, gcs_path in enumerate(gcs_paths, start=1):
            if limit and total_new >= limit:
                LOGGER.info(f"⚠️ Reached limit ({limit}) — stopping early.")
                break

            data = read_json_from_gcs(bucket, gcs_path)
            items = data.get("items", []) if data else []

            async def process_thread(thread):
                nonlocal total_new
                top_snip = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                if "authorChannelId" not in top_snip or top_snip.get("likeCount", 0) < LIKE_THRESHOLD:
                    return None

                cid = top_snip["authorChannelId"]["value"]
                if cid in seen:
                    return None
                seen.add(cid)

                async with sem:  # limit concurrency
                    batch = db.batch()
                    added = await _init_channel_doc(
                        context, batch, db, cid,
                        top_snip.get("authorProfileImageUrl"),
                        model
                    )
                    if added:
                        batch.commit()
                        total_new += 1
                        LOGGER.info(f"✅ Added {cid}")
                        return cid
                return None

            # Run all threads concurrently (within concurrency limit)
            await asyncio.gather(*[
                process_thread(thread)
                for thread in items
            ])

            LOGGER.info(f"── {path_idx}/{len(gcs_paths):<3} "
                        f"{os.path.basename(gcs_path):<15} "
                        f"→ total so far: {total_new}")

    LOGGER.info(f"🎉 Done! {total_new} total new channels registered.")




async def _init_channel_doc(context, batch, db, cid: str, avatar_url: Optional[str], model) -> bool:
    doc_ref = db.collection(COLLECTION_NAME).document(cid)
    if doc_ref.get().exists:
        return False


    # --- Process avatar ---
    label = "MISSING"
    metrics = {}
    if avatar_url:
        try:
            label, metrics = classify_avatar_url(avatar_url, size=128, model=model)
            if label == "DEFAULT":
                LOGGER.info(f"🚫 Skipping default avatar {cid}")
                return False
        except Exception as e:
            LOGGER.warning(f"⚠️ Avatar classification failed for {cid}: {e}")

    # --- Scrape links & featured ---
    about_links, subs = await scrape_about_page(context, cid)

    if not about_links and not subs:
        LOGGER.info(f"⏭️ Skipping https://www.youtube.com/channel/{cid} — no links or featured channels found")
        return False

    # --- Store channel ---
    batch.set(doc_ref, {
        "channel_id": cid,
        "avatar_url": avatar_url,
        "avatar_label": label,
        "avatar_metrics": metrics,
        "about_links_count": len(about_links),
        "featured_channels_count": len(subs),
        "is_screenshot_stored": False,
        "is_bot_checked": False,
        "registered_at": datetime.utcnow(),
    })
    return True


# def register_commenter_channels(bucket: str, gcs_paths: list[str]) -> None:
#     db = firestore.Client()
#     seen: Set[str] = set()
#     total_new = 0
#     model = get_xgb_model()

#     for path_idx, gcs_path in enumerate(gcs_paths, start=1):
#         data = read_json_from_gcs(bucket, gcs_path)
#         items = data.get("items", []) if data else []
#         num_threads = len(items)

#         batch = db.batch()
#         new_this_file = 0

#         for thread in items:
#             top_snip = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
#             if "authorChannelId" in top_snip and top_snip.get("likeCount", 0) >= LIKE_THRESHOLD:
#                 cid = top_snip["authorChannelId"]["value"]
#                 if cid not in seen:
#                     seen.add(cid)
#                     _init_channel_doc(batch, db, cid, top_snip.get("authorProfileImageUrl"), model)
#                     new_this_file += 1

#             for reply in thread.get("replies", {}).get("comments", []):
#                 snip = reply.get("snippet", {})
#                 if "authorChannelId" in snip and snip.get("likeCount", 0) >= LIKE_THRESHOLD:
#                     cid = snip["authorChannelId"]["value"]
#                     if cid not in seen:
#                         seen.add(cid)
#                         _init_channel_doc(batch, db, cid, snip.get("authorProfileImageUrl"), model)
#                         new_this_file += 1

#         LOGGER.info(f"── {path_idx}/{len(gcs_paths):<3} "
#                     f"{os.path.basename(gcs_path):<15} "
#                     f"({num_threads:>3} threads) → {new_this_file} new channels")

#         if new_this_file:
#             batch.commit()
#             total_new += new_this_file

#     LOGGER.info(f"🎉 Finished: {len(gcs_paths)} files, {total_new} total new channels (≥{LIKE_THRESHOLD} likes)")


def backfill_bot_probabilities(limit: int = 5000):
    """Recompute bot_probability for existing channels missing it."""
    db = firestore.Client()
    model = get_xgb_model()
    snaps = db.collection(COLLECTION_NAME).limit(limit).stream()

    batch = db.batch()
    updated = 0

    for snap in snaps:
        doc = snap.to_dict() or {}
        metrics = doc.get("avatar_metrics", {})
        if not metrics or metrics.get("has_bot_probability"):
            continue

        avatar_url = doc.get("avatar_url")
        if not avatar_url:
            continue

        try:
            label, new_metrics = classify_avatar_url(avatar_url, size=128, model=model)
            metrics.update(new_metrics)
            metrics["has_bot_probability"] = True
            doc_ref = db.collection(COLLECTION_NAME).document(snap.id)
            batch.update(doc_ref, {"avatar_metrics": metrics, "avatar_label": label})
            updated += 1

            if updated % 100 == 0:
                batch.commit()
                batch = db.batch()
                LOGGER.info(f"✅ Updated {updated} so far...")
        except Exception as e:
            LOGGER.warning(f"⚠️ Failed to backfill {snap.id}: {e}")

    if updated:
        batch.commit()
    LOGGER.info(f"🎉 Backfill finished: {updated} channels updated with bot_probability")


# def _init_channel_doc(batch, db, cid: str, avatar_url: Optional[str], model) -> None:
#     doc_ref = db.collection(COLLECTION_NAME).document(cid)
#     if doc_ref.get().exists:
#         return

#     label = "MISSING"
#     metrics = {}
#     if avatar_url:
#         try:
#             label, metrics = classify_avatar_url(avatar_url, size=128, model=model)
#             if label == "DEFAULT":
#                 LOGGER.info(f"🚫 Skipping default avatar {cid}")
#                 return
#         except Exception as e:
#             LOGGER.warning(f"⚠️ Avatar classification failed for {cid}: {e}")

#     batch.set(doc_ref, {
#         "channel_id": cid,
#         "avatar_url": avatar_url,
#         "avatar_label": label,
#         "avatar_metrics": metrics,
#         "is_screenshot_stored": False,
#         "is_bot_checked": False,
#         "registered_at": datetime.utcnow(),
#     })


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Register or backfill commenter channels with bot probabilities.")
    parser.add_argument("--bucket", help="GCS bucket name")
    parser.add_argument("--gcs_paths", nargs="*", help="Paths to video_comments/raw/*.json")
    parser.add_argument("--backfill", action="store_true", help="Run in backfill mode")

    args = parser.parse_args()

    if args.backfill:
        backfill_bot_probabilities()
    else:
        if not args.bucket or not args.gcs_paths:
            raise SystemExit("❌ Need --bucket and --gcs_paths unless --backfill is used")
        register_commenter_channels(args.bucket, args.gcs_paths)
