import re, cv2, numpy as np, requests, joblib, os
from app.analysis.classifier_utils import score_with_pca_kmeans

_MODEL = None
def get_xgb_model(model_path="xgb_bot_model.pkl"):
    global _MODEL
    if _MODEL is None:
        if os.path.exists(model_path):
            _MODEL = joblib.load(model_path)
        else:
            print(f"⚠️ No model found at {model_path}, skipping probability scoring")
            _MODEL = None
    return _MODEL


# ───── Download Helpers ─────
def upgrade_avatar_url(url: str, size: int = 256) -> str:
    """
    Replace the *last* occurrence of '=s<number>-' with '=s<size>-' in the URL.
    Keeps any trailing suffixes like '-c-k-c0x00ffffff-no-rj'.
    """
    match = list(re.finditer(r"(=s)(\d+)(-[^?]*)", url))
    if not match:
        return url  # nothing to replace

    last = match[-1]
    start, end = last.span(2)  # group(2) = digits
    return url[:start] + str(size) + url[end:]


def download_avatar(url: str, timeout=5) -> np.ndarray | None:
    try:
        resp = requests.get(url, timeout=timeout)
        arr  = np.frombuffer(resp.content, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None

# ───── Metrics ─────
def edge_density(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 80, 160)
    return float(np.count_nonzero(edges)) / edges.size

def dominant_color_fraction(img: np.ndarray, k: int = 3) -> float:
    Z = img.reshape((-1,3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0)
    _c, labels, _ = cv2.kmeans(Z, k, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    return counts.max() / labels.size

def white_fraction(img: np.ndarray) -> float:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    S, V = hsv[:,:,1], hsv[:,:,2]
    white_mask = (S <= 40) & (V >= 200)
    return float(np.count_nonzero(white_mask)) / white_mask.size

def _largest_color_cluster_ratio(img: np.ndarray, k: int = 3) -> float:
    Z = img.reshape((-1, 3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0)
    _c, labels, _ = cv2.kmeans(Z, k, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    return float(counts.max()) / float(labels.size)

def _color_entropy(img: np.ndarray, bins: int = 16) -> float:
    hist = cv2.calcHist([img], [0, 1, 2], None,
                        [bins, bins, bins],
                        [0, 256, 0, 256, 0, 256])
    hist = hist.ravel() / hist.sum()
    hist = hist[hist > 0]
    return float(-(hist * np.log2(hist)).sum())


def saturation_stats(img: np.ndarray) -> tuple[float,float]:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:,:,1].astype(np.float32)/255.0
    return float(sat.mean()), float(sat.std())

def brightness_mean(img: np.ndarray) -> float:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return float(hsv[:,:,2].mean()/255.0)

def color_variance(img: np.ndarray) -> float:
    return float(np.var(img.astype(np.float32)))

def symmetry_score(gray: np.ndarray) -> float:
    h, w = gray.shape
    left  = gray[:, :w//2]
    right = cv2.flip(gray[:, w-w//2:], 1)
    return float(1.0 - np.mean(cv2.absdiff(left, right))/255.0)

def skin_tone_fraction(img: np.ndarray) -> float:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]
    skin_mask = (H < 50) & (S > 40) & (S < 150) & (V > 60)
    return float(np.count_nonzero(skin_mask)) / skin_mask.size

def hough_lines_density(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi/180, 50)
    return float(len(lines)) / (gray.size/1000) if lines is not None else 0.0

def is_suspicious_avatar(img, dbg=False):
    """
    Detects suspicious / racy avatars.
    Uses heuristics: high skin tone, not a flat background, high entropy.
    """
    if img is None:
        return False, {"reason": "no_image"}

    # --- metrics ---
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]
    # crude skin detection in HSV
    skin_mask = ((H >= 0) & (H <= 50)) & (S >= 0.23*255) & (S <= 0.68*255) & (V >= 0.35*255) & (V <= 1.0*255)

    dominant_frac   = float(_largest_color_cluster_ratio(img))
    color_entropy_v = float(_color_entropy(img))
    skin_frac       = float(np.count_nonzero(skin_mask)) / float(skin_mask.size)

    suspicious = (
        skin_frac > 0.2 and
        dominant_frac < 0.85 and
        color_entropy_v > 2.0
    )
    
    metrics = {
        "dominant_frac": dominant_frac,
        "color_entropy": color_entropy_v,
        "skin_frac": skin_frac,
    }
    for k, v in metrics.items():
        print(f"[DEBUG] {k}: {v!r} (type={type(v)})")
    if dbg:
        print(f"{'SUSPICIOUS' if suspicious else 'OK'} | "
              f"dom={dominant_frac:.2f} H={color_entropy:.2f} skin={skin_frac:.2f}")

    return suspicious, metrics


# ───── Classifier + Metrics Dump ─────
def classify_avatar_url(url: str, size: int = 256, model=None):
    
    hi = upgrade_avatar_url(url, size=size)
    img = download_avatar(hi)
    if img is None:
        img = download_avatar(url)
    if img is None:
        return "MISSING", {}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    metrics = {
        "ed"      : float(edge_density(gray)),
        "dom"     : float(dominant_color_fraction(img)),
        "white"   : float(white_fraction(img)),
        "entropy" : float(_color_entropy(img)),
        "sat_mean": float(saturation_stats(img)[0]),
        "sat_std" : float(saturation_stats(img)[1]),
        "bright"  : float(brightness_mean(img)),
        "var"     : float(color_variance(img)),
        "sym"     : float(symmetry_score(gray)),
        "skin"    : float(skin_tone_fraction(img)),
        "lines"   : float(hough_lines_density(gray)),
    }

    # for k, v in metrics.items():
    #     print(f"[DEBUG] {k}: {v!r} (type={type(v)})")


    # ---- Bot probability via model ----
    model = model or get_xgb_model()
    if model is not None:
        # ---- Bot probability via PCA+KMeans ----
        metrics = score_with_pca_kmeans(metrics)
    else:
        metrics["has_bot_probability"] = False

    # ---- Heuristic labels ----
    is_default = metrics["dom"] > 0.99 and metrics["entropy"] < 1.0
    is_suspicious = (metrics["skin"] > 0.01 and
                     metrics["dom"] < 0.9 and
                     metrics["entropy"] > 2.0)

    if is_default:
        label = "DEFAULT"
    elif is_suspicious:
        label = "SUSPICIOUS"
    else:
        label = "CUSTOM"

    return label, metrics





if __name__ == "__main__":
    test_urls = [
        # Sus
        "https://yt3.ggpht.com/ytc/AIdro_kz3lQ9Hqs6oAEsOL6PXqKBaGQAfhnhuZ4AM0OQgQz89_f1bm0WwWRi6kOnIQ-se2plZQ=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/ytc/AIdro_ngAwmGFSE0UVPyRbo1l5V_GAoUSs4mxTHOtHg_4Oo=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/ytc/AIdro_nVG3Y1GFrHdIR66Zb6mbL2_FGXuBnGc-Etx6CCPQk=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/ytc/AIdro_kZhJ1byL1bRnes168vMbuUu8wMhwuO36b3YEyp0pg=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/ytc/AIdro_nj52r54LP66EYFqP7Inb6jhP8S_q3e1BbIP1asn4ZSRuEPMPd_TcQnDlhRVA6szGI8QQ=s48-c-k-c0x00ffffff-no-rj",


        # Sus
        "https://yt3.ggpht.com/MG1QZpRE7EosgUrdtz93805tRp0rOMGZxdQLhu-N9LC0sQPklRTaxWUVl3JjMvLZhmHCMBXaLTg=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/PKi3T9d3YLHinpHDFG_GjmZhYeucEWiD3IX8PvUECNwOgoVrWJhznnoAKAQlUACpqwhqVhPUWLE=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/I8ZEkI3Gns0cwbDgx6CXN2qwQqY8f0xKmJ7FZhRZqcBjcOBLTBsvjETtge0OYed7J2VI54DW=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/eDTs5uJyLCtDaoedd5MIKiGabfgOA0XSRFR14XwiIMwKghO4YIy1Gifioz-ba3V82oR5eZhqpQ=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/3hXEQ3ybwWy7oN3kkqXwx7b5EOHMOZ91Xdrh7Gom269MfT6LSSTuQn_5Dzp9OBKlZG-fE4_yag=s48-c-k-c0x00ffffff-no-rj",
        
        # Real avatars
        "https://yt3.ggpht.com/ytc/AIdro_mNvcHHJomcQF7xSuKi3G8ifbv4UBeBj5kPsQHPNXsctg=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/ytc/AIdro_m1aT82LuvQZwMtIQVk_Phtdbay1JbvJOfWeQgT7UDDAP8=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/ytc/AIdro_m8K0q5_ZuLzHr-u3YAdQHWfjN0vewDZjzsSkf9wm--e88=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/ytc/AIdro_m-b3w-r73zvBNjxBI8KHd6zJRt36efQLA8CUW-7YupB4k=s48-c-k-c0x00ffffff-no-rj",
        "https://yt3.ggpht.com/3r3qIMHgoCHMsFU3_s7Z8hJAGXmxOXtWl0ysPzgpP8jAuSgwLDja6xury7R_JctQA8mpj69FH7k=s48-c-k-c0x00ffffff-no-rj",
    ]

    for url in test_urls:
        label, m = classify_avatar_url(url)
        print(f"{label:7} | "
              f"ed={m['ed']:.3f} dom={m['dom']:.2f} white={m['white']:.2f} "
              f"H={m['entropy']:.2f} sat={m['sat_mean']:.2f}±{m['sat_std']:.2f} "
              f"bright={m['bright']:.2f} var={m['var']:.1f} sym={m['sym']:.2f} "
              f"skin={m['skin']:.2f} lines={m['lines']:.2f}")


