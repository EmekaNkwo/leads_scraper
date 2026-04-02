from __future__ import annotations

import csv
import json
from pathlib import Path

from scraper_models import LeadRecord


def export_csv(rows: list[LeadRecord], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "query",
                "name",
                "phone",
                "address",
                "email",
                "owner_name",
                "website",
                "category",
                "social_links",
                "scraped_at",
                "confidence_score",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.query,
                    row.name,
                    row.phone,
                    row.address,
                    row.email,
                    row.owner_name,
                    row.website,
                    row.category,
                    ";".join(row.social_links),
                    row.scraped_at,
                    row.confidence_score,
                ]
            )


def append_master_csv(rows: list[LeadRecord], master_path: Path) -> None:
    needs_header = not master_path.exists()
    with master_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if needs_header:
            writer.writerow(
                [
                    "query",
                    "name",
                    "phone",
                    "address",
                    "email",
                    "owner_name",
                    "website",
                    "category",
                    "social_links",
                    "scraped_at",
                    "confidence_score",
                ]
            )
        for row in rows:
            writer.writerow(
                [
                    row.query,
                    row.name,
                    row.phone,
                    row.address,
                    row.email,
                    row.owner_name,
                    row.website,
                    row.category,
                    ";".join(row.social_links),
                    row.scraped_at,
                    row.confidence_score,
                ]
            )


def export_json(rows: list[LeadRecord], output_path: Path) -> None:
    payload = [row.to_dict() for row in rows]
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

