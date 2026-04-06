from pathlib import Path

from scraper_dedupe_store import load_seen_aliases, save_seen_leads
from scraper_models import LeadRecord


def test_save_seen_leads_persists_aliases(tmp_path: Path):
    db_path = tmp_path / "seen_leads.sqlite3"
    leads = [
        LeadRecord(
            query="electronics store lagos",
            name="Shop",
            phone="0800 000 0000",
            address="Somewhere",
            maps_url="https://maps.google.com/?cid=123",
        )
    ]

    inserted = save_seen_leads(db_path, leads)
    aliases = load_seen_aliases(db_path)

    assert inserted >= 1
    assert "lead-address:shop|somewhere" in aliases
    assert "lead-phone:shop|08000000000" in aliases
    assert "maps:https://maps.google.com?cid=123" in aliases


def test_save_seen_leads_dedupes_existing_aliases(tmp_path: Path):
    db_path = tmp_path / "seen_leads.sqlite3"
    lead = LeadRecord(
        query="electronics store lagos",
        name="Shop",
        phone="0800 000 0000",
        address="Somewhere",
        maps_url="https://maps.google.com/?cid=123",
    )

    first = save_seen_leads(db_path, [lead])
    second = save_seen_leads(db_path, [lead])

    assert first >= 1
    assert second == 0
