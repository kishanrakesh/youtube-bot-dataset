from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass
class ChannelLabelDTO:
    channel_id: str
    label: Literal["yes", "no", "suspected"]
    labeled_at: datetime
    label_source: str  # e.g., "manual", "screenshot", "model_v1"

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "label": self.label,
            "labeled_at": self.labeled_at.isoformat(),
            "label_source": self.label_source
        }

    @staticmethod
    def from_dict(data: dict) -> "ChannelLabelDTO":
        return ChannelLabelDTO(
            channel_id=data["channel_id"],
            label=data["label"],
            labeled_at=datetime.fromisoformat(data["labeled_at"]),
            label_source=data["label_source"]
        )
