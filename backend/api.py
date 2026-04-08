from __future__ import annotations

import asyncio
import contextlib
import csv
import json
import logging
import re
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent_runtime import (
    AgentAnalysis,
    AgentLeadInsight,
    AgentProgress,
    AgentRunCancelled,
    AgentRunRequest,
    AgentRunStatus,
    AgentRunStore,
    AgentWorkflowRunner,
)
from scraper import run_query
from scraper_config import AppConfig
from scraper_dedupe_store import count_seen_aliases, save_seen_leads
from scraper_models import LeadRecord
from scraper_utils import cleanup_expired_files, path_expiration, setup_logger, slugify

app = FastAPI(
    title="Leads Scraper API",
    description=(
        "Google Maps leads scraper with enrichment and export pipeline. "
        "Submit scraping jobs, poll for results, download CSV exports, "
        "or run the lightweight LangGraph-based agent supervisor."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

api_logger = logging.getLogger("uvicorn.error")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    queries: list[str] = Field(
        ...,
        min_length=1,
        examples=[["electronics store lagos", "computer shop ikeja"]],
        description="One or more Google Maps search queries.",
    )
    max_results_per_query: int = Field(30, ge=1, le=500, description="Stop after N leads per query.")
    max_scrolls_per_query: int = Field(15, ge=1, le=100, description="Max scroll iterations in the results pane.")
    max_runtime_seconds: int = Field(0, ge=0, le=3600, description="Per-query time limit in seconds. 0 = no limit.")
    headless: bool = Field(True, description="Run browser in headless mode.")
    enrich_websites: bool = Field(True, description="Visit each business website to extract email/owner hints.")
    resume: bool = Field(False, description="Resume from checkpoint if available for a query.")


class LeadOut(BaseModel):
    query: str
    name: str
    phone: str
    address: str
    email: str
    owner_name: str
    website: str
    maps_url: str
    category: str
    social_links: list[str]
    scraped_at: str
    confidence_score: float


class QueryResult(BaseModel):
    query: str
    status: str = Field(description="completed | failed | cancelled")
    leads_count: int
    elapsed_seconds: float
    csv_path: str
    export_expires_at: str | None = None
    error: str | None = None


class JobProgress(BaseModel):
    query: str | None = None
    phase: str = "idle"
    leads_collected: int = 0
    leads_target: int = 0
    visible_cards: int = 0
    scrolls_used: int = 0
    max_scrolls: int = 0
    stale_scrolls: int = 0
    message: str | None = None
    end_reason: str | None = None
    elapsed_seconds: float | None = None
    csv_path: str | None = None
    export_expires_at: str | None = None
    updated_at: str | None = None


class JobStatus(BaseModel):
    job_id: str
    status: str = Field(description="pending | running | completed | failed | cancelled")
    created_at: str
    completed_at: str | None = None
    queries: list[str] = Field(default_factory=list)
    queries_total: int
    queries_done: int = 0
    results: list[QueryResult] = Field(default_factory=list)
    leads: list[LeadOut] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    progress: JobProgress | None = None
    recent_events: list[str] = Field(default_factory=list)
    export_retention_minutes: int = 0
    exports_are_temporary: bool = True
    master_csv_enabled: bool = True
    combined_csv_filename: str | None = None
    combined_csv_path: str | None = None
    combined_csv_expires_at: str | None = None


class ExportFile(BaseModel):
    filename: str
    size_bytes: int
    modified_at: str
    expires_at: str | None = None


class ConfigOut(BaseModel):
    queries: list[str]
    max_results_per_query: int
    max_scrolls_per_query: int
    max_runtime_seconds: int
    output_dir: str
    logs_dir: str
    checkpoint_dir: str
    export_retention_minutes: int
    headless: bool
    enrich_websites: bool
    enable_master_csv: bool


class HealthOut(BaseModel):
    status: str
    version: str
    uptime_seconds: float


class DedupeStatusOut(BaseModel):
    alias_count: int


class ScrapeJobStore:
    _replace_retries = 5
    _replace_retry_delay_seconds = 0.05
    _retryable_winerrors = {5, 32}
    _retryable_errnos = {13}

    def __init__(self, directory: Path):
        self.directory = directory

    def _is_valid_job_id(self, job_id: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_-]+", job_id))

    def _path_for(self, job_id: str) -> Path:
        if not self._is_valid_job_id(job_id):
            raise ValueError(f"Invalid job id: {job_id}")
        return self.directory / f"{job_id}.json"

    def _temp_path_for(self, job_id: str) -> Path:
        if not self._is_valid_job_id(job_id):
            raise ValueError(f"Invalid job id: {job_id}")
        return self.directory / f"{job_id}.{uuid.uuid4().hex}.tmp"

    def _is_retryable_replace_error(self, exc: OSError) -> bool:
        if isinstance(exc, PermissionError):
            return True
        return getattr(exc, "winerror", None) in self._retryable_winerrors or getattr(exc, "errno", None) in self._retryable_errnos

    def _replace_with_retry(self, temp_path: Path, path: Path) -> None:
        for attempt in range(self._replace_retries):
            try:
                temp_path.replace(path)
                return
            except OSError as exc:
                if not self._is_retryable_replace_error(exc):
                    raise
                if attempt == self._replace_retries - 1:
                    raise
                time.sleep(self._replace_retry_delay_seconds * (attempt + 1))

    def save(self, job: JobStatus) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for(job.job_id)
        temp_path = self._temp_path_for(job.job_id)
        try:
            temp_path.write_text(job.model_dump_json(indent=2), encoding="utf-8")
            self._replace_with_retry(temp_path, path)
        finally:
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)

    def load(self, job_id: str) -> JobStatus | None:
        if not self._is_valid_job_id(job_id):
            return None
        path = self._path_for(job_id)
        if not path.exists():
            return None
        return JobStatus.model_validate_json(path.read_text(encoding="utf-8"))

    def list_jobs(self, limit: int = 20) -> list[JobStatus]:
        if not self.directory.exists():
            return []
        jobs: list[JobStatus] = []
        for path in self.directory.glob("*.json"):
            try:
                jobs.append(JobStatus.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return jobs[:limit]


# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

_jobs: dict[str, JobStatus] = {}
_job_cancel_events: dict[str, Event] = {}
_jobs_lock = Lock()
_agent_runs: dict[str, AgentRunStatus] = {}
_agent_cancel_events: dict[str, Event] = {}
_agent_runs_lock = Lock()
_start_time = time.time()
_NON_TERMINAL_JOB_STATUSES = {"pending", "running", "cancel_requested"}


def _load_runtime_config() -> AppConfig:
    return AppConfig.from_file("scraper_config.json")


def _agent_store() -> AgentRunStore:
    return AgentRunStore(Path("agent_runs"))


def _job_store() -> ScrapeJobStore:
    return ScrapeJobStore(Path("scrape_jobs"))


def _save_job_locked(job: JobStatus) -> JobStatus:
    job_copy = job.model_copy(deep=True)
    _jobs[job_copy.job_id] = job_copy
    _job_store().save(job_copy)
    return job_copy.model_copy(deep=True)


def _save_job(job: JobStatus) -> JobStatus:
    with _jobs_lock:
        return _save_job_locked(job)


def _save_agent_run(run: AgentRunStatus) -> AgentRunStatus:
    with _agent_runs_lock:
        run_copy = run.model_copy(deep=True)
        _agent_runs[run_copy.run_id] = run_copy
        _agent_store().save(run_copy)
        return run_copy.model_copy(deep=True)


def _get_agent_run(run_id: str) -> AgentRunStatus | None:
    cached_copy: AgentRunStatus | None = None
    with _agent_runs_lock:
        cached = _agent_runs.get(run_id)
        if cached is not None:
            cached_copy = cached.model_copy(deep=True)
    if cached_copy is not None:
        return _hydrate_agent_linked_export(cached_copy)
    stored = _agent_store().load(run_id)
    if stored is None:
        return None
    with _agent_runs_lock:
        _agent_runs[run_id] = stored
    return _hydrate_agent_linked_export(stored.model_copy(deep=True))


def _get_job_store_snapshot(job_id: str) -> JobStatus | None:
    stored = _job_store().load(job_id)
    if stored is None:
        return None
    normalized = _normalize_persisted_job(stored)
    with _jobs_lock:
        _jobs[job_id] = normalized
    return normalized.model_copy(deep=True)


def _hydrate_agent_linked_export(run: AgentRunStatus) -> AgentRunStatus:
    if not run.scrape_job_id:
        return run
    scrape_job = _get_job_snapshot(run.scrape_job_id)
    if scrape_job is None:
        return run
    if not scrape_job.combined_csv_filename:
        if run.linked_export_filename is None and run.linked_export_expires_at is None:
            return run
        return run.model_copy(update={"linked_export_filename": None, "linked_export_expires_at": None})
    if (
        run.linked_export_filename == scrape_job.combined_csv_filename
        and run.linked_export_expires_at == scrape_job.combined_csv_expires_at
    ):
        return run
    return run.model_copy(
        update={
            "linked_export_filename": scrape_job.combined_csv_filename,
            "linked_export_expires_at": scrape_job.combined_csv_expires_at,
        },
    )


def _list_agent_runs(limit: int) -> list[AgentRunStatus]:
    combined: dict[str, AgentRunStatus] = {
        run.run_id: run for run in _agent_store().list_runs(limit=max(limit, 100))
    }
    with _agent_runs_lock:
        for run in _agent_runs.values():
            combined[run.run_id] = run.model_copy(deep=True)
    runs = list(combined.values())
    runs.sort(key=lambda run: run.created_at, reverse=True)
    return [_hydrate_agent_linked_export(run) for run in runs[:limit]]


def _is_agent_cancel_requested(run_id: str) -> bool:
    cancel_event = _agent_cancel_events.get(run_id)
    return cancel_event.is_set() if cancel_event else False


def _update_agent_run(run_id: str, recent_event: str | None = None, **updates: object) -> AgentRunStatus:
    with _agent_runs_lock:
        run = _agent_runs.get(run_id)
        if run is None:
            stored = _agent_store().load(run_id)
            if stored is None:
                raise KeyError(run_id)
            run = stored
            _agent_runs[run_id] = stored
        if "progress" in updates and updates["progress"] is not None:
            updates["progress"] = AgentProgress.model_validate(updates["progress"])
        if "analysis" in updates and updates["analysis"] is not None:
            updates["analysis"] = AgentAnalysis.model_validate(updates["analysis"])
        payload = run.model_dump()
        payload.update({key: value for key, value in updates.items() if value is not None})
        if recent_event is not None:
            payload["recent_events"] = (run.recent_events + [recent_event])[-8:]
        updated = AgentRunStatus.model_validate(payload)
        _agent_runs[run_id] = updated
        _agent_store().save(updated)
        return updated.model_copy(deep=True)


def _protected_runtime_paths(cfg: AppConfig) -> set[Path]:
    protected: set[Path] = set()
    checkpoint_dir = Path(cfg.checkpoint_dir)
    with _jobs_lock:
        active_jobs = [job for job in _jobs.values() if job.status in {"pending", "running"}]

    for job in active_jobs:
        if job.combined_csv_path:
            protected.add(Path(job.combined_csv_path))
        for result in job.results:
            if result.csv_path:
                protected.add(Path(result.csv_path))
        for query in job.queries:
            protected.add(checkpoint_dir / f"{slugify(query)}.json")
    return protected


def _cleanup_runtime_files(cfg: AppConfig, include_all: bool = True) -> int:
    paths = [Path(cfg.output_dir)]
    patterns = ["leads_*.csv"]
    if include_all:
        paths.extend([Path(cfg.checkpoint_dir), Path(cfg.logs_dir)])
        patterns.extend(["*.json", "*.log"])

    return cleanup_expired_files(
        paths,
        cfg.export_retention_minutes,
        patterns,
        protected_paths=_protected_runtime_paths(cfg),
    )


def _build_job_summary(job: JobStatus) -> dict[str, int]:
    return {
        "total_leads": len(job.leads),
        "emails_found": sum(1 for lead in job.leads if lead.email != "N/A"),
        "websites_found": sum(1 for lead in job.leads if lead.website != "N/A"),
        "queries_succeeded": sum(1 for result in job.results if result.status == "completed"),
        "queries_failed": sum(1 for result in job.results if result.status == "failed"),
        "queries_cancelled": sum(1 for result in job.results if result.status == "cancelled"),
    }


def _is_cancel_requested(job_id: str) -> bool:
    cancel_event = _job_cancel_events.get(job_id)
    return cancel_event.is_set() if cancel_event else False


def _list_jobs(limit: int) -> list[JobStatus]:
    combined: dict[str, JobStatus] = {
        job.job_id: _normalize_persisted_job(job)
        for job in _job_store().list_jobs(limit=max(limit, 100))
    }
    with _jobs_lock:
        for job in _jobs.values():
            combined[job.job_id] = job.model_copy(deep=True)
    jobs = list(combined.values())
    jobs.sort(key=lambda job: job.created_at, reverse=True)
    return jobs[:limit]


def _update_job_progress(job: JobStatus, update: dict[str, object]) -> None:
    previous = job.progress or JobProgress()
    message = update.get("message")
    if "end_reason" in update:
        if update["end_reason"] is not None:
            end_reason = str(update["end_reason"])
        elif previous.end_reason == "cancel_requested":
            end_reason = previous.end_reason
        else:
            end_reason = None
    else:
        end_reason = previous.end_reason
    job.progress = JobProgress(
        query=str(update.get("query")) if update.get("query") is not None else previous.query,
        phase=str(update.get("phase", previous.phase)),
        leads_collected=int(update.get("leads_collected", previous.leads_collected)),
        leads_target=int(update.get("leads_target", previous.leads_target)),
        visible_cards=int(update.get("visible_cards", previous.visible_cards)),
        scrolls_used=int(update.get("scrolls_used", previous.scrolls_used)),
        max_scrolls=int(update.get("max_scrolls", previous.max_scrolls)),
        stale_scrolls=int(update.get("stale_scrolls", previous.stale_scrolls)),
        message=str(message) if message is not None else previous.message,
        end_reason=end_reason,
        elapsed_seconds=float(update.get("elapsed_seconds")) if update.get("elapsed_seconds") is not None else previous.elapsed_seconds,
        csv_path=str(update.get("csv_path")) if update.get("csv_path") is not None else previous.csv_path,
        export_expires_at=(
            str(update.get("export_expires_at"))
            if update.get("export_expires_at") is not None
            else previous.export_expires_at
        ),
        updated_at=datetime.now().isoformat(),
    )
    if message is not None:
        job.recent_events = (job.recent_events + [str(message)])[-8:]


def _lead_to_out(lead: LeadRecord) -> LeadOut:
    return LeadOut(
        query=lead.query,
        name=lead.name,
        phone=lead.phone,
        address=lead.address,
        email=lead.email,
        owner_name=lead.owner_name,
        website=lead.website,
        maps_url=lead.maps_url,
        category=lead.category,
        social_links=lead.social_links,
        scraped_at=lead.scraped_at,
        confidence_score=lead.confidence_score,
    )


def _job_csv_filename(job: JobStatus) -> str:
    timestamp_source = job.completed_at or job.created_at
    try:
        timestamp = datetime.fromisoformat(timestamp_source).strftime("%Y-%m-%d_%I-%M-%S%p").lower()
    except ValueError:
        timestamp = datetime.now().strftime("%Y-%m-%d_%I-%M-%S%p").lower()
    unique_queries = sorted({result.query for result in job.results if result.query})
    query_slug = slugify(unique_queries[0]) if len(unique_queries) == 1 else "combined-job"
    return f"leads_{query_slug}_{timestamp}.csv"


def _resolve_export_filepath(filename: str, must_exist: bool = False) -> Path | None:
    export_dir = Path(_load_runtime_config().output_dir).resolve()
    requested = Path(filename)
    filepath = (export_dir / requested).resolve()
    if (
        requested.name != filename
        or filepath.parent != export_dir
        or filepath.suffix != ".csv"
        or (must_exist and (not filepath.exists() or not filepath.is_file()))
    ):
        return None
    return filepath


def _write_combined_job_csv(job: JobStatus, output_dir: Path, retention_minutes: int) -> None:
    if not job.leads:
        job.combined_csv_filename = None
        job.combined_csv_path = None
        job.combined_csv_expires_at = None
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = _job_csv_filename(job)
    filepath = output_dir / filename
    fields = list(LeadOut.model_fields.keys())
    with filepath.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for lead in job.leads:
            row = lead.model_dump()
            row["social_links"] = ";".join(row["social_links"])
            writer.writerow(row)

    job.combined_csv_filename = filename
    job.combined_csv_path = str(filepath)
    job.combined_csv_expires_at = (
        path_expiration(filepath, retention_minutes).isoformat() if retention_minutes > 0 else None
    )


def _ensure_job_export(job: JobStatus) -> JobStatus:
    if not job.leads:
        return job
    output_dir = Path(_load_runtime_config().output_dir)
    filepath = (
        _resolve_export_filepath(job.combined_csv_filename, must_exist=True)
        if job.combined_csv_filename
        else None
    )
    if filepath is not None:
        return job

    refreshed = job.model_copy(deep=True)
    _write_combined_job_csv(refreshed, output_dir, refreshed.export_retention_minutes)
    return _save_job(refreshed)


def _normalize_persisted_job(job: JobStatus) -> JobStatus:
    if job.status not in _NON_TERMINAL_JOB_STATUSES:
        return job

    resumed = job.model_copy(deep=True)
    resumed.completed_at = resumed.completed_at or datetime.now().isoformat()
    resumed.summary = _build_job_summary(resumed)
    was_cancel_requested = resumed.status == "cancel_requested" or (
        resumed.progress is not None and resumed.progress.end_reason == "cancel_requested"
    )
    resumed.status = "cancelled" if was_cancel_requested else "failed"
    _update_job_progress(
        resumed,
        {
            "query": resumed.progress.query if resumed.progress else (resumed.queries[0] if resumed.queries else None),
            "phase": resumed.status,
            "message": (
                "Job cancellation finished after the server restarted."
                if was_cancel_requested
                else "Job stopped when the server restarted before the scrape could finish."
            ),
            "end_reason": "cancel_requested" if was_cancel_requested else "unexpected_restart",
        },
    )
    if resumed.leads:
        _write_combined_job_csv(resumed, Path(_load_runtime_config().output_dir), resumed.export_retention_minutes)
    _job_store().save(resumed)
    return resumed


def _csv_stream_response(filepath: Path, filename: str) -> FileResponse:
    return FileResponse(filepath, media_type="text/csv", filename=filename)


def _create_scrape_job(req: ScrapeRequest) -> JobStatus:
    cfg = _load_runtime_config()
    job_id = uuid.uuid4().hex[:12]
    job = JobStatus(
        job_id=job_id,
        status="pending",
        created_at=datetime.now().isoformat(),
        queries=req.queries,
        queries_total=len(req.queries),
        export_retention_minutes=cfg.export_retention_minutes,
        exports_are_temporary=cfg.export_retention_minutes > 0,
        master_csv_enabled=cfg.enable_master_csv,
    )
    with _jobs_lock:
        _job_cancel_events[job_id] = Event()
        _save_job_locked(job)
    api_logger.info("job=%s submitted queries=%s", job_id, req.queries)
    Thread(target=_run_job, args=(job_id, req), daemon=True).start()
    return job.model_copy(deep=True)


def _get_job_snapshot(job_id: str) -> JobStatus | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None:
            return job.model_copy(deep=True)
    return _get_job_store_snapshot(job_id)


def _request_job_cancel(job_id: str) -> JobStatus:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            stored = _job_store().load(job_id)
            if stored is None:
                raise KeyError(job_id)
            job = stored
            _jobs[job_id] = stored
        if job.status in {"completed", "failed", "cancelled"}:
            return job.model_copy(deep=True)

        cancel_event = _job_cancel_events.get(job_id)
        if cancel_event is not None:
            cancel_event.set()

        if job.status == "pending":
            job.status = "cancelled"
            job.completed_at = datetime.now().isoformat()
            job.summary = _build_job_summary(job)
            _update_job_progress(
                job,
                {
                    "query": job.queries[0] if job.queries else None,
                    "phase": "cancelled",
                    "message": "Job cancelled before it started.",
                    "end_reason": "cancel_requested",
                },
            )
        else:
            _update_job_progress(
                job,
                {
                    "query": job.progress.query if job.progress else (job.queries[0] if job.queries else None),
                    "phase": "cancel_requested",
                    "message": "Cancellation requested. Stopping job...",
                    "end_reason": "cancel_requested",
                },
            )
        return _save_job_locked(job)


def _launch_agent_run(run_id: str, req: AgentRunRequest) -> None:
    Thread(target=_run_agent_workflow, args=(run_id, req), daemon=True).start()


def _run_agent_workflow(run_id: str, req: AgentRunRequest) -> None:
    try:
        runner = AgentWorkflowRunner(
            run_id=run_id,
            update_run=lambda **updates: _update_agent_run(run_id, **updates),
            is_cancel_requested=lambda: _is_agent_cancel_requested(run_id),
            create_scrape_job=lambda payload: _create_scrape_job(ScrapeRequest.model_validate(payload)),
            get_scrape_job=lambda job_id: (
                snapshot.model_dump() if (snapshot := _get_job_snapshot(job_id)) is not None else None
            ),
            cancel_scrape_job=lambda job_id: _request_job_cancel(job_id),
        )
        asyncio.run(runner.run(req))
    except AgentRunCancelled as exc:
        _update_agent_run(
            run_id,
            status="cancelled",
            completed_at=datetime.now().isoformat(),
            progress=AgentProgress(
                phase="cancelled",
                message=str(exc),
                updated_at=datetime.now().isoformat(),
            ),
            recent_event=str(exc),
        )
    except Exception as exc:
        api_logger.exception("agent_run=%s failed: %s", run_id, exc)
        _update_agent_run(
            run_id,
            status="failed",
            completed_at=datetime.now().isoformat(),
            error=str(exc),
            progress=AgentProgress(
                phase="failed",
                message=f"Agent run failed unexpectedly: {exc}",
                updated_at=datetime.now().isoformat(),
            ),
            recent_event=f"Agent run failed unexpectedly: {exc}",
        )
    finally:
        with _agent_runs_lock:
            _agent_cancel_events.pop(run_id, None)


def _run_job(job_id: str, req: ScrapeRequest) -> None:
    try:
        with _jobs_lock:
            job = _jobs[job_id]
            if _is_cancel_requested(job_id):
                job.status = "cancelled"
                job.completed_at = datetime.now().isoformat()
                _update_job_progress(
                    job,
                    {
                        "query": job.queries[0] if job.queries else None,
                        "phase": "cancelled",
                        "message": "Job cancelled before it started.",
                        "end_reason": "cancel_requested",
                    },
                )
                _save_job_locked(job)
                return
            job.status = "running"
            _save_job_locked(job)
        api_logger.info(
            "job=%s started queries=%s max_results=%s max_scrolls=%s max_runtime_seconds=%s headless=%s enrich_websites=%s resume=%s",
            job_id,
            req.queries,
            req.max_results_per_query,
            req.max_scrolls_per_query,
            req.max_runtime_seconds,
            req.headless,
            req.enrich_websites,
            req.resume,
        )

        cfg = _load_runtime_config()
        cfg.queries = req.queries
        cfg.max_results_per_query = req.max_results_per_query
        cfg.max_scrolls_per_query = req.max_scrolls_per_query
        cfg.max_runtime_seconds = req.max_runtime_seconds
        cfg.headless = req.headless
        cfg.enrich_websites = req.enrich_websites
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger = setup_logger(Path(cfg.logs_dir), run_id)
        output_dir = Path(cfg.output_dir)
        checkpoints_dir = Path(cfg.checkpoint_dir)
        _cleanup_runtime_files(cfg)

        def update_progress(update: dict[str, object]) -> None:
            with _jobs_lock:
                job = _jobs.get(job_id)
                if job is None:
                    return
                _update_job_progress(job, update)
                _save_job_locked(job)

        for query in cfg.queries:
            if _is_cancel_requested(job_id):
                update_progress(
                    {
                        "query": query,
                        "phase": "cancel_requested",
                        "message": "Cancellation requested. Stopping job...",
                        "end_reason": "cancel_requested",
                    }
                )
                break
            try:
                api_logger.info("job=%s query=%r started", job_id, query)
                leads, elapsed, csv_path = run_query(
                    query=query,
                    cfg=cfg,
                    output_dir=output_dir,
                    checkpoints_dir=checkpoints_dir,
                    logger=logger,
                    resume=req.resume,
                    progress_callback=update_progress,
                    should_cancel=lambda: _is_cancel_requested(job_id),
                )
                with _jobs_lock:
                    job = _jobs[job_id]
                    job.leads.extend([_lead_to_out(l) for l in leads])
                    job.results.append(
                        QueryResult(
                            query=query,
                            status="cancelled" if _is_cancel_requested(job_id) else "completed",
                            leads_count=len(leads),
                            elapsed_seconds=round(elapsed, 1),
                            csv_path=str(csv_path),
                            export_expires_at=(
                                path_expiration(Path(csv_path), cfg.export_retention_minutes).isoformat()
                                if cfg.export_retention_minutes > 0
                                else None
                            ),
                        )
                    )
                    _save_job_locked(job)
                api_logger.info(
                    "job=%s query=%r completed status=%s leads=%s elapsed_seconds=%.1f csv_path=%s",
                    job_id,
                    query,
                    "cancelled" if _is_cancel_requested(job_id) else "completed",
                    len(leads),
                    elapsed,
                    csv_path,
                )
                if not leads:
                    latest_progress = job.progress
                    api_logger.warning(
                        "job=%s query=%r produced_zero_leads phase=%s end_reason=%s recent_events=%s",
                        job_id,
                        query,
                        latest_progress.phase if latest_progress else None,
                        latest_progress.end_reason if latest_progress else None,
                        job.recent_events[-3:],
                    )
            except Exception as exc:
                api_logger.exception("job=%s query=%r failed: %s", job_id, query, exc)
                with _jobs_lock:
                    job = _jobs[job_id]
                    job.results.append(
                        QueryResult(
                            query=query,
                            status="cancelled" if _is_cancel_requested(job_id) else "failed",
                            leads_count=0,
                            elapsed_seconds=0,
                            csv_path="",
                            error=str(exc),
                        )
                    )
                    _save_job_locked(job)
                update_progress(
                    {
                        "query": query,
                        "phase": "query_failed",
                        "message": f"Query failed: {exc}",
                        "end_reason": None,
                    }
                )
            with _jobs_lock:
                job = _jobs.get(job_id)
                if job is not None:
                    job.queries_done += 1
                    _save_job_locked(job)
            if _is_cancel_requested(job_id):
                break

        with _jobs_lock:
            job = _jobs[job_id]
            job.summary = _build_job_summary(job)
            job.completed_at = datetime.now().isoformat()
            if _is_cancel_requested(job_id):
                job.status = "cancelled"
                final_message = f"Job cancelled with {job.summary['total_leads']} total leads"
                end_reason = "cancel_requested"
            else:
                job.status = "failed" if job.results and all(r.error for r in job.results) else "completed"
                final_message = f"Job {job.status} with {job.summary['total_leads']} total leads"
                end_reason = None
            _write_combined_job_csv(job, output_dir, cfg.export_retention_minutes)
            _save_job_locked(job)
        api_logger.info(
            "job=%s finished status=%s total_leads=%s queries_done=%s/%s summary=%s",
            job_id,
            job.status,
            job.summary["total_leads"],
            job.queries_done,
            job.queries_total,
            job.summary,
        )
        update_progress(
            {
                "phase": job.status,
                "message": final_message,
                "end_reason": end_reason,
            }
        )
    except Exception as exc:
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job.summary = _build_job_summary(job)
                job.completed_at = datetime.now().isoformat()
                job.status = "cancelled" if _is_cancel_requested(job_id) else "failed"
                _update_job_progress(
                    job,
                    {
                        "query": job.progress.query if job.progress else (job.queries[0] if job.queries else None),
                        "phase": job.status,
                        "message": (
                            "Job cancelled."
                            if job.status == "cancelled"
                            else f"Job failed unexpectedly: {exc}"
                        ),
                        "end_reason": "cancel_requested" if job.status == "cancelled" else "unexpected_error",
                    },
                )
                _write_combined_job_csv(job, Path(_load_runtime_config().output_dir), job.export_retention_minutes)
                _save_job_locked(job)
        api_logger.exception("job=%s failed unexpectedly: %s", job_id, exc)
    finally:
        with _jobs_lock:
            _job_cancel_events.pop(job_id, None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthOut, tags=["System"])
def health_check():
    """Server health check with uptime."""
    return HealthOut(
        status="ok",
        version="1.0.0",
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@app.get("/dedupe/status", response_model=DedupeStatusOut, tags=["System"])
def get_dedupe_status():
    """Return the current size of the persistent dedupe store."""
    cfg = _load_runtime_config()
    db_path = Path(cfg.dedupe_db_path)
    try:
        alias_count = count_seen_aliases(db_path)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Dedupe store unavailable: {exc}") from exc
    return DedupeStatusOut(alias_count=alias_count)


@app.get("/config", response_model=ConfigOut, tags=["Configuration"])
def get_config():
    """Return the current default configuration from scraper_config.json."""
    cfg = _load_runtime_config()
    return ConfigOut(
        queries=cfg.queries,
        max_results_per_query=cfg.max_results_per_query,
        max_scrolls_per_query=cfg.max_scrolls_per_query,
        max_runtime_seconds=cfg.max_runtime_seconds,
        output_dir=cfg.output_dir,
        logs_dir=cfg.logs_dir,
        checkpoint_dir=cfg.checkpoint_dir,
        export_retention_minutes=cfg.export_retention_minutes,
        headless=cfg.headless,
        enrich_websites=cfg.enrich_websites,
        enable_master_csv=cfg.enable_master_csv,
    )


@app.post("/scrape", response_model=JobStatus, status_code=202, tags=["Scraping"])
def start_scrape(req: ScrapeRequest):
    """
    Submit a new scraping job.

    The job runs in the background. Use the returned `job_id` to poll
    progress via `GET /scrape/{job_id}`.
    """
    return _create_scrape_job(req)


@app.get("/scrape/{job_id}", response_model=JobStatus, tags=["Scraping"])
def get_job(job_id: str):
    """
    Poll the status and results of a scraping job.

    Returns current progress, per-query results, and all scraped leads
    once the job completes.
    """
    job = _get_job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@app.delete("/scrape/{job_id}", response_model=JobStatus, status_code=202, tags=["Scraping"])
def cancel_job(job_id: str):
    """Request cancellation for a pending or running scraping job."""
    try:
        return _request_job_cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.") from exc


@app.get("/scrape", response_model=list[JobStatus], tags=["Scraping"])
def list_jobs(
    status: str | None = Query(None, description="Filter by status: pending, running, completed, failed, cancelled"),
    limit: int = Query(20, ge=1, le=100, description="Max jobs to return"),
):
    """List all scraping jobs, optionally filtered by status."""
    jobs = _list_jobs(limit)
    if status:
        jobs = [j for j in jobs if j.status == status]
    return jobs[:limit]


@app.post("/agent/runs", response_model=AgentRunStatus, status_code=202, tags=["Agents"])
def start_agent_run(req: AgentRunRequest):
    """Submit a lightweight LangGraph-supervised run that plans, executes, and analyzes a scrape."""
    run = AgentRunStatus(
        run_id=uuid.uuid4().hex[:12],
        status="pending",
        created_at=datetime.now().isoformat(),
        goal=req.goal,
        progress=AgentProgress(
            phase="queued",
            message="Agent run created and waiting for the supervisor to start.",
            updated_at=datetime.now().isoformat(),
        ),
    )
    with _agent_runs_lock:
        _agent_runs[run.run_id] = run
        _agent_cancel_events[run.run_id] = Event()
    _agent_store().save(run)
    api_logger.info("agent_run=%s submitted goal=%r", run.run_id, req.goal)
    _launch_agent_run(run.run_id, req)
    return run.model_copy(deep=True)


@app.get("/agent/runs", response_model=list[AgentRunStatus], tags=["Agents"])
def list_agent_runs(
    limit: int = Query(20, ge=1, le=100, description="Max agent runs to return"),
):
    """List recent agent-supervised runs."""
    return _list_agent_runs(limit)


@app.get("/agent/runs/{run_id}", response_model=AgentRunStatus, tags=["Agents"])
def get_agent_run(run_id: str):
    """Fetch an agent run by id, including the planner output and analysis."""
    run = _get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")
    return run


@app.delete("/agent/runs/{run_id}", response_model=AgentRunStatus, status_code=202, tags=["Agents"])
def cancel_agent_run(run_id: str):
    """Request cancellation for an agent run and any linked scrape job."""
    run = _get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")
    if run.status in {"completed", "failed", "cancelled"}:
        return run

    with _agent_runs_lock:
        cancel_event = _agent_cancel_events.get(run_id)
        if cancel_event is not None:
            cancel_event.set()

    if run.scrape_job_id:
        try:
            _request_job_cancel(run.scrape_job_id)
        except KeyError:
            api_logger.warning("agent_run=%s linked_scrape_job_missing job=%s", run_id, run.scrape_job_id)

    return _update_agent_run(
        run_id,
        status="cancel_requested",
        progress=AgentProgress(
            phase="cancel_requested",
            message="Cancellation requested. Waiting for the workflow to stop cleanly.",
            updated_at=datetime.now().isoformat(),
        ),
        recent_event="User requested cancellation for the agent run.",
    )


@app.get("/exports", response_model=list[ExportFile], tags=["Exports"])
def list_exports(
    limit: int = Query(20, ge=1, le=100, description="Max files to return"),
):
    """List recent CSV export files."""
    cfg = _load_runtime_config()
    _cleanup_runtime_files(cfg, include_all=False)
    export_dir = Path(cfg.output_dir)
    if not export_dir.exists():
        return []
    files = sorted(export_dir.glob("leads_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        ExportFile(
            filename=f.name,
            size_bytes=f.stat().st_size,
            modified_at=datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            expires_at=(
                path_expiration(f, cfg.export_retention_minutes).isoformat()
                if cfg.export_retention_minutes > 0
                else None
            ),
        )
        for f in files[:limit]
    ]


@app.get("/exports/{filename}", tags=["Exports"])
def download_export(filename: str):
    """Download a specific export file by name."""
    cfg = _load_runtime_config()
    _cleanup_runtime_files(cfg, include_all=False)
    filepath = _resolve_export_filepath(filename, must_exist=True)
    if filepath is None:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")
    return _csv_stream_response(filepath, filename)


@app.get("/scrape/{job_id}/csv", tags=["Scraping"])
def download_job_csv(job_id: str):
    """
    Download all leads from a completed job as a single combined CSV.
    """
    job = _get_job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job.status not in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail="Job has not finished yet.")
    if not job.leads:
        raise HTTPException(status_code=404, detail="No leads in this job.")
    job = _ensure_job_export(job)
    if not job.combined_csv_filename:
        raise HTTPException(status_code=404, detail="No durable CSV export is available for this job.")
    filepath = _resolve_export_filepath(job.combined_csv_filename, must_exist=True)
    if filepath is None:
        raise HTTPException(status_code=404, detail=f"File '{job.combined_csv_filename}' not found.")
    return _csv_stream_response(filepath, job.combined_csv_filename)


@app.get("/agent/runs/{run_id}/csv", tags=["Agents"])
def download_agent_run_csv(run_id: str):
    """Download the best available CSV for an agent run, even after a restart."""
    run = _get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")

    if run.scrape_job_id:
        job = _get_job_snapshot(run.scrape_job_id)
        if job is not None:
            try:
                return download_job_csv(job.job_id)
            except HTTPException as exc:
                if exc.status_code not in {404, 409} or not run.linked_export_filename:
                    raise

    if not run.linked_export_filename:
        raise HTTPException(status_code=404, detail="No durable CSV export is available for this agent run.")
    filepath = _resolve_export_filepath(run.linked_export_filename, must_exist=True)
    if filepath is None:
        raise HTTPException(status_code=404, detail=f"File '{run.linked_export_filename}' not found.")
    return _csv_stream_response(filepath, run.linked_export_filename)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
