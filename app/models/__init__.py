"""Data Transfer Objects (DTOs) for YouTube bot detection project.

This package contains all DTOs organized by domain:
- channels: Channel-related DTOs
- videos: Video-related DTOs
- comments: Comment-related DTOs
- domains: Domain-related DTOs
- edges: Relationship/edge DTOs

All DTOs can be imported directly from this package for convenience:
    from app.models import ChannelDTO, VideoDTO, CommentDTO
"""

# Channel-related DTOs
from app.models.channels import (
    ChannelDTO,
    ChannelLabelDTO,
    ChannelScreenshotDTO,
    ChannelStatusDTO,
)

# Video DTOs
from app.models.videos import VideoDTO

# Comment DTOs
from app.models.comments import CommentDTO

# Domain DTOs
from app.models.domains import (
    DomainDTO,
    DomainEnrichmentDTO,
)

# Edge/Relationship DTOs
from app.models.edges import (
    ChannelDiscoveryEdgeDTO,
    ChannelDomainLinkDTO,
    ChannelFeaturedEdgeDTO,
    VideoTagEdgeDTO,
    VideoTopicCategoryEdgeDTO,
)

__all__ = [
    # Channels
    "ChannelDTO",
    "ChannelLabelDTO",
    "ChannelScreenshotDTO",
    "ChannelStatusDTO",
    # Videos
    "VideoDTO",
    # Comments
    "CommentDTO",
    # Domains
    "DomainDTO",
    "DomainEnrichmentDTO",
    # Edges
    "ChannelDiscoveryEdgeDTO",
    "ChannelDomainLinkDTO",
    "ChannelFeaturedEdgeDTO",
    "VideoTagEdgeDTO",
    "VideoTopicCategoryEdgeDTO",
]
