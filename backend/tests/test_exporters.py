from pathlib import Path

from scraper_exporters import append_master_csv, export_csv
from scraper_models import LeadRecord


def test_export_csv_writes_maps_url_column(tmp_path: Path):
    output = tmp_path / "leads.csv"
    rows = [
        LeadRecord(
            query="electronics store lagos",
            name="Shop",
            phone="0800 000 0000",
            address="Somewhere",
            website="https://example.com",
            maps_url="https://maps.google.com/?cid=123",
        )
    ]

    export_csv(rows, output)

    content = output.read_text(encoding="utf-8").splitlines()
    assert content[0].startswith("query,name,phone,address,email,owner_name,website,maps_url,category")
    assert "https://maps.google.com?cid=123" in content[1]


def test_append_master_csv_dedupes_existing_rows(tmp_path: Path):
    master = tmp_path / "master_leads.csv"
    first = LeadRecord(
        query="electronics store lagos",
        name="Shop",
        phone="0800 000 0000",
        address="Somewhere",
        maps_url="https://maps.google.com/?cid=123",
    )
    duplicate = LeadRecord(
        query="electronics store lagos",
        name="Shop",
        phone="+234 800 000 0000",
        address="Somewhere",
        maps_url="https://maps.google.com/?cid=123&utm_source=test",
    )
    second = LeadRecord(
        query="electronics store lagos",
        name="Second Shop",
        phone="0900 000 0000",
        address="Elsewhere",
        maps_url="https://maps.google.com/?cid=999",
    )

    append_master_csv([first], master)
    append_master_csv([duplicate, second], master)

    rows = master.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 3
    assert rows[0].startswith("query,name,phone,address,email,owner_name,website,maps_url,category")
    assert "Second Shop" in rows[2]
