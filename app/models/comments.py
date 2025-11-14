"""Comment-related Data Transfer Objects (DTOs).

This module contains DTOs for YouTube video comments.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional


@dataclass
class CommentDTO:
    """Video comment information from YouTube API."""
    
    comment_id: str
    video_id: str
    author_channel_id: str
    text: str
    like_count: int
    published_at: datetime
    updated_at: Optional[datetime]
    is_reply: bool  # True if it's a reply to another comment

    parent_comment_id: Optional[str] = None  # Only set if is_reply=True
    discovered_at: datetime = field(default_factory=datetime.utcnow)  # When the comment was fetched

    def to_dict(self) -> dict:
        data = asdict(self)
        data["published_at"] = data["published_at"].isoformat()
        if data["updated_at"]:
            data["updated_at"] = data["updated_at"].isoformat()
        data["discovered_at"] = data["discovered_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "CommentDTO":
        return CommentDTO(
            comment_id=data["comment_id"],
            video_id=data["video_id"],
            author_channel_id=data["author_channel_id"],
            text=data["text"],
            like_count=data["like_count"],
            published_at=datetime.fromisoformat(data["published_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            is_reply=data["is_reply"],
            parent_comment_id=data.get("parent_comment_id"),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
        )
