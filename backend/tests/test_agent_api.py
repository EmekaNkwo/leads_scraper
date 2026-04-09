from datetime import datetime
from threading import Event

from fastapi.testclient import TestClient

import api


def _clear_agent_state() -> None:
    with api._agent_runs_lock:
        api._agent_runs.clear()
        api._agent_cancel_events.clear()


def _clear_job_state() -> None:
    with api._jobs_lock:
        api._jobs.clear()
        api._job_cancel_events.clear()


def test_start_agent_run_returns_pending_and_persists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(api.app)
    started: list[str] = []

    monkeypatch.setattr(api, "_launch_agent_run", lambda run_id, req: started.append(run_id))

    response = client.post(
        "/agent/runs",
        json={
            "goal": "Find wholesale electronics suppliers in Ikeja with reachable websites",
            "max_queries": 3,
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"
    assert data["goal"].startswith("Find wholesale electronics suppliers")
    assert data["run_id"] in started
    assert (tmp_path / "agent_runs" / f"{data['run_id']}.json").exists()
    _clear_agent_state()


def test_get_agent_run_reads_from_persisted_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = api.AgentRunStore(tmp_path / "agent_runs")
    run = api.AgentRunStatus(
        run_id="agent-persisted",
        status="completed",
        created_at=datetime.now().isoformat(),
        completed_at=datetime.now().isoformat(),
        goal="Find contactable electronics shops",
        proposed_queries=["electronics shops ikeja"],
        progress=api.AgentProgress(phase="completed", message="Done", updated_at=datetime.now().isoformat()),
        analysis=api.AgentAnalysis(
            total_leads=1,
            emails_found=1,
            websites_found=1,
            top_leads=[
                api.AgentLeadInsight(
                    name="Shop",
                    query="electronics shops ikeja",
                    score=0.92,
                    email="owner@example.com",
                    website="https://example.com",
                    reasons=["has direct email", "has website"],
                )
            ],
            summary="Found one high-signal lead.",
        ),
    )
    store.save(run)

    client = TestClient(api.app)
    response = client.get("/agent/runs/agent-persisted")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["analysis"]["top_leads"][0]["name"] == "Shop"
    _clear_agent_state()


def test_get_agent_run_hydrates_linked_export_from_persisted_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job_store = api.ScrapeJobStore(tmp_path / "scrape_jobs")
    job_store.save(
        api.JobStatus(
            job_id="scrape-persisted",
            status="completed",
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            queries=["restaurants lagos"],
            queries_total=1,
            queries_done=1,
            combined_csv_filename="leads_restaurants-lagos.csv",
            combined_csv_path=str(tmp_path / "csv_exports" / "leads_restaurants-lagos.csv"),
            combined_csv_expires_at=datetime.now().isoformat(),
        )
    )
    store = api.AgentRunStore(tmp_path / "agent_runs")
    store.save(
        api.AgentRunStatus(
            run_id="agent-linked-export",
            status="completed",
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            goal="Find restaurants in Lagos",
            scrape_job_id="scrape-persisted",
            scrape_job_status="completed",
            progress=api.AgentProgress(phase="completed", message="Done", updated_at=datetime.now().isoformat()),
        )
    )

    client = TestClient(api.app)
    response = client.get("/agent/runs/agent-linked-export")

    assert response.status_code == 200
    data = response.json()
    assert data["linked_export_filename"] == "leads_restaurants-lagos.csv"
    _clear_agent_state()
    _clear_job_state()


def test_get_agent_run_overrides_stale_linked_export_from_persisted_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job_store = api.ScrapeJobStore(tmp_path / "scrape_jobs")
    job_store.save(
        api.JobStatus(
            job_id="scrape-latest-export",
            status="completed",
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            queries=["restaurants lagos"],
            queries_total=1,
            queries_done=1,
            combined_csv_filename="leads_restaurants-lagos-latest.csv",
            combined_csv_path=str(tmp_path / "csv_exports" / "leads_restaurants-lagos-latest.csv"),
            combined_csv_expires_at=datetime.now().isoformat(),
        )
    )
    store = api.AgentRunStore(tmp_path / "agent_runs")
    store.save(
        api.AgentRunStatus(
            run_id="agent-stale-export",
            status="completed",
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            goal="Find restaurants in Lagos",
            scrape_job_id="scrape-latest-export",
            scrape_job_status="completed",
            linked_export_filename="stale-export.csv",
            progress=api.AgentProgress(phase="completed", message="Done", updated_at=datetime.now().isoformat()),
        )
    )

    client = TestClient(api.app)
    response = client.get("/agent/runs/agent-stale-export")

    assert response.status_code == 200
    data = response.json()
    assert data["linked_export_filename"] == "leads_restaurants-lagos-latest.csv"
    _clear_agent_state()
    _clear_job_state()


def test_list_agent_runs_returns_newest_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = api.AgentRunStore(tmp_path / "agent_runs")
    store.save(
        api.AgentRunStatus(
            run_id="older",
            status="completed",
            created_at="2026-04-06T10:00:00",
            goal="Older run",
            progress=api.AgentProgress(phase="completed", updated_at="2026-04-06T10:01:00"),
        )
    )
    store.save(
        api.AgentRunStatus(
            run_id="newer",
            status="running",
            created_at="2026-04-06T11:00:00",
            goal="Newer run",
            progress=api.AgentProgress(phase="monitoring", updated_at="2026-04-06T11:01:00"),
        )
    )

    client = TestClient(api.app)
    response = client.get("/agent/runs")

    assert response.status_code == 200
    data = response.json()
    assert [item["run_id"] for item in data[:2]] == ["newer", "older"]
    _clear_agent_state()


def test_cancel_agent_run_marks_cancel_requested_and_scrape_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scrape_job = api.JobStatus(
        job_id="scrape-job-1",
        status="running",
        created_at=datetime.now().isoformat(),
        queries=["electronics shops ikeja"],
        queries_total=1,
        progress=api.JobProgress(phase="scraping", query="electronics shops ikeja"),
    )
    run = api.AgentRunStatus(
        run_id="agent-cancel",
        status="running",
        created_at=datetime.now().isoformat(),
        goal="Find electronics shops",
        scrape_job_id=scrape_job.job_id,
        scrape_job_status="running",
        progress=api.AgentProgress(phase="monitoring", updated_at=datetime.now().isoformat()),
    )
    with api._jobs_lock:
        api._jobs[scrape_job.job_id] = scrape_job
        api._job_cancel_events[scrape_job.job_id] = Event()
    with api._agent_runs_lock:
        api._agent_runs[run.run_id] = run
        api._agent_cancel_events[run.run_id] = Event()

    client = TestClient(api.app)
    response = client.delete("/agent/runs/agent-cancel")

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "cancel_requested"
    assert data["progress"]["phase"] == "cancel_requested"
    assert api._agent_cancel_events[run.run_id].is_set() is True
    assert api._job_cancel_events[scrape_job.job_id].is_set() is True

    with api._jobs_lock:
        api._jobs.pop(scrape_job.job_id, None)
        api._job_cancel_events.pop(scrape_job.job_id, None)
    _clear_agent_state()


def test_download_agent_run_csv_falls_back_to_persisted_export(tmp_path, monkeypatch):
    export_dir = tmp_path / "csv_exports"
    export_dir.mkdir()
    export_file = export_dir / "leads_restaurants-lagos.csv"
    export_file.write_text("query,name\nrestaurants lagos,Shop\n", encoding="utf-8")

    class FakeConfig:
        queries = ["restaurants lagos"]
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
    store = api.AgentRunStore(tmp_path / "agent_runs")
    store.save(
        api.AgentRunStatus(
            run_id="agent-export-download",
            status="completed",
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            goal="Find restaurants in Lagos",
            scrape_job_id="missing-job",
            scrape_job_status="completed",
            linked_export_filename="leads_restaurants-lagos.csv",
            linked_export_expires_at=datetime.now().isoformat(),
            progress=api.AgentProgress(phase="completed", message="Done", updated_at=datetime.now().isoformat()),
        )
    )

    client = TestClient(api.app)
    response = client.get("/agent/runs/agent-export-download/csv")

    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('"leads_restaurants-lagos.csv"')
    _clear_agent_state()
