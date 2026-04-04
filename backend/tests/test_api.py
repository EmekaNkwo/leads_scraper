from pathlib import Path

from fastapi.testclient import TestClient

import api


def test_get_config_no_json_flag(monkeypatch):
    class FakeConfig:
        queries = ["electronics store lagos"]
        max_results_per_query = 50
        max_scrolls_per_query = 15
        max_runtime_seconds = 0
        output_dir = "csv_exports"
        logs_dir = "logs"
        checkpoint_dir = "checkpoints"
        archive_after_days = 14
        headless = True
        enrich_websites = True

    monkeypatch.setattr(api.AppConfig, "from_file", classmethod(lambda cls, _path: FakeConfig()))

    client = TestClient(api.app)
    response = client.get("/config")

    assert response.status_code == 200
    data = response.json()
    assert "export_json" not in data
    assert data["enrich_websites"] is True


def test_list_exports_only_returns_csv(tmp_path: Path, monkeypatch):
    export_dir = tmp_path / "csv_exports"
    export_dir.mkdir()
    (export_dir / "leads_sample.csv").write_text("query,name\nq,shop\n", encoding="utf-8")
    (export_dir / "leads_sample.json").write_text("[]", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    client = TestClient(api.app)
    response = client.get("/exports")

    assert response.status_code == 200
    data = response.json()
    assert [item["filename"] for item in data] == ["leads_sample.csv"]


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
