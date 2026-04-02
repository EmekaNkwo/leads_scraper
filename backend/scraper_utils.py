from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from scraper_models import LeadRecord


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def normalize_key(lead: LeadRecord) -> str:
    name = re.sub(r"\s+", " ", lead.name.strip().lower())
    address = re.sub(r"\s+", " ", lead.address.strip().lower())
    phone = re.sub(r"\D+", "", lead.phone)
    return f"{name}|{address}|{phone}"


def compute_confidence(lead: LeadRecord) -> float:
    score = 0.0
    if lead.phone != "N/A":
        score += 0.25
    if lead.address != "N/A":
        score += 0.2
    if lead.website != "N/A":
        score += 0.2
    if lead.email != "N/A":
        score += 0.25
    if lead.owner_name != "N/A":
        score += 0.1
    return round(min(score, 1.0), 2)


def setup_logger(logs_dir: Path, run_id: str) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"leads_scraper_{run_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(logs_dir / f"run_{run_id}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def archive_old_exports(output_dir: Path, days: int) -> None:
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now() - timedelta(days=days)

    for csv_file in output_dir.glob("*.csv"):
        modified = datetime.fromtimestamp(csv_file.stat().st_mtime)
        if modified < cutoff:
            csv_file.rename(archive_dir / csv_file.name)


def checkpoint_path(checkpoint_dir: Path, query: str) -> Path:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"{slugify(query)}.json"


def save_checkpoint(path: Path, leads: list[LeadRecord], index: int) -> None:
    payload = {"index": index, "leads": [lead.to_dict() for lead in leads]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint(path: Path, query: str) -> tuple[int, list[LeadRecord]]:
    if not path.exists():
        return 0, []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0, []

    index = int(payload.get("index", 0))
    leads: list[LeadRecord] = []
    for item in payload.get("leads", []):
        leads.append(LeadRecord(query=query, **{k: v for k, v in item.items() if k != "query"}))
    return index, leads

