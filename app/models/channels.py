"""Channel-related Data Transfer Objects (DTOs).

This module contains all DTOs related to YouTube channels, including:
- ChannelDTO: Core channel information and metadata
- ChannelLabelDTO: Bot classification labels
- ChannelScreenshotDTO: Screenshot capture metadata
- ChannelStatusDTO: Channel availability status
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


@dataclass
class ChannelDTO:
    """Core channel information from YouTube API."""
    
    # --- Core Identity ---
    id: str
    handle: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    country: Optional[str] = None
    published_at: Optional[datetime] = None
    discovered_at: datetime = field(default_factory=datetime.utcnow)

    # --- Visuals ---
    thumbnail_url_default: Optional[str] = None
    thumbnail_url_medium: Optional[str] = None
    thumbnail_url_high: Optional[str] = None
    banner_external_url: Optional[str] = None

    # --- Statistics ---
    view_count: Optional[int] = None
    video_count: Optional[int] = None
    subscriber_count: Optional[int] = None
    is_subscriber_count_hidden: Optional[bool] = None

    # --- Topic and Metadata ---
    topic_ids: List[str] = field(default_factory=list)
    topic_categories: List[str] = field(default_factory=list)
    keywords: Optional[str] = None
    uploads_playlist_id: Optional[str] = None

    # --- Flags from API ---
    is_linked: Optional[bool] = None
    is_made_for_kids: Optional[bool] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        # Remove any None values (BQ prefers omitted fields)
        return {k: v for k, v in data.items() if v is not None}

    @staticmethod
    def from_dict(data: dict) -> "ChannelDTO":
        return ChannelDTO(
            id=data["id"],
            handle=data.get("handle"),
            title=data.get("title"),
            description=data.get("description"),
            country=data.get("country"),
            published_at=datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None,
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
            thumbnail_url_default=data.get("thumbnail_url_default"),
            thumbnail_url_medium=data.get("thumbnail_url_medium"),
            thumbnail_url_high=data.get("thumbnail_url_high"),
            banner_external_url=data.get("banner_external_url"),
            view_count=data.get("view_count"),
            video_count=data.get("video_count"),
            subscriber_count=data.get("subscriber_count"),
            is_subscriber_count_hidden=data.get("is_subscriber_count_hidden"),
            topic_ids=data.get("topic_ids", []),
            topic_categories=data.get("topic_categories", []),
            keywords=data.get("keywords"),
            uploads_playlist_id=data.get("uploads_playlist_id"),
            is_linked=data.get("is_linked"),
            is_made_for_kids=data.get("is_made_for_kids"),
        )


@dataclass
class ChannelLabelDTO:
    """Bot classification label for a channel."""
    
    channel_id: str
    label: Literal["yes", "no", "suspected"]
    labeled_at: datetime
    label_source: str  # e.g., "manual", "screenshot", "model_v1"

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "label": self.label,
            "labeled_at": self.labeled_at.isoformat(),
            "label_source": self.label_source
        }

    @staticmethod
    def from_dict(data: dict) -> "ChannelLabelDTO":
        return ChannelLabelDTO(
            channel_id=data["channel_id"],
            label=data["label"],
            labeled_at=datetime.fromisoformat(data["labeled_at"]),
            label_source=data["label_source"]
        )


@dataclass
class ChannelScreenshotDTO:
    """Screenshot capture metadata for a channel."""
    
    channel_id: str
    gcs_uri: str
    captured_at: datetime
    batch_id: str  # Optional but useful for tracking review batches

    def to_dict(self) -> dict:
        data = asdict(self)
        data["captured_at"] = data["captured_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "ChannelScreenshotDTO":
        return ChannelScreenshotDTO(
            channel_id=data["channel_id"],
            gcs_uri=data["gcs_uri"],
            captured_at=datetime.fromisoformat(data["captured_at"]),
            batch_id=data["batch_id"]
        )


@dataclass
class ChannelStatusDTO:
    """Channel availability status."""
    
    channel_id: str
    status: Literal["active", "removed"]
    checked_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["checked_at"] = data["checked_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "ChannelStatusDTO":
        return ChannelStatusDTO(
            channel_id=data["channel_id"],
            status=data["status"],
            checked_at=datetime.fromisoformat(data["checked_at"])
        )
