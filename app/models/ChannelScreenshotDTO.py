from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class ChannelScreenshotDTO:
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
