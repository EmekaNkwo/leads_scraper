from pathlib import Path

import scraper
from scraper_config import AppConfig
from scraper_models import LeadRecord


def test_run_query_exports_csv_only_and_updates_checkpoint(tmp_path: Path, monkeypatch):
    def fake_scrape_query(**_kwargs):
        return [
            LeadRecord(
                query="electronics store lagos",
                name="Shop",
                phone="0800 000 0000",
                address="Somewhere",
                maps_url="https://maps.google.com/?cid=123",
            )
        ]

    monkeypatch.setattr(scraper, "scrape_query", fake_scrape_query)

    cfg = AppConfig(
        queries=["electronics store lagos"],
        output_dir=str(tmp_path / "exports"),
        checkpoint_dir=str(tmp_path / "checkpoints"),
        logs_dir=str(tmp_path / "logs"),
        dedupe_db_path=str(tmp_path / "checkpoints" / "seen_leads.sqlite3"),
        enrich_websites=False,
        enable_master_csv=True,
    )
    logger = scraper.setup_logger(tmp_path / "logs", "test_run")

    leads, _elapsed, csv_path = scraper.run_query(
        query="electronics store lagos",
        cfg=cfg,
        output_dir=Path(cfg.output_dir),
        checkpoints_dir=Path(cfg.checkpoint_dir),
        logger=logger,
        resume=False,
    )

    assert len(leads) == 1
    assert csv_path.exists()
    assert list((tmp_path / "exports").glob("*.json")) == []
    checkpoint_files = list((tmp_path / "checkpoints").glob("*.json"))
    assert len(checkpoint_files) == 1
    assert (tmp_path / "exports" / "master_leads.csv").exists()


def test_run_query_resume_dedupes_checkpoint_and_new_results(tmp_path: Path, monkeypatch):
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    checkpoint_file = checkpoint_dir / "electronics-store-lagos.json"
    checkpoint_file.write_text(
        """
{
  "version": 2,
  "lead_keys": ["maps:https://maps.google.com?cid=123"],
  "card_keys": ["href:https://maps.google.com?cid=123"],
  "meta": {
    "scrolls_used": 4
  },
  "leads": [
    {
      "query": "electronics store lagos",
      "name": "Shop",
      "phone": "0800 000 0000",
      "address": "Somewhere",
      "maps_url": "https://maps.google.com/?cid=123"
    }
  ]
}
        """.strip(),
        encoding="utf-8",
    )

    captured_kwargs = {}

    def fake_scrape_query(**kwargs):
        captured_kwargs.update(kwargs)
        return [
            LeadRecord(
                query="electronics store lagos",
                name="Shop",
                phone="+234 800 000 0000",
                address="Somewhere",
                maps_url="https://maps.google.com/?cid=123&utm_source=test",
            ),
            LeadRecord(
                query="electronics store lagos",
                name="Second Shop",
                phone="0900 000 0000",
                address="Elsewhere",
                maps_url="https://maps.google.com/?cid=999",
            ),
        ]

    monkeypatch.setattr(scraper, "scrape_query", fake_scrape_query)

    cfg = AppConfig(
        queries=["electronics store lagos"],
        output_dir=str(tmp_path / "exports"),
        checkpoint_dir=str(checkpoint_dir),
        logs_dir=str(tmp_path / "logs"),
        dedupe_db_path=str(checkpoint_dir / "seen_leads.sqlite3"),
        enrich_websites=False,
    )
    logger = scraper.setup_logger(tmp_path / "logs", "resume_run")

    leads, _elapsed, _csv_path = scraper.run_query(
        query="electronics store lagos",
        cfg=cfg,
        output_dir=Path(cfg.output_dir),
        checkpoints_dir=checkpoint_dir,
        logger=logger,
        resume=True,
    )

    assert len(leads) == 2
    assert captured_kwargs["initial_scrolls_used"] == 4


def test_run_query_skips_master_csv_when_disabled(tmp_path: Path, monkeypatch):
    def fake_scrape_query(**_kwargs):
        return [
            LeadRecord(
                query="electronics store lagos",
                name="Shop",
                phone="0800 000 0000",
                address="Somewhere",
                maps_url="https://maps.google.com/?cid=123",
            )
        ]

    monkeypatch.setattr(scraper, "scrape_query", fake_scrape_query)

    cfg = AppConfig(
        queries=["electronics store lagos"],
        output_dir=str(tmp_path / "exports"),
        checkpoint_dir=str(tmp_path / "checkpoints"),
        logs_dir=str(tmp_path / "logs"),
        dedupe_db_path=str(tmp_path / "checkpoints" / "seen_leads.sqlite3"),
        enrich_websites=False,
        enable_master_csv=False,
    )
    logger = scraper.setup_logger(tmp_path / "logs", "no_master")

    leads, _elapsed, csv_path = scraper.run_query(
        query="electronics store lagos",
        cfg=cfg,
        output_dir=Path(cfg.output_dir),
        checkpoints_dir=Path(cfg.checkpoint_dir),
        logger=logger,
        resume=False,
    )

    assert len(leads) == 1
    assert csv_path.exists()
    assert not (tmp_path / "exports" / "master_leads.csv").exists()


def test_run_query_skips_leads_seen_in_sqlite_store(tmp_path: Path, monkeypatch):
    def fake_scrape_query(**_kwargs):
        return [
            LeadRecord(
                query="electronics store lagos",
                name="Shop",
                phone="0800 000 0000",
                address="Somewhere",
                maps_url="https://maps.google.com/?cid=123",
            ),
            LeadRecord(
                query="electronics store lagos",
                name="Second Shop",
                phone="0900 000 0000",
                address="Elsewhere",
                maps_url="https://maps.google.com/?cid=999",
            ),
        ]

    monkeypatch.setattr(scraper, "scrape_query", fake_scrape_query)

    cfg = AppConfig(
        queries=["electronics store lagos"],
        output_dir=str(tmp_path / "exports"),
        checkpoint_dir=str(tmp_path / "checkpoints"),
        logs_dir=str(tmp_path / "logs"),
        dedupe_db_path=str(tmp_path / "checkpoints" / "seen_leads.sqlite3"),
        enrich_websites=False,
        enable_master_csv=False,
    )
    logger = scraper.setup_logger(tmp_path / "logs", "sqlite_seen")

    scraper.save_seen_leads(
        Path(cfg.dedupe_db_path),
        [
            LeadRecord(
                query="electronics store lagos",
                name="Shop",
                phone="0800 000 0000",
                address="Somewhere",
                maps_url="https://maps.google.com/?cid=123",
            )
        ],
    )

    leads, _elapsed, _csv_path = scraper.run_query(
        query="electronics store lagos",
        cfg=cfg,
        output_dir=Path(cfg.output_dir),
        checkpoints_dir=Path(cfg.checkpoint_dir),
        logger=logger,
        resume=False,
    )

    assert [lead.name for lead in leads] == ["Second Shop"]
