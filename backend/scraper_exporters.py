from __future__ import annotations

import csv
from pathlib import Path

from scraper_models import LeadRecord
from scraper_utils import dedupe_leads, normalize_lead

CSV_HEADERS = [
    "query",
    "name",
    "phone",
    "address",
    "email",
    "owner_name",
    "website",
    "maps_url",
    "category",
    "social_links",
    "scraped_at",
    "confidence_score",
]


def _lead_to_row(lead: LeadRecord) -> list[object]:
    normalized = normalize_lead(lead)
    return [
        normalized.query,
        normalized.name,
        normalized.phone,
        normalized.address,
        normalized.email,
        normalized.owner_name,
        normalized.website,
        normalized.maps_url,
        normalized.category,
        ";".join(normalized.social_links),
        normalized.scraped_at,
        normalized.confidence_score,
    ]


def _row_to_lead(record: dict[str, str]) -> LeadRecord:
    return normalize_lead(
        LeadRecord(
            query=record.get("query", "N/A"),
            name=record.get("name", "N/A"),
            phone=record.get("phone", "N/A"),
            address=record.get("address", "N/A"),
            email=record.get("email", "N/A"),
            owner_name=record.get("owner_name", "N/A"),
            website=record.get("website", "N/A"),
            maps_url=record.get("maps_url", "N/A"),
            category=record.get("category", "N/A"),
            social_links=[link for link in record.get("social_links", "").split(";") if link],
            scraped_at=record.get("scraped_at", ""),
            confidence_score=float(record.get("confidence_score", "0") or 0),
        )
    )


def _read_csv_leads(path: Path) -> list[LeadRecord]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return [_row_to_lead(record) for record in csv.DictReader(csv_file)]


def export_csv(rows: list[LeadRecord], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADERS)
        for row in rows:
            writer.writerow(_lead_to_row(row))


def append_master_csv(rows: list[LeadRecord], master_path: Path) -> None:
    existing_rows = _read_csv_leads(master_path)
    export_csv(dedupe_leads(existing_rows + rows), master_path)

