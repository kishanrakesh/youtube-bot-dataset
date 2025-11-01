from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class VideoTagEdgeDTO:
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
