"""Utility functions for constructing GCS paths."""

from datetime import date
from typing import Optional

__all__ = [
    # Video paths
    "trending_video_raw_path",
    "trending_video_manifest_path",
    "trending_seen_path",
    "video_by_channel_raw_path",
    "video_by_id_raw_path",
    "video_metadata_seen_path",
    "video_comments_path",
    "video_comments_seen_path",
    "videos_by_channel_seen_path",
    # Channel paths
    "channel_metadata_raw_path",
    "channel_metadata_seen_path",
    "channel_metadata_manifest_path",
    "channel_sections_raw_path",
    "channel_sections_seen_path",
    "channel_sections_manifest_path",
    # Domain paths
    "domain_seen_path",
    "domain_whois_raw_path",
    "domain_enrichment_completed_path",
    "domain_ready_path",
    "domain_completed_path",
    # Screenshot paths
    "screenshot_ready_path",
    "screenshot_completed_path",
]

BASE = "youtube-bot-dataset"


# ============================================================================
# Video Paths
# ============================================================================

def trending_video_raw_path(region: str, category: str, page: int, dt: Optional[str] = None) -> str:
    """Generate path for trending video data.
    
    Args:
        region: Region code (e.g., 'US', 'GB')
        category: YouTube category ID
        page: Page number
        dt: Date string in YYYY-MM-DD format (defaults to today)
        
    Returns:
        GCS path for trending video data
    """
    dt = dt or date.today().isoformat()
    filename = f"{region}_{category}_page_{page}.json"
    return f"{BASE}/video_metadata/trending/raw/{dt}/{filename}"


def trending_video_manifest_path() -> str:
    """Generate path for global trending video manifest.
    
    Returns:
        GCS path for trending video manifest
    """
    return f"{BASE}/video_metadata/trending/manifests/global_manifest.json"


def video_by_channel_raw_path(channel_id: str, page: int) -> str:
    """Generate path for videos by channel.
    
    Args:
        channel_id: YouTube channel ID
        page: Page number
        
    Returns:
        GCS path for channel videos
    """
    return f"{BASE}/video_metadata/by_channel/raw/{channel_id}_page_{page}.json"


def video_by_id_raw_path(video_id: str) -> str:
    """Generate path for video metadata by ID.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        GCS path for video metadata
    """
    return f"{BASE}/video_metadata/by_id/raw/{video_id}.json"


def video_metadata_seen_path(video_id: str) -> str:
    """Generate path for video metadata seen marker.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        GCS path for seen marker
    """
    return f"{BASE}/seen/video_metadata/by_id/{video_id}.json"


def video_comments_seen_path(video_id: str) -> str:
    """Generate path for video comments seen marker.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        GCS path for seen marker
    """
    return f"{BASE}/seen/video_comments/by_video/{video_id}.json"


def videos_by_channel_seen_path(channel_id: str, page: int) -> str:
    """Generate path for channel videos seen marker.
    
    Args:
        channel_id: YouTube channel ID
        page: Page number
        
    Returns:
        GCS path for seen marker
    """
    return f"{BASE}/seen/video_metadata/by_channel/{channel_id}_page_{page}.json"


def video_comments_path(video_id: str) -> str:
    """Generate path for video comments data.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        GCS path for video comments
    """
    return f"{BASE}/video_comments/raw/{video_id}.json"


def trending_seen_path(region: str, category_id: str, page: int, fetch_date: str) -> str:
    """Generate path for trending videos seen marker.
    
    Args:
        region: Region code (e.g., 'US', 'GB')
        category_id: YouTube category ID
        page: Page number
        fetch_date: Date string in YYYY-MM-DD format
        
    Returns:
        GCS path for seen marker
    """
    return f"{BASE}/seen/video_metadata/trending/{fetch_date}/{region}_{category_id}_page_{page}.json"


# ============================================================================
# Channel Metadata Paths
# ============================================================================

def channel_metadata_raw_path(channel_id: str) -> str:
    """Generate path for raw channel metadata.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for raw channel metadata
    """
    return f"{BASE}/channel_metadata/raw/{channel_id}.json"


def channel_metadata_seen_path(channel_id: str) -> str:
    """Generate path for channel metadata seen marker.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for seen marker
    """
    return f"{BASE}/seen/channel_metadata/{channel_id}.json"


def channel_metadata_manifest_path(channel_id: str) -> str:
    """Generate path for channel metadata manifest.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for channel manifest
    """
    return f"{BASE}/channel_metadata/manifests/{channel_id}.json"


# ============================================================================
# Channel Sections Paths
# ============================================================================

def channel_sections_raw_path(channel_id: str) -> str:
    """Generate path for raw channel sections data.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for raw channel sections
    """
    return f"{BASE}/channel_sections/raw/{channel_id}.json"


def channel_sections_seen_path(channel_id: str) -> str:
    """Generate path for channel sections seen marker.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for seen marker
    """
    return f"{BASE}/seen/channel_sections/{channel_id}.json"


def channel_sections_manifest_path() -> str:
    """Generate path for global channel sections manifest.
    
    Returns:
        GCS path for channel sections manifest
    """
    return f"{BASE}/channel_sections/manifests/global_manifest.json"


# ============================================================================
# Domain Enrichment Paths
# ============================================================================

def domain_seen_path(normalized_domain: str) -> str:
    """Generate path for domain seen marker.
    
    Args:
        normalized_domain: Normalized domain name
        
    Returns:
        GCS path for seen marker
    """
    return f"{BASE}/seen/domains/domains/{normalized_domain}.json"


def domain_whois_raw_path(normalized_domain: str) -> str:
    """Generate path for raw domain WHOIS data.
    
    Args:
        normalized_domain: Normalized domain name
        
    Returns:
        GCS path for raw WHOIS data
    """
    return f"{BASE}/domain_enrichment/raw/{normalized_domain}.json"


def domain_enrichment_completed_path(normalized_domain: str) -> str:
    """Generate path for domain enrichment completion marker.
    
    Args:
        normalized_domain: Normalized domain name
        
    Returns:
        GCS path for completion marker
    """
    return f"{BASE}/domain_enrichment/completed/{normalized_domain}.json"


def domain_ready_path(domain: str) -> str:
    """Generate path for domain ready marker.
    
    Args:
        domain: Domain name
        
    Returns:
        GCS path for ready marker
    """
    return f"{BASE}/domains/ready/{domain}.json"


def domain_completed_path(domain: str) -> str:
    """Generate path for domain completion marker.
    
    Args:
        domain: Domain name
        
    Returns:
        GCS path for completion marker
    """
    return f"{BASE}/domains/completed/{domain}.json"


# ============================================================================
# Screenshots
# ============================================================================

def screenshot_ready_path(channel_id: str) -> str:
    """Generate path for screenshot ready marker.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for ready marker
    """
    return f"{BASE}/channel_screenshots/ready/{channel_id}.jpg"


def screenshot_completed_path(channel_id: str) -> str:
    """Generate path for screenshot completion marker.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for completion marker
    """
    return f"{BASE}/channel_screenshots/completed/{channel_id}.jpg"


# ============================================================================
# Labels
# ============================================================================

def label_ready_path(channel_id: str) -> str:
    """Generate path for label ready marker.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for ready marker
    """
    return f"{BASE}/channel_labels/ready/{channel_id}.json"


def label_completed_path(channel_id: str) -> str:
    """Generate path for label completion marker.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for completion marker
    """
    return f"{BASE}/channel_labels/completed/{channel_id}.json"


# ============================================================================
# Channel Links
# ============================================================================

def channel_link_ready_path(channel_id: str) -> str:
    """Generate path for channel link ready marker.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for ready marker
    """
    return f"{BASE}/channel_links/ready/{channel_id}.json"


def channel_link_completed_path(channel_id: str) -> str:
    """Generate path for channel link completion marker.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        GCS path for completion marker
    """
    return f"{BASE}/channel_links/completed/{channel_id}.json"
