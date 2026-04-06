from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from scraper_models import LeadRecord
from scraper_utils import lead_identity_aliases


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_lead_aliases (
            alias_key TEXT PRIMARY KEY,
            primary_key TEXT NOT NULL,
            query TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_seen_lead_aliases_primary_key ON seen_lead_aliases(primary_key)"
    )
    return connection


def load_seen_aliases(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    with _connect(db_path) as connection:
        rows = connection.execute("SELECT alias_key FROM seen_lead_aliases").fetchall()
    return {str(row[0]) for row in rows}


def count_seen_aliases(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    with _connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM seen_lead_aliases").fetchone()
    return int(row[0]) if row else 0


def save_seen_leads(db_path: Path, leads: list[LeadRecord]) -> int:
    if not leads:
        return 0

    inserted = 0
    now = datetime.now().isoformat()
    with _connect(db_path) as connection:
        for lead in leads:
            aliases = lead_identity_aliases(lead)
            primary_key = sorted(aliases)[0]
            for alias in aliases:
                existing = connection.execute(
                    "SELECT 1 FROM seen_lead_aliases WHERE alias_key = ?",
                    (alias,),
                ).fetchone()
                if existing:
                    connection.execute(
                        """
                        UPDATE seen_lead_aliases
                        SET last_seen_at = ?, query = ?, primary_key = ?
                        WHERE alias_key = ?
                        """,
                        (now, lead.query, primary_key, alias),
                    )
                    continue
                connection.execute(
                    """
                    INSERT INTO seen_lead_aliases(alias_key, primary_key, query, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (alias, primary_key, lead.query, now, now),
                )
                inserted += 1
    return inserted
