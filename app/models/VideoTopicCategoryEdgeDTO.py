from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class VideoTopicCategoryEdgeDTO:
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
