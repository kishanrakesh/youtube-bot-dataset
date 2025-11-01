from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class ChannelFeaturedEdgeDTO:
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
