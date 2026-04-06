import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

import api
from scraper_models import LeadRecord


def test_get_config_no_json_flag(monkeypatch):
    class FakeConfig:
        queries = ["electronics store lagos"]
        max_results_per_query = 50
        max_scrolls_per_query = 15
        max_runtime_seconds = 0
        output_dir = "csv_exports"
        logs_dir = "logs"
        checkpoint_dir = "checkpoints"
        export_retention_minutes = 60
        headless = True
        enrich_websites = True
        enable_master_csv = False

    monkeypatch.setattr(api.AppConfig, "from_file", classmethod(lambda cls, _path: FakeConfig()))

    client = TestClient(api.app)
    response = client.get("/config")

    assert response.status_code == 200
    data = response.json()
    assert "export_json" not in data
    assert data["enrich_websites"] is True
    assert data["export_retention_minutes"] == 60
    assert data["enable_master_csv"] is False


def test_list_exports_only_returns_csv_and_filters_expired_files(tmp_path: Path, monkeypatch):
    export_dir = tmp_path / "csv_exports"
    export_dir.mkdir()
    fresh = export_dir / "leads_sample.csv"
    expired = export_dir / "leads_old.csv"
    fresh.write_text("query,name\nq,shop\n", encoding="utf-8")
    expired.write_text("query,name\nq,old shop\n", encoding="utf-8")
    (export_dir / "leads_sample.json").write_text("[]", encoding="utf-8")

    stale_time = (datetime.now() - timedelta(minutes=120)).timestamp()
    os.utime(expired, (stale_time, stale_time))

    monkeypatch.chdir(tmp_path)
    client = TestClient(api.app)
    response = client.get("/exports")

    assert response.status_code == 200
    data = response.json()
    assert [item["filename"] for item in data] == ["leads_sample.csv"]
    assert data[0]["expires_at"] is not None
    assert not expired.exists()


def test_list_exports_keeps_running_job_export_file(tmp_path: Path, monkeypatch):
    export_dir = tmp_path / "csv_exports"
    export_dir.mkdir()
    protected = export_dir / "leads_running.csv"
    protected.write_text("query,name\nq,shop\n", encoding="utf-8")
    stale_time = (datetime.now() - timedelta(minutes=120)).timestamp()
    os.utime(protected, (stale_time, stale_time))

    job = api.JobStatus(
        job_id="job-running",
        status="running",
        created_at=datetime.now().isoformat(),
        queries=["electronics store lagos"],
        queries_total=1,
        progress=api.JobProgress(phase="running"),
        results=[
            api.QueryResult(
                query="electronics store lagos",
                leads_count=1,
                elapsed_seconds=10.0,
                csv_path=str(protected),
            )
        ],
    )
    with api._jobs_lock:
        api._jobs[job.job_id] = job

    monkeypatch.chdir(tmp_path)
    client = TestClient(api.app)
    response = client.get("/exports")

    assert response.status_code == 200
    assert protected.exists()
    with api._jobs_lock:
        api._jobs.pop(job.job_id, None)


def test_download_export_rejects_path_traversal(tmp_path: Path, monkeypatch):
    export_dir = tmp_path / "csv_exports"
    export_dir.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("secret", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    client = TestClient(api.app)
    response = client.get("/exports/../outside.csv")

    assert response.status_code == 404


def test_download_job_csv_uses_query_and_timestamp_filename():
    client = TestClient(api.app)
    job = api.JobStatus(
        job_id="job123",
        status="completed",
        created_at="2026-04-04T03:27:42",
        completed_at="2026-04-04T03:30:48",
        queries_total=1,
        queries_done=1,
        results=[
            api.QueryResult(
                query="electronics store lagos",
                leads_count=1,
                elapsed_seconds=10.0,
                csv_path="csv_exports/leads_electronics-store-lagos.csv",
            )
        ],
        leads=[
            api.LeadOut(
                query="electronics store lagos",
                name="Shop",
                phone="08000000000",
                address="Somewhere",
                email="N/A",
                owner_name="N/A",
                website="N/A",
                maps_url="N/A",
                category="N/A",
                social_links=[],
                scraped_at="2026-04-04 03:30:48",
                confidence_score=0.45,
            )
        ],
        summary={"total_leads": 1},
    )
    with api._jobs_lock:
        api._jobs[job.job_id] = job

    response = client.get(f"/scrape/{job.job_id}/csv")

    assert response.status_code == 200
    assert (
        response.headers["content-disposition"]
        == "attachment; filename=leads_electronics-store-lagos_2026-04-04_03-30-48am.csv"
    )
    with api._jobs_lock:
        api._jobs.pop(job.job_id, None)


def test_get_dedupe_status_returns_alias_count(tmp_path: Path, monkeypatch):
    dedupe_db = tmp_path / "checkpoints" / "seen_leads.sqlite3"
    api.save_seen_leads(
        dedupe_db,
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

    class FakeConfig:
        queries = ["electronics store lagos"]
        max_results_per_query = 50
        max_scrolls_per_query = 15
        max_runtime_seconds = 0
        output_dir = "csv_exports"
        logs_dir = "logs"
        checkpoint_dir = str(tmp_path / "checkpoints")
        dedupe_db_path = str(dedupe_db)
        export_retention_minutes = 60
        headless = True
        enrich_websites = True
        enable_master_csv = False

    monkeypatch.setattr(api.AppConfig, "from_file", classmethod(lambda cls, _path: FakeConfig()))

    client = TestClient(api.app)
    response = client.get("/dedupe/status")

    assert response.status_code == 200
    data = response.json()
    assert data == {"alias_count": 3}
