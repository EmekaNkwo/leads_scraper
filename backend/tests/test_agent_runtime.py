import asyncio
from types import SimpleNamespace
from pathlib import Path

import pytest

from agent_runtime import (
    AgentAnalysis,
    AgentProgress,
    AgentRunCancelled,
    AgentRunRequest,
    AgentRunStatus,
    AgentRunStore,
    AgentWorkflowRunner,
    analyze_scrape_payload,
    build_agent_queries,
)


class RunHarness:
    def __init__(self) -> None:
        self.history: list[AgentRunStatus] = []
        self.run = AgentRunStatus(
            run_id="agent-test",
            status="pending",
            created_at="2026-04-06T12:00:00",
            goal="Find wholesale electronics suppliers in Ikeja with reachable websites",
            progress=AgentProgress(phase="queued", updated_at="2026-04-06T12:00:00"),
            analysis=AgentAnalysis(),
        )

    def update(self, recent_event: str | None = None, **updates):
        payload = self.run.model_dump()
        payload.update({key: value for key, value in updates.items() if value is not None})
        if recent_event is not None:
            payload["recent_events"] = (self.run.recent_events + [recent_event])[-8:]
        self.run = AgentRunStatus.model_validate(payload)
        self.history.append(self.run.model_copy(deep=True))
        return self.run


def test_build_agent_queries_respects_limit_and_dedupes():
    queries = build_agent_queries(
        "Find wholesale electronics suppliers in Ikeja with reachable websites",
        max_queries=4,
    )

    assert len(queries) == 4
    assert len(set(q.casefold() for q in queries)) == 4
    assert queries[0] == "wholesale electronics suppliers in Ikeja with reachable websites"


def test_analyze_scrape_payload_tolerates_invalid_confidence_score():
    analysis = analyze_scrape_payload(
        {
            "status": "completed",
            "leads": [
                {
                    "name": "Shop",
                    "query": "electronics shops ikeja",
                    "email": "owner@example.com",
                    "website": "https://example.com",
                    "owner_name": "Ada",
                    "confidence_score": "not-a-number",
                }
            ],
        }
    )

    assert analysis.total_leads == 1
    assert analysis.top_leads[0].score == 0.7
    assert "has direct email" in analysis.top_leads[0].reasons


def test_analyze_scrape_payload_returns_all_ranked_leads():
    analysis = analyze_scrape_payload(
        {
            "status": "completed",
            "leads": [
                {
                    "name": f"Shop {index}",
                    "query": "electronics shops ikeja",
                    "email": "owner@example.com" if index % 2 == 0 else "N/A",
                    "website": "https://example.com" if index % 3 == 0 else "N/A",
                    "owner_name": "Ada" if index % 4 == 0 else "N/A",
                    "confidence_score": 0.1 * index,
                }
                for index in range(7)
            ],
        }
    )

    assert analysis.total_leads == 7
    assert len(analysis.top_leads) == 7
    assert analysis.top_leads[0].score >= analysis.top_leads[-1].score


def test_agent_workflow_runner_completes_happy_path():
    harness = RunHarness()
    scrape_updates = [
        {"job_id": "scrape-1", "status": "running", "progress": {"message": "Scraping in progress"}},
        {
            "job_id": "scrape-1",
            "status": "completed",
            "combined_csv_filename": "leads_restaurants-lagos.csv",
            "combined_csv_expires_at": "2026-04-07T23:59:59",
            "progress": {"message": "Scrape complete"},
            "leads": [
                {
                    "name": "Shop",
                    "query": "electronics shops ikeja",
                    "email": "owner@example.com",
                    "website": "https://example.com",
                    "owner_name": "Ada",
                    "confidence_score": 0.8,
                }
            ],
        },
    ]

    runner = AgentWorkflowRunner(
        run_id=harness.run.run_id,
        update_run=harness.update,
        is_cancel_requested=lambda: False,
        create_scrape_job=lambda payload: SimpleNamespace(job_id="scrape-1", status="pending"),
        get_scrape_job=lambda _job_id: scrape_updates.pop(0),
        cancel_scrape_job=lambda _job_id: None,
        poll_interval_seconds=0,
    )

    asyncio.run(
        runner.run(
            AgentRunRequest(
                goal="Find wholesale electronics suppliers in Ikeja with reachable websites",
                max_queries=3,
            )
        )
    )

    assert harness.run.status == "completed"
    assert harness.run.scrape_job_id == "scrape-1"
    assert harness.run.analysis is not None
    assert harness.run.analysis.total_leads == 1
    assert harness.run.analysis.top_leads[0].name == "Shop"
    assert harness.run.linked_export_filename == "leads_restaurants-lagos.csv"


def test_agent_workflow_runner_raises_when_cancelled_before_planning():
    harness = RunHarness()
    runner = AgentWorkflowRunner(
        run_id=harness.run.run_id,
        update_run=harness.update,
        is_cancel_requested=lambda: True,
        create_scrape_job=lambda payload: SimpleNamespace(job_id="scrape-1", status="pending"),
        get_scrape_job=lambda _job_id: None,
        cancel_scrape_job=lambda _job_id: None,
        poll_interval_seconds=0,
    )

    with pytest.raises(AgentRunCancelled):
        asyncio.run(
            runner.run(
                AgentRunRequest(
                    goal="Find wholesale electronics suppliers in Ikeja with reachable websites",
                    max_queries=2,
                )
            )
        )


def test_agent_workflow_runner_keeps_cancelled_status_consistent():
    harness = RunHarness()
    cancel_checks = iter([False, False, True, True])
    scrape_updates = [
        {"job_id": "scrape-1", "status": "running", "progress": {"message": "Scraping in progress"}},
        {
            "job_id": "scrape-1",
            "status": "cancelled",
            "progress": {"message": "Scrape cancelled"},
            "leads": [],
        },
    ]
    cancelled_jobs: list[str] = []

    runner = AgentWorkflowRunner(
        run_id=harness.run.run_id,
        update_run=harness.update,
        is_cancel_requested=lambda: next(cancel_checks, True),
        create_scrape_job=lambda payload: SimpleNamespace(job_id="scrape-1", status="pending"),
        get_scrape_job=lambda _job_id: scrape_updates.pop(0),
        cancel_scrape_job=lambda job_id: cancelled_jobs.append(job_id),
        poll_interval_seconds=0,
    )

    asyncio.run(
        runner.run(
            AgentRunRequest(
                goal="Find wholesale electronics suppliers in Ikeja with reachable websites",
                max_queries=3,
            )
        )
    )

    assert cancelled_jobs == ["scrape-1"]
    assert harness.run.status == "cancelled"
    assert not any(
        snapshot.status == "running" and snapshot.scrape_job_status == "cancelled"
        for snapshot in harness.history
    )


def test_agent_run_store_retries_replace_on_permission_error(tmp_path, monkeypatch):
    store = AgentRunStore(tmp_path / "agent_runs")
    run = AgentRunStatus(
        run_id="agent-store",
        status="completed",
        created_at="2026-04-07T01:00:00",
        completed_at="2026-04-07T01:00:02",
        goal="Find electronics stores in Ikeja",
        progress=AgentProgress(phase="completed", updated_at="2026-04-07T01:00:02"),
    )
    original_replace = Path.replace
    attempts = {"count": 0}

    def flaky_replace(self: Path, target: Path):
        if self.suffix == ".tmp" and attempts["count"] < 2:
            attempts["count"] += 1
            raise PermissionError(5, "Access is denied")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr("agent_runtime.time.sleep", lambda _seconds: None)

    store.save(run)

    assert attempts["count"] == 2
    assert store.load(run.run_id) is not None
    assert not list((tmp_path / "agent_runs").glob("*.tmp"))


def test_agent_run_store_retries_replace_on_retryable_oserror(tmp_path, monkeypatch):
    store = AgentRunStore(tmp_path / "agent_runs")
    run = AgentRunStatus(
        run_id="agent-store-oserror",
        status="completed",
        created_at="2026-04-07T01:00:00",
        completed_at="2026-04-07T01:00:02",
        goal="Find electronics stores in Ikeja",
        progress=AgentProgress(phase="completed", updated_at="2026-04-07T01:00:02"),
    )
    original_replace = Path.replace
    attempts = {"count": 0}

    def flaky_replace(self: Path, target: Path):
        if self.suffix == ".tmp" and attempts["count"] < 1:
            attempts["count"] += 1
            error = OSError("Access is denied")
            error.errno = 13
            error.winerror = 32
            raise error
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr("agent_runtime.time.sleep", lambda _seconds: None)

    store.save(run)

    assert attempts["count"] == 1
    assert store.load(run.run_id) is not None


def test_agent_run_store_cleans_temp_file_when_retries_exhausted(tmp_path, monkeypatch):
    store = AgentRunStore(tmp_path / "agent_runs")
    run = AgentRunStatus(
        run_id="agent-store-fails",
        status="completed",
        created_at="2026-04-07T01:00:00",
        completed_at="2026-04-07T01:00:02",
        goal="Find electronics stores in Ikeja",
        progress=AgentProgress(phase="completed", updated_at="2026-04-07T01:00:02"),
    )

    def always_fail_replace(self: Path, target: Path):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", always_fail_replace)
    monkeypatch.setattr("agent_runtime.time.sleep", lambda _seconds: None)

    with pytest.raises(PermissionError):
        store.save(run)

    assert store.load(run.run_id) is None
    assert not list((tmp_path / "agent_runs").glob("*.tmp"))
