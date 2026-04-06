from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from scraper_models import LeadRecord

NA_VALUE = "N/A"


@dataclass
class CheckpointState:
    leads: list[LeadRecord] = field(default_factory=list)
    lead_keys: set[str] = field(default_factory=set)
    card_keys: set[str] = field(default_factory=set)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def normalize_text(value: str) -> str:
    if not value or value == NA_VALUE:
        return NA_VALUE
    normalized = normalize_whitespace(value)
    return normalized if normalized else NA_VALUE


def normalize_phone(value: str) -> str:
    if not value or value == NA_VALUE:
        return NA_VALUE
    digits = re.sub(r"\D+", "", value)
    return digits if digits else NA_VALUE


def canonicalize_url(value: str) -> str:
    if not value or value == NA_VALUE:
        return NA_VALUE
    candidate = value.strip()
    if not candidate:
        return NA_VALUE
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return normalize_whitespace(value)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    filtered_query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.startswith("utm_")]
    normalized = urlunsplit((parsed.scheme.lower() or "https", netloc, path, urlencode(filtered_query), ""))
    return normalized if normalized else NA_VALUE


def normalize_social_links(links: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for link in links:
        canonical = canonicalize_url(link)
        if canonical == NA_VALUE or canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


def normalize_lead(lead: LeadRecord) -> LeadRecord:
    lead.query = normalize_whitespace(lead.query)
    lead.name = normalize_text(lead.name)
    lead.phone = normalize_phone(lead.phone)
    lead.address = normalize_text(lead.address)
    normalized_email = normalize_text(lead.email)
    lead.email = normalized_email.casefold() if normalized_email != NA_VALUE else NA_VALUE
    lead.owner_name = normalize_text(lead.owner_name)
    lead.website = canonicalize_url(lead.website)
    lead.maps_url = canonicalize_url(lead.maps_url)
    lead.category = normalize_text(lead.category)
    lead.social_links = normalize_social_links(lead.social_links)
    return lead


def lead_identity_aliases(lead: LeadRecord) -> set[str]:
    normalized = normalize_lead(lead)
    aliases: set[str] = set()
    if normalized.name != NA_VALUE and normalized.address != NA_VALUE:
        aliases.add(f"lead-address:{normalized.name.casefold()}|{normalized.address.casefold()}")
    if normalized.name != NA_VALUE and normalized.phone != NA_VALUE:
        aliases.add(f"lead-phone:{normalized.name.casefold()}|{normalized.phone}")
    if normalized.maps_url != NA_VALUE:
        aliases.add(f"maps:{normalized.maps_url}")
    if normalized.website != NA_VALUE and normalized.name != NA_VALUE:
        aliases.add(f"site:{normalized.name.casefold()}|{normalized.website.casefold()}")
    if not aliases:
        aliases.add(
            "fallback:" + "|".join(
                [
                    normalized.name.casefold(),
                    normalized.address.casefold(),
                    normalized.phone,
                    normalized.category.casefold(),
                ]
            )
        )
    return aliases


def lead_identity_key(lead: LeadRecord) -> str:
    aliases = lead_identity_aliases(lead)
    for prefix in ("lead-address:", "lead-phone:", "maps:", "site:", "fallback:"):
        for alias in aliases:
            if alias.startswith(prefix):
                return alias
    return sorted(aliases)[0]


def normalize_key(lead: LeadRecord) -> str:
    return lead_identity_key(lead)


def dedupe_leads(leads: list[LeadRecord]) -> list[LeadRecord]:
    deduped: list[LeadRecord] = []
    seen: set[str] = set()
    for lead in leads:
        aliases = lead_identity_aliases(lead)
        if seen.intersection(aliases):
            continue
        seen.update(aliases)
        deduped.append(lead)
    return deduped


def compute_confidence(lead: LeadRecord) -> float:
    score = 0.0
    if lead.phone != NA_VALUE:
        score += 0.25
    if lead.address != NA_VALUE:
        score += 0.2
    if lead.website != NA_VALUE:
        score += 0.2
    if lead.email != NA_VALUE:
        score += 0.25
    if lead.owner_name != NA_VALUE:
        score += 0.1
    return round(min(score, 1.0), 2)


def setup_logger(logs_dir: Path, run_id: str) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"leads_scraper_{run_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(logs_dir / f"run_{run_id}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def retention_deadline(created_at: datetime, retention_minutes: int) -> datetime | None:
    if retention_minutes <= 0:
        return None
    return created_at + timedelta(minutes=retention_minutes)


def path_expiration(path: Path, retention_minutes: int) -> datetime | None:
    if retention_minutes <= 0 or not path.exists():
        return None
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return retention_deadline(modified, retention_minutes)


def cleanup_expired_files(
    paths: list[Path],
    retention_minutes: int,
    patterns: list[str],
    protected_paths: set[Path] | None = None,
) -> int:
    if retention_minutes <= 0:
        return 0

    cutoff = datetime.now() - timedelta(minutes=retention_minutes)
    deleted = 0
    seen: set[Path] = set()
    protected = {path.resolve() for path in (protected_paths or set()) if path.exists()}
    for root in paths:
        if not root.exists():
            continue
        for pattern in patterns:
            for file_path in root.glob(pattern):
                if file_path in seen or not file_path.is_file():
                    continue
                seen.add(file_path)
                if file_path.resolve() in protected:
                    continue
                modified = datetime.fromtimestamp(file_path.stat().st_mtime)
                if modified >= cutoff:
                    continue
                try:
                    file_path.unlink(missing_ok=True)
                except PermissionError:
                    # Windows can keep recently used log files locked; skip them.
                    continue
                except OSError:
                    continue
                deleted += 1
    return deleted


def checkpoint_path(checkpoint_dir: Path, query: str) -> Path:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"{slugify(query)}.json"


def save_checkpoint(path: Path, leads: list[LeadRecord], lead_keys: set[str], card_keys: set[str]) -> None:
    payload = {
        "version": 2,
        "saved_at": datetime.now().isoformat(),
        "lead_keys": sorted(lead_keys),
        "card_keys": sorted(card_keys),
        "leads": [normalize_lead(lead).to_dict() for lead in leads],
        "meta": {
            "lead_count": len(leads),
            "card_key_count": len(card_keys),
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint(path: Path, query: str) -> CheckpointState:
    if not path.exists():
        return CheckpointState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return CheckpointState()

    leads: list[LeadRecord] = []
    for item in payload.get("leads", []):
        leads.append(normalize_lead(LeadRecord(query=query, **{k: v for k, v in item.items() if k != "query"})))

    if payload.get("version") == 2:
        lead_keys = {key for key in payload.get("lead_keys", []) if isinstance(key, str)}
        card_keys = {key for key in payload.get("card_keys", []) if isinstance(key, str)}
        for lead in leads:
            lead_keys.update(lead_identity_aliases(lead))
        return CheckpointState(leads=leads, lead_keys=lead_keys, card_keys=card_keys)

    return CheckpointState(
        leads=leads,
        lead_keys={alias for lead in leads for alias in lead_identity_aliases(lead)},
        card_keys=set(),
    )

