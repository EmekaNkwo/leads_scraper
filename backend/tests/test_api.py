import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient

import api
from scraper_models import LeadRecord


def _clear_job_state() -> None:
    with api._jobs_lock:
        api._jobs.clear()
        api._job_cancel_events.clear()


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
                status="completed",
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
                status="completed",
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
        == 'attachment; filename="leads_electronics-store-lagos_2026-04-04_03-30-48am.csv"'
    )
    with api._jobs_lock:
        persisted = api._jobs[job.job_id]
        assert persisted.combined_csv_filename == "leads_electronics-store-lagos_2026-04-04_03-30-48am.csv"
    with api._jobs_lock:
        api._jobs.pop(job.job_id, None)


def test_download_job_csv_allows_cancelled_jobs_with_leads():
    client = TestClient(api.app)
    job = api.JobStatus(
        job_id="job-cancelled",
        status="cancelled",
        created_at="2026-04-04T03:27:42",
        completed_at="2026-04-04T03:30:48",
        queries_total=1,
        queries_done=1,
        results=[
            api.QueryResult(
                query="electronics store lagos",
                status="cancelled",
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
        summary={"total_leads": 1, "queries_cancelled": 1},
    )
    with api._jobs_lock:
        api._jobs[job.job_id] = job

    response = client.get(f"/scrape/{job.job_id}/csv")

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith('attachment; filename="leads_electronics-store-lagos_')
    with api._jobs_lock:
        api._jobs.pop(job.job_id, None)


def test_get_job_reads_from_persisted_store(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = api.ScrapeJobStore(tmp_path / "scrape_jobs")
    store.save(
        api.JobStatus(
            job_id="job-persisted",
            status="completed",
            created_at="2026-04-04T03:27:42",
            completed_at="2026-04-04T03:30:48",
            queries=["electronics store lagos"],
            queries_total=1,
            queries_done=1,
        )
    )

    client = TestClient(api.app)
    response = client.get("/scrape/job-persisted")

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-persisted"
    _clear_job_state()


def test_download_job_csv_reads_persisted_job_after_restart(tmp_path: Path, monkeypatch):
    export_dir = tmp_path / "csv_exports"

    class FakeConfig:
        queries = ["electronics store lagos"]
        max_results_per_query = 50
        max_scrolls_per_query = 15
        max_runtime_seconds = 0
        output_dir = str(export_dir)
        logs_dir = "logs"
        checkpoint_dir = "checkpoints"
        export_retention_minutes = 60
        headless = True
        enrich_websites = True
        enable_master_csv = False

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, "_load_runtime_config", lambda: FakeConfig())
    store = api.ScrapeJobStore(tmp_path / "scrape_jobs")
    store.save(
        api.JobStatus(
            job_id="job-restart",
            status="completed",
            created_at="2026-04-04T03:27:42",
            completed_at="2026-04-04T03:30:48",
            queries=["electronics store lagos"],
            queries_total=1,
            queries_done=1,
            results=[
                api.QueryResult(
                    query="electronics store lagos",
                    status="completed",
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
    )

    client = TestClient(api.app)
    response = client.get("/scrape/job-restart/csv")

    assert response.status_code == 200
    assert (export_dir / "leads_electronics-store-lagos_2026-04-04_03-30-48am.csv").exists()
    _clear_job_state()


def test_get_job_marks_persisted_running_job_failed_after_restart(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = api.ScrapeJobStore(tmp_path / "scrape_jobs")
    store.save(
        api.JobStatus(
            job_id="job-running-persisted",
            status="running",
            created_at="2026-04-04T03:27:42",
            queries=["electronics store lagos"],
            queries_total=1,
            progress=api.JobProgress(
                query="electronics store lagos",
                phase="scraping",
                message="Still scraping",
            ),
        )
    )

    client = TestClient(api.app)
    response = client.get("/scrape/job-running-persisted")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["progress"]["end_reason"] == "unexpected_restart"
    _clear_job_state()


def test_download_job_csv_rejects_tampered_combined_filename(tmp_path: Path, monkeypatch):
    export_dir = tmp_path / "csv_exports"
    export_dir.mkdir()

    class FakeConfig:
        queries = ["electronics store lagos"]
        max_results_per_query = 50
        max_scrolls_per_query = 15
        max_runtime_seconds = 0
        output_dir = str(export_dir)
        logs_dir = "logs"
        checkpoint_dir = "checkpoints"
        export_retention_minutes = 60
        headless = True
        enrich_websites = True
        enable_master_csv = False

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, "_load_runtime_config", lambda: FakeConfig())
    store = api.ScrapeJobStore(tmp_path / "scrape_jobs")
    store.save(
        api.JobStatus(
            job_id="job-tampered-csv",
            status="completed",
            created_at="2026-04-04T03:27:42",
            completed_at="2026-04-04T03:30:48",
            queries=["electronics store lagos"],
            queries_total=1,
            queries_done=1,
            combined_csv_filename="../secret.csv",
            combined_csv_path=str(tmp_path / "secret.csv"),
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
    )

    client = TestClient(api.app)
    response = client.get("/scrape/job-tampered-csv/csv")

    assert response.status_code == 200
    assert "../" not in response.headers["content-disposition"]
    assert "secret.csv" not in response.headers["content-disposition"]
    _clear_job_state()


def test_build_job_summary_counts_cancelled_queries():
    job = api.JobStatus(
        job_id="job-summary",
        status="cancelled",
        created_at=datetime.now().isoformat(),
        queries=["electronics store lagos"],
        queries_total=3,
        results=[
            api.QueryResult(
                query="electronics store lagos",
                status="completed",
                leads_count=2,
                elapsed_seconds=10.0,
                csv_path="csv_exports/leads_1.csv",
            ),
            api.QueryResult(
                query="computer shop ikeja",
                status="failed",
                leads_count=0,
                elapsed_seconds=0.0,
                csv_path="",
                error="boom",
            ),
            api.QueryResult(
                query="phone store yaba",
                status="cancelled",
                leads_count=1,
                elapsed_seconds=5.0,
                csv_path="csv_exports/leads_2.csv",
            ),
        ],
        leads=[
            api.LeadOut(query="electronics store lagos", name="A", phone="N/A", address="N/A", email="x@example.com", owner_name="N/A", website="https://example.com", maps_url="N/A", category="N/A", social_links=[], scraped_at="2026-04-06 13:00:00", confidence_score=0.5),
            api.LeadOut(query="phone store yaba", name="B", phone="N/A", address="N/A", email="N/A", owner_name="N/A", website="N/A", maps_url="N/A", category="N/A", social_links=[], scraped_at="2026-04-06 13:00:00", confidence_score=0.5),
        ],
    )

    assert api._build_job_summary(job) == {
        "total_leads": 2,
        "emails_found": 1,
        "websites_found": 1,
        "queries_succeeded": 1,
        "queries_failed": 1,
        "queries_cancelled": 1,
    }


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


def test_cancel_running_job_requests_cancellation():
    client = TestClient(api.app)
    job = api.JobStatus(
        job_id="job-cancel",
        status="running",
        created_at=datetime.now().isoformat(),
        queries=["electronics store lagos"],
        queries_total=1,
        progress=api.JobProgress(phase="scraping", query="electronics store lagos"),
    )
    with api._jobs_lock:
        api._jobs[job.job_id] = job
        api._job_cancel_events[job.job_id] = Event()

    response = client.delete(f"/scrape/{job.job_id}")

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "running"
    assert data["progress"]["phase"] == "cancel_requested"
    assert data["progress"]["end_reason"] == "cancel_requested"
    assert api._job_cancel_events[job.job_id].is_set() is True

    with api._jobs_lock:
        api._jobs.pop(job.job_id, None)
        api._job_cancel_events.pop(job.job_id, None)


def test_run_job_marks_failed_on_unexpected_exception(monkeypatch):
    job_id = "job-crash"
    request = api.ScrapeRequest(queries=["electronics store lagos"])
    job = api.JobStatus(
        job_id=job_id,
        status="pending",
        created_at=datetime.now().isoformat(),
        queries=request.queries,
        queries_total=1,
    )

    with api._jobs_lock:
        api._jobs[job_id] = job
        api._job_cancel_events[job_id] = Event()

    monkeypatch.setattr(api, "_cleanup_runtime_files", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    api._run_job(job_id, request)

    with api._jobs_lock:
        failed_job = api._jobs[job_id]
        assert failed_job.status == "failed"
        assert failed_job.completed_at is not None
        assert failed_job.progress is not None
        assert failed_job.progress.end_reason == "unexpected_error"
        assert "Job failed unexpectedly: boom" in failed_job.recent_events[-1]
        api._jobs.pop(job_id, None)
