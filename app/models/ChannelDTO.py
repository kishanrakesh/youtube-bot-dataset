from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class ChannelDTO:
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
