from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class LeadRecord:
    query: str
    name: str = "N/A"
    phone: str = "N/A"
    address: str = "N/A"
    email: str = "N/A"
    owner_name: str = "N/A"
    website: str = "N/A"
    category: str = "N/A"
    social_links: list[str] = field(default_factory=list)
    scraped_at: str = ""
    confidence_score: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

