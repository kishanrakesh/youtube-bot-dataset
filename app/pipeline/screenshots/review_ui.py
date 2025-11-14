#review_channel_screenshots.py

import cv2, numpy as np, logging, os, requests
from typing import List, Dict
from google.cloud import firestore, storage
import re
from datetime import datetime

LOGGER = logging.getLogger("review")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


LOGGER = logging.getLogger("avatar_annotator")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

COLLECTION_NAME = "channel"
AVATAR_SIZE = 128  # px

BUCKET_NAME     = os.getenv("SCREENSHOT_BUCKET", "yt-bot-screens")
REVIEW_LIMIT    = 200
BATCH_SIZE      = 6   # how many screenshots per screen (grid)

# ───── GCP clients ─────
_db, _storage, _bucket = None, None, None
def db():
    global _db
    if _db is None: _db = firestore.Client()
    return _db
def bucket():
    global _storage, _bucket
    if _storage is None:
        _storage = storage.Client()
        _bucket = _storage.bucket(BUCKET_NAME)
    return _bucket

# ───── GCS → OpenCV ─────
def load_png(gcs_uri: str, target_crop_h: int = 800):
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

    
# ───── Firestore query ─────
def fetch_docs(limit=200):
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



def preprocess_docs(docs, batch_size=6, width=800, crop_h=800, cols=2):
    """Download, resize, crop, and precompose batches into grid images."""
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




# ───── GUI loop ─────
# def review_docs(docs: List[firestore.DocumentSnapshot]):
#     if not docs:
#         LOGGER.info("Nothing to review.")
#         return

#     # 🔹 Preload everything into memory
#     batches, coords_per_batch = preprocess_docs(docs, batch_size=4, width=1000, crop_h=1000)

#     WIN = "Annotate (click = bot, k next, j back, q quit)"
#     selected: set[int] = set()
#     index = 0  # current batch index

#     cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)

#     def render_and_show():
#         """Show the preloaded grid with red rectangles on selected items."""
#         grid = batches[index].copy()
#         coords_map = coords_per_batch[index]
#         for idx in coords_map:
#             if idx in selected:
#                 x, y, w, h = coords_map[idx]
#                 cv2.rectangle(grid, (x, y), (x+w-1, y+h-1), (0, 0, 255), 8)
#         cv2.imshow(WIN, grid)
#         return coords_map

#     coords_map = render_and_show()

#     def mouse_click(event, x, y, flags, param):
#         nonlocal coords_map, selected
#         if event == cv2.EVENT_LBUTTONDOWN:
#             for idx, (ix, iy, iw, ih) in coords_map.items():
#                 if ix <= x < ix+iw and iy <= y < iy+ih:
#                     if idx in selected:
#                         selected.remove(idx)
#                     else:
#                         selected.add(idx)
#                     coords_map = render_and_show()
#                     break

#     cv2.setMouseCallback(WIN, mouse_click)

#     while True:
#         k = cv2.waitKeyEx(0)

#         if k in (ord("q"), 27):  # quit
#             break
#         elif k in (ord("k"),):  # next batch
#             if index < len(batches)-1:
#                 index += 1
#                 coords_map = render_and_show()
#         elif k in (ord("j"),):  # prev batch
#             if index > 0:
#                 index -= 1
#                 coords_map = render_and_show()

#     cv2.destroyAllWindows()

#     # 🔹 Write back only seen docs
#     seen_idxs = set().union(*coords_per_batch[: index+1])  # everything user paged through
#     batch = db().batch()
#     now = firestore.SERVER_TIMESTAMP
#     for i in seen_idxs:
#         snap = docs[i]
#         is_bot = (i in selected)
#         snap.reference.update({
#             "is_bot": is_bot,
#             "is_bot_check_type": "manual",
#             "is_bot_checked": True,
#             "is_bot_set_at": now,
#             "last_checked_at": now,
#         })
#     LOGGER.info(f"✅ Wrote {len(seen_idxs)} labels to Firestore (bots={len(selected)}, not_bots={len(seen_idxs)-len(selected)})")


# ───── Firestore + GCS ─────
db = firestore.Client()
storage_client = storage.Client()
bucket = storage_client.bucket("yt-bot-screens")

def upgrade_avatar_url(url: str, target_size: int = 256) -> str:
    """
    Replace the size component (=sXX-) in a YouTube avatar URL with =s{target_size}-.
    """
    if not url:
        return url
    return re.sub(r"=s\d+-", f"=s{target_size}-", url)

def download_image(url: str, size=AVATAR_SIZE):
    """Download avatar from URL and resize to square."""
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

def download_screenshot(gcs_uri: str, max_w=1200):
    """Fetch full screenshot from GCS."""
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        return None
    bkt, path = gcs_uri[5:].split("/", 1)
    blob = (storage_client.bucket(bkt).blob(path) 
            if bkt != bucket.name else bucket.blob(path))
    data = blob.download_as_bytes()
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is not None and img.shape[1] > max_w:
        scale = max_w / img.shape[1]
        img = cv2.resize(img, (max_w, int(img.shape[0]*scale)))
    return img


def review_docs(docs: List[firestore.DocumentSnapshot]):
    """Stage 1: Avatar grid → Stage 2: Screenshot view."""
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
                    snap = db.collection(COLLECTION_NAME).document(cid).get()
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

    # 🔹 Write back: all seen → at least "not bot"
    batch = db.batch()
    now = datetime.utcnow()
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
