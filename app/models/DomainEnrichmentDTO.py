from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

@dataclass
class DomainEnrichmentDTO:
    domain: str
    registrar: Optional[str]
    registrant_name: Optional[str]
    registrant_organization: Optional[str]
    registrant_street: Optional[str]
    registrant_city: Optional[str]
    registrant_state: Optional[str]
    registrant_country: Optional[str]

    is_privacy_protected: bool
    creation_date: Optional[datetime]

    enrichment_method: str  # e.g., "whois.domaintools"
    enriched_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        if data["creation_date"]:
            data["creation_date"] = data["creation_date"].isoformat()
        data["enriched_at"] = data["enriched_at"].isoformat()
        return data

    @staticmethod
    def from_dict(data: dict) -> "DomainEnrichmentDTO":
        return DomainEnrichmentDTO(
            domain=data["domain"],
            registrar=data.get("registrar"),
            registrant_name=data.get("registrant_name"),
            registrant_organization=data.get("registrant_organization"),
            registrant_street=data.get("registrant_street"),
            registrant_city=data.get("registrant_city"),
            registrant_state=data.get("registrant_state"),
            registrant_country=data.get("registrant_country"),
            is_privacy_protected=data["is_privacy_protected"],
            creation_date=datetime.fromisoformat(data["creation_date"]) if data.get("creation_date") else None,
            enrichment_method=data["enrichment_method"],
            enriched_at=datetime.fromisoformat(data["enriched_at"]),
        )
