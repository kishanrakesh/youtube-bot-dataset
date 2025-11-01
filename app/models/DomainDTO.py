from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional

@dataclass
class DomainDTO:
    domain: str  # Normalized (e.g., example.com)
    first_seen_at: datetime = field(default_factory=datetime.utcnow)
    discovered_by: Optional[str] = None  # e.g., "channel_link", "manual", "comment"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["first_seen_at"] = data["first_seen_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "DomainDTO":
        return DomainDTO(
            domain=data["domain"],
            first_seen_at=datetime.fromisoformat(data["first_seen_at"]),
            discovered_by=data.get("discovered_by")
        )
