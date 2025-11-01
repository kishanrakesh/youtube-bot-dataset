from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

@dataclass
class ChannelDomainLinkDTO:
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
