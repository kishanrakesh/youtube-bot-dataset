"""Interactive screenshot review UI for bot detection.

Provides a two-stage review interface:
1. Avatar grid view for quick browsing
2. Full screenshot view for detailed inspection

Uses OpenCV for UI rendering and Firestore for label storage.
"""

import cv2
import logging
import numpy as np
import os
import re
import requests
from datetime import datetime
from typing import List, Dict, Optional

from google.cloud import firestore, storage

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

COLLECTION_NAME = "channel"
AVATAR_SIZE = 128  # px
BUCKET_NAME = os.getenv("SCREENSHOT_BUCKET", "yt-bot-screens")
REVIEW_LIMIT = 200
BATCH_SIZE = 6  # how many screenshots per screen (grid)


# ============================================================================
# GCP Client Initialization
# ============================================================================

_db, _storage, _bucket = None, None, None


def db() -> firestore.Client:
    """Get or create Firestore client.
    
    Returns:
        Initialized Firestore client
    """
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def bucket() -> storage.Bucket:
    """Get or create GCS bucket reference.
    
    Returns:
        Initialized storage bucket
    """
    global _storage, _bucket
    if _storage is None:
        _storage = storage.Client()
        _bucket = _storage.bucket(BUCKET_NAME)
    return _bucket


# ============================================================================
# Image Loading and Processing
# ============================================================================

def load_png(gcs_uri: str, target_crop_h: int = 800) -> Optional[np.ndarray]:
    """Load and crop PNG screenshot from GCS.
    
    Args:
        gcs_uri: GCS URI (gs://bucket/path)
        target_crop_h: Target height to crop to (keeps top portion)
        
    Returns:
        Cropped image as numpy array, or None if failed
    """
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        return None
    bkt, path = gcs_uri[5:].split("/", 1)
    try:
        blob = bucket().client.bucket(bkt).blob(path) if bkt != BUCKET_NAME else bucket().blob(path)
        data = blob.download_as_bytes()
        arr  = np.frombuffer(data, dtype=np.uint8)
        img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if img is not None:
            h, w = img.shape[:2]

            # Ensure target_crop_h doesn’t exceed actual height
            crop_h = min(target_crop_h, h)

            # Crop bottom off → keep top portion (banner + avatar + title + first row of featured channels)
            img = img[0:crop_h, :]

        return img
    except Exception as e:
        LOGGER.warning("⚠️ Failed to load %s: %s", gcs_uri, e)
        return None


# ============================================================================
# Firestore Query
# ============================================================================

def fetch_docs(limit: int = 200) -> List[firestore.DocumentSnapshot]:
    """Fetch channel documents needing manual review.
    
    Queries for channels with screenshots but no bot labels yet,
    sorted by bot probability (highest first).
    
    Args:
        limit: Maximum number of documents to fetch
        
    Returns:
        List of Firestore document snapshots
    """
    snaps = (
        db.collection(COLLECTION_NAME)
          .where("is_screenshot_stored", "==", True)
          .where("is_bot_checked", "==", False)
          .limit(limit)
          .stream()
    )

    docs = list(snaps)

    # Sort using avatar_metrics.bot_probability
    docs.sort(
        key=lambda snap: (snap.to_dict().get("avatar_metrics", {}).get("bot_probability", 0.0)),
        reverse=True
    )

    LOGGER.info("Fetched %d docs for manual review", len(docs))
    return docs


# ============================================================================
# Batch Preprocessing
# ============================================================================

def preprocess_docs(
    docs: List[firestore.DocumentSnapshot],
    batch_size: int = 6,
    width: int = 800,
    crop_h: int = 800,
    cols: int = 2
) -> tuple:
    """Download, resize, crop, and compose batches into grid images.
    
    Prepares screenshot batches for display in the review UI by loading
    images from GCS, resizing them, and arranging them in a grid layout.
    
    Args:
        docs: List of Firestore document snapshots
        batch_size: Number of screenshots per batch
        width: Target width for each screenshot
        crop_h: Target height to crop each screenshot to
        cols: Number of columns in grid layout
        
    Returns:
        Tuple of (batches, coords_per_batch) where:
            - batches: List of grid images (numpy arrays)
            - coords_per_batch: List of coordinate maps for click detection
    """
    batches = []
    coords_per_batch = []
    total = len(docs)

    LOGGER.info(f"📥 Preprocessing {total} docs into batches of {batch_size}...")

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        imgs, coords_map = [], {}
        row_imgs, row_idxs, row_max_h, rows, y_off = [], [], 0, [], 0

        LOGGER.info(f"⚙️  Processing batch {start//batch_size + 1} "
                    f"({start+1}–{end} of {total})")

        for idx in range(start, end):
            snap = docs[idx]
            gcs_uri = snap.get("screenshot_gcs_uri")
            img = load_png(gcs_uri)

            if img is None:
                LOGGER.warning(f"⚠️ Missing image for doc {idx} ({gcs_uri})")
                img = np.ones((crop_h, width, 3), np.uint8) * 240
                cv2.putText(img, "missing", (20, crop_h//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
            else:
                # resize + crop
                h, w = img.shape[:2]
                scale = width / w
                img = cv2.resize(img, (width, int(h * scale)))

                # crop height
                if img.shape[0] > crop_h:
                    img = img[:crop_h, :]

                # 🔹 crop width (remove side margins)
                side_crop = int(img.shape[1] * 0.05)  # 5% from each side
                if side_crop > 0:
                    img = img[:, side_crop:-side_crop]


            row_imgs.append(img); row_idxs.append(idx)
            row_max_h = max(row_max_h, img.shape[0])

            # 🔹 flush row when it's full (cols) or last image
            if len(row_imgs) == cols or idx == end - 1:
                row_w = sum(im.shape[1] for im in row_imgs) + (len(row_imgs)-1)*8
                row = np.ones((row_max_h, row_w, 3), np.uint8) * 255
                x = 0
                for im, idxx in zip(row_imgs, row_idxs):
                    h, w = im.shape[:2]
                    row[0:h, x:x+w] = im
                    coords_map[idxx] = (x, y_off, w, h)
                    x += w + 8
                rows.append(row)
                y_off += row_max_h + 8
                row_imgs, row_idxs, row_max_h = [], [], 0

        # pad rows to same width before stacking
        max_w = max(r.shape[1] for r in rows)
        padded_rows = []
        for r in rows:
            if r.shape[1] < max_w:
                pad = np.ones((r.shape[0], max_w - r.shape[1], 3), np.uint8) * 255
                r = np.hstack([r, pad])
            padded_rows.append(r)

        grid = padded_rows[0] if len(padded_rows) == 1 else np.vstack(padded_rows)
        batches.append(grid)
        coords_per_batch.append(coords_map)

        LOGGER.info(f"✅ Finished batch {start//batch_size + 1} "
                    f"({len(batches)} total so far)")

    LOGGER.info(f"🎉 Preprocessing complete: {len(batches)} batches created.")
    return batches, coords_per_batch


# ============================================================================
# Helper Utilities
# ============================================================================

# Initialize GCP clients for helper functions
_db_client = firestore.Client()
_storage_client = storage.Client()
_bucket_client = _storage_client.bucket("yt-bot-screens")


def upgrade_avatar_url(url: str, target_size: int = 256) -> str:
    """Convert low-resolution avatar URL to higher resolution.
    
    YouTube avatar URLs contain size parameters (e.g., s88-c-k-c0x00ffffff-no-rj).
    This function replaces the size component to request higher resolution avatars.
    
    Args:
        url: Original avatar URL
        target_size: Desired size in pixels (default: 256)
        
    Returns:
        Modified URL with higher resolution parameters
    """
    if not url:
        return url
    return re.sub(r"=s\d+-", f"=s{target_size}-", url)


def download_image(url: str, size: int = AVATAR_SIZE) -> np.ndarray:
    """Download avatar from URL and resize to square.
    
    Fetches the avatar image from a YouTube URL, upgrades it to higher
    resolution, and resizes it to the specified size.
    
    Args:
        url: Avatar image URL
        size: Target size for square avatar (default: AVATAR_SIZE constant)
        
    Returns:
        Resized avatar image as numpy array, or gray placeholder on failure
    """
    if not url:
        return np.ones((size, size, 3), np.uint8) * 200
    try:
        url = upgrade_avatar_url(url, 256)  # force higher-res avatar
        resp = requests.get(url, timeout=5)
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("decode failed")
        img = cv2.resize(img, (size, size))
        return img
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to load avatar {url}: {e}")
        return np.ones((size, size, 3), np.uint8) * 200


def download_screenshot(gcs_uri: str, max_w: int = 1200) -> Optional[np.ndarray]:
    """Fetch full screenshot from GCS.
    
    Downloads a channel screenshot from Google Cloud Storage and optionally
    resizes it to fit within the specified maximum width.
    
    Args:
        gcs_uri: GCS URI (e.g., gs://bucket/path/to/image.png)
        max_w: Maximum width to resize to (default: 1200)
        
    Returns:
        Screenshot image as numpy array, or None if download fails
    """
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        return None
    bkt, path = gcs_uri[5:].split("/", 1)
    blob = (_storage_client.bucket(bkt).blob(path) 
            if bkt != _bucket_client.name else _bucket_client.blob(path))
    data = blob.download_as_bytes()
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is not None and img.shape[1] > max_w:
        scale = max_w / img.shape[1]
        img = cv2.resize(img, (max_w, int(img.shape[0]*scale)))
    return img


# ============================================================================
# Main Review UI
# ============================================================================

def review_docs(docs: List[firestore.DocumentSnapshot]) -> set:
    """Interactive two-stage UI for manual bot detection review.
    
    Provides a two-stage review process:
    1. Avatar grid view: Browse channels quickly
    2. Screenshot view: Click an avatar to see full screenshot and label
    
    Controls:
    - Click avatar: Open full screenshot
    - b/n in screenshot view: Mark as bot/not-bot
    - k/j in grid: Next/previous page
    - q: Quit and save labels
    
    Args:
        docs: List of Firestore channel documents to review
        
    Returns:
        Set of channel IDs that were labeled
    """
    if not docs:
        LOGGER.info("No docs to review")
        return

    # Preload avatars
    avatars = []
    for snap in docs:
        url = snap.get("avatar_url")
        avatars.append(download_image(url))

    selected: Dict[str, bool] = {}   # channel_id → is_bot
    seen: set[str] = set()           # all channels shown in any grid
    index, cols, rows = 0, 2, 2
    page_size = cols * rows


    WIN = "Annotate (click avatar → inspect; q quit)"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)

    def render_grid():
        """Render 3×3 avatar grid with overlays and update seen set."""
        tiles = []
        for i in range(index, min(index+page_size, len(docs))):
            snap = docs[i]
            cid = snap.id
            seen.add(cid)   # mark as seen
            img = avatars[i].copy()

            # overlay if labeled
            if cid in selected:
                color = (0,255,0) if selected[cid] is False else (0,0,255)
                cv2.rectangle(img, (0,0), (AVATAR_SIZE-1, AVATAR_SIZE-1), color, 3)

            tiles.append((img, cid))

        # arrange grid
        # arrange grid
        grid_rows = []
        for r in range(0, len(tiles), cols):
            row_imgs = [t[0] for t in tiles[r:r+cols]]
            row = np.hstack(row_imgs)
            grid_rows.append(row)

        # 🔹 Pad rows to same width
        max_w = max(r.shape[1] for r in grid_rows)
        padded_rows = []
        for r in grid_rows:
            if r.shape[1] < max_w:
                pad = np.ones((r.shape[0], max_w - r.shape[1], 3), np.uint8) * 255
                r = np.hstack([r, pad])
            padded_rows.append(r)

        grid = np.vstack(padded_rows)
        cv2.imshow(WIN, grid)


        # build coords map
        coords_map = {}
        i = 0
        for r in range(rows):
            for c in range(cols):
                idx = index + i
                if idx >= len(docs): break
                cid = docs[idx].id
                coords_map[cid] = (c*AVATAR_SIZE, r*AVATAR_SIZE, AVATAR_SIZE, AVATAR_SIZE)
                i += 1
        return coords_map

    coords_map = render_grid()

    def mouse_click(event, x, y, flags, param):
        nonlocal coords_map
        if event == cv2.EVENT_LBUTTONDOWN:
            for cid, (ix, iy, iw, ih) in coords_map.items():
                if ix <= x < ix+iw and iy <= y < iy+ih:
                    # Stage 2: show screenshot
                    snap = _db_client.collection(COLLECTION_NAME).document(cid).get()
                    gcs_uri = snap.get("screenshot_gcs_uri")
                    big = download_screenshot(gcs_uri)
                    if big is None:
                        LOGGER.warning("⚠️ No screenshot for %s", cid)
                        return

                    cv2.namedWindow("Screenshot view (b=bot, n=not, esc=back)", cv2.WINDOW_NORMAL)
                    cv2.imshow("Screenshot view (b=bot, n=not, esc=back)", big)

                    while True:
                        k = cv2.waitKey(0)
                        if k == ord("b"):
                            selected[cid] = True
                            break
                        elif k == ord("n"):
                            selected[cid] = False
                            break
                        elif k == 27:  # esc
                            break

                    cv2.destroyWindow("Screenshot view (b=bot, n=not, esc=back)")
                    coords_map = render_grid()
                    break

    cv2.setMouseCallback(WIN, mouse_click)

    while True:
        k = cv2.waitKey(0)
        if k == ord("q"): break
        elif k == ord("k"):  # next page
            if index+page_size < len(docs):
                index += page_size
                coords_map = render_grid()
        elif k == ord("j"):  # prev page
            if index-page_size >= 0:
                index -= page_size
                coords_map = render_grid()

    cv2.destroyAllWindows()

    # Write back: all seen channels get labeled
    batch = _db_client.batch()
    now = datetime.now()
    for snap in docs:
        cid = snap.id
        if cid not in seen:
            continue  # untouched if never viewed

        label = selected.get(cid, False)  # default False if not explicitly labeled
        doc_ref = snap.reference
        batch.update(doc_ref, {
            "is_bot": label,
            "is_bot_check_type": "manual",
            "is_bot_checked": True,
            "is_bot_set_at": now,
            "last_checked_at": now,
        })
    batch.commit()
    LOGGER.info(f"✅ Wrote {len(seen)} labels to Firestore "
                f"{selected.values()}, "
                f"(bots={sum(1 for v in selected.values() if v)}, "
                f"not_bots={len(seen)-sum(1 for v in selected.values() if v)})")
    
    return selected.keys()
