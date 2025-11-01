from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Literal

@dataclass
class ChannelStatusDTO:
    channel_id: str
    status: Literal["active", "removed"]
    checked_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["checked_at"] = data["checked_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "ChannelStatusDTO":
        return ChannelStatusDTO(
            channel_id=data["channel_id"],
            status=data["status"],
            checked_at=datetime.fromisoformat(data["checked_at"])
        )
