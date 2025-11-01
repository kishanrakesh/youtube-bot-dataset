from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime

@dataclass
class VideoDTO:
    video_id: str
    title: Optional[str]
    description: Optional[str]
    channel_id: str
    channel_title: Optional[str]
    published_at: datetime

    trending_category_id: Optional[str] = None  # If discovered via trending
    trending_country_code: Optional[str] = None  # e.g., "US", "IN"

    tags: List[str] = field(default_factory=list)
    topic_categories: List[str] = field(default_factory=list)  # YouTube topic URLs

    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None

    duration_seconds: Optional[int] = None
    is_live: Optional[bool] = None
    is_made_for_kids: Optional[bool] = None

    discovered_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["published_at"] = data["published_at"].isoformat()
        data["discovered_at"] = data["discovered_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "VideoDTO":
        return VideoDTO(
            video_id=data["video_id"],
            title=data.get("title"),
            description=data.get("description"),
            channel_id=data["channel_id"],
            channel_title=data.get("channel_title"),
            published_at=datetime.fromisoformat(data["published_at"]),
            trending_category_id=data.get("trending_category_id"),
            trending_country_code=data.get("trending_country_code"),
            tags=data.get("tags", []),
            topic_categories=data.get("topic_categories", []),
            view_count=data.get("view_count"),
            like_count=data.get("like_count"),
            comment_count=data.get("comment_count"),
            duration_seconds=data.get("duration_seconds"),
            is_live=data.get("is_live"),
            is_made_for_kids=data.get("is_made_for_kids"),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
        )
