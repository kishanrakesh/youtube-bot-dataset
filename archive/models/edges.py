"""Edge/Relationship Data Transfer Objects (DTOs).

This module contains DTOs representing relationships/edges between entities:
- ChannelDiscoveryEdgeDTO: How channels are discovered
- ChannelDomainLinkDTO: Links from channels to external domains
- ChannelFeaturedEdgeDTO: Featured channel relationships
- VideoTagEdgeDTO: Video-to-tag relationships
- VideoTopicCategoryEdgeDTO: Video-to-topic relationships
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Literal


@dataclass
class ChannelDiscoveryEdgeDTO:
    """Records how a channel was discovered."""
    
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


@dataclass
class ChannelDomainLinkDTO:
    """Links from channels to external domains."""
    
    channel_id: str
    domain: str  # Normalized domain (e.g., "example.com")
    raw_url: str  # Full URL as extracted (e.g., "https://example.com/shop?ref=bot")
    extraction_method: str  # e.g., "manual", "playwright", "parser_v1"
    discovered_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["discovered_at"] = data["discovered_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "ChannelDomainLinkDTO":
        return ChannelDomainLinkDTO(
            channel_id=data["channel_id"],
            domain=data["domain"],
            raw_url=data["raw_url"],
            extraction_method=data["extraction_method"],
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
        )


@dataclass
class ChannelFeaturedEdgeDTO:
    """Featured channel relationships."""
    
    source_channel_id: str  # The channel that contains the featured section
    featured_channel_id: str  # The channel that is featured
    section_title: str  # The text label (e.g., "Check These Out", "My Bots")
    discovered_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["discovered_at"] = data["discovered_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "ChannelFeaturedEdgeDTO":
        return ChannelFeaturedEdgeDTO(
            source_channel_id=data["source_channel_id"],
            featured_channel_id=data["featured_channel_id"],
            section_title=data["section_title"],
            discovered_at=datetime.fromisoformat(data["discovered_at"])
        )


@dataclass
class VideoTagEdgeDTO:
    """Video-to-tag relationships."""
    
    video_id: str
    tag: str
    discovered_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["discovered_at"] = data["discovered_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "VideoTagEdgeDTO":
        return VideoTagEdgeDTO(
            video_id=data["video_id"],
            tag=data["tag"],
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
        )


@dataclass
class VideoTopicCategoryEdgeDTO:
    """Video-to-topic category relationships."""
    
    video_id: str
    topic_category_url: str  # e.g., YouTube topic ontology URL
    discovered_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["discovered_at"] = data["discovered_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "VideoTopicCategoryEdgeDTO":
        return VideoTopicCategoryEdgeDTO(
            video_id=data["video_id"],
            topic_category_url=data["topic_category_url"],
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
        )
