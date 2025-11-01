from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Literal

@dataclass
class ChannelDiscoveryEdgeDTO:
    from_id: str  # The ID that led to discovering the channel
    from_type: Literal["video", "comment", "channel", "search_result"]  # Explicit type of `from_id`
    to_channel_id: str  # The newly discovered channel
    method: Literal["comment", "featured", "manual", "cse"]  # Discovery method
    context_video_id: Optional[str] = None  # For "comment" method
    context_comment_id: Optional[str] = None  # For "comment" method
    discovered_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["discovered_at"] = data["discovered_at"].isoformat()
        return {k: v for k, v in data.items() if v is not None}

    @staticmethod
    def from_dict(data: dict) -> "ChannelDiscoveryEdgeDTO":
        return ChannelDiscoveryEdgeDTO(
            from_id=data["from_id"],
            from_type=data["from_type"],
            to_channel_id=data["to_channel_id"],
            method=data["method"],
            context_video_id=data.get("context_video_id"),
            context_comment_id=data.get("context_comment_id"),
            discovered_at=datetime.fromisoformat(data["discovered_at"])
        )
