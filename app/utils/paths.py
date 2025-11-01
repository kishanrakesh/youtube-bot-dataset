# app/paths.py

from datetime import date
from typing import Optional

BASE = "youtube-bot-dataset"

# -------------------- VIDEO PATHS --------------------

def trending_video_raw_path(region: str, category: str, page: int, dt: Optional[str] = None):
    dt = dt or date.today().isoformat()
    filename = f"{region}_{category}_page_{page}.json"
    return f"{BASE}/video_metadata/trending/raw/{dt}/{filename}"

def trending_video_manifest_path():
    return f"{BASE}/video_metadata/trending/manifests/global_manifest.json"

def video_by_channel_raw_path(channel_id: str, page: int):
    return f"{BASE}/video_metadata/by_channel/raw/{channel_id}_page_{page}.json"

def video_by_id_raw_path(video_id: str):
    return f"{BASE}/video_metadata/by_id/raw/{video_id}.json"

def video_metadata_seen_path(video_id: str) -> str:
    return f"{BASE}/seen/video_metadata/by_id/{video_id}.json"

def video_comments_seen_path(video_id: str) -> str:
    return f"{BASE}/seen/video_comments/by_video/{video_id}.json"

def videos_by_channel_seen_path(channel_id: str, page: int) -> str:
    return f"{BASE}/seen/video_metadata/by_channel/{channel_id}_page_{page}.json"

def video_comments_path(video_id: str):
    return f"{BASE}/video_comments/raw/{video_id}.json"

def trending_seen_path(region: str, category_id: str, page: int, fetch_date: str) -> str:
    return f"{BASE}/seen/video_metadata/trending/{fetch_date}/{region}_{category_id}_page_{page}.json"


# -------------------- CHANNEL METADATA PATHS --------------------

def channel_metadata_raw_path(channel_id: str):
    return f"{BASE}/channel_metadata/raw/{channel_id}.json"

def channel_metadata_seen_path(channel_id: str):
    return f"{BASE}/seen/channel_metadata/{channel_id}.json"

def channel_metadata_manifest_path(channel_id: str):
    return f"{BASE}/channel_metadata/manifests/{channel_id}.json"

# -------------------- CHANNEL SECTIONS PATHS --------------------

def channel_sections_raw_path(channel_id: str):
    return f"{BASE}/channel_sections/raw/{channel_id}.json"

def channel_sections_seen_path(channel_id: str):
    return f"{BASE}/seen/channel_sections/{channel_id}.json"

def channel_sections_manifest_path():
    return f"{BASE}/channel_sections/manifests/global_manifest.json"

# -------------------- DOMAIN ENRICHMENT PATHS --------------------

def domain_seen_path(normalized_domain: str):
    return f"{BASE}/seen/domains/domains/{normalized_domain}.json"

def domain_whois_raw_path(normalized_domain: str):
    return f"{BASE}/domain_enrichment/raw/{normalized_domain}.json"

def domain_enrichment_completed_path(normalized_domain: str):
    return f"{BASE}/domain_enrichment/completed/{normalized_domain}.json"

def domain_ready_path(domain: str):
    return f"{BASE}/domains/ready/{domain}.json"

def domain_completed_path(domain: str):
    return f"{BASE}/domains/completed/{domain}.json"

# -------------------- SCREENSHOTS --------------------

def screenshot_ready_path(channel_id: str):
    return f"{BASE}/channel_screenshots/ready/{channel_id}.jpg"

def screenshot_completed_path(channel_id: str):
    return f"{BASE}/channel_screenshots/completed/{channel_id}.jpg"

# -------------------- LABELS --------------------

def label_ready_path(channel_id: str):
    return f"{BASE}/channel_labels/ready/{channel_id}.json"

def label_completed_path(channel_id: str):
    return f"{BASE}/channel_labels/completed/{channel_id}.json"

# -------------------- CHANNEL LINKS --------------------

def channel_link_ready_path(channel_id: str):
    return f"{BASE}/channel_links/ready/{channel_id}.json"

def channel_link_completed_path(channel_id: str):
    return f"{BASE}/channel_links/completed/{channel_id}.json"
