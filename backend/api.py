from __future__ import annotations

import csv
import io
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from scraper import run_query
from scraper_config import AppConfig
from scraper_models import LeadRecord
from scraper_utils import setup_logger

app = FastAPI(
    title="Leads Scraper API",
    description=(
        "Google Maps leads scraper with enrichment and export pipeline. "
        "Submit scraping jobs, poll for results, and download CSV/JSON exports."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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
    export_json: bool = Field(True, description="Also export a JSON file alongside CSV.")
    resume: bool = Field(False, description="Resume from checkpoint if available for a query.")


class LeadOut(BaseModel):
    query: str
    name: str
    phone: str
    address: str
    email: str
    owner_name: str
    website: str
    category: str
    social_links: list[str]
    scraped_at: str
    confidence_score: float


class QueryResult(BaseModel):
    query: str
    leads_count: int
    elapsed_seconds: float
    csv_path: str
    error: str | None = None


class JobStatus(BaseModel):
    job_id: str
    status: str = Field(description="pending | running | completed | failed")
    created_at: str
    completed_at: str | None = None
    queries_total: int
    queries_done: int = 0
    results: list[QueryResult] = []
    leads: list[LeadOut] = []
    summary: dict[str, int] = {}


class ExportFile(BaseModel):
    filename: str
    size_bytes: int
    modified_at: str


class ConfigOut(BaseModel):
    queries: list[str]
    max_results_per_query: int
    max_scrolls_per_query: int
    max_runtime_seconds: int
    output_dir: str
    logs_dir: str
    checkpoint_dir: str
    archive_after_days: int
    headless: bool
    enrich_websites: bool
    export_json: bool


class HealthOut(BaseModel):
    status: str
    version: str
    uptime_seconds: float


# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

_jobs: dict[str, JobStatus] = {}
_start_time = time.time()


def _lead_to_out(lead: LeadRecord) -> LeadOut:
    return LeadOut(
        query=lead.query,
        name=lead.name,
        phone=lead.phone,
        address=lead.address,
        email=lead.email,
        owner_name=lead.owner_name,
        website=lead.website,
        category=lead.category,
        social_links=lead.social_links,
        scraped_at=lead.scraped_at,
        confidence_score=lead.confidence_score,
    )


def _run_job(job_id: str, req: ScrapeRequest) -> None:
    job = _jobs[job_id]
    job.status = "running"

    cfg = AppConfig(
        queries=req.queries,
        max_results_per_query=req.max_results_per_query,
        max_scrolls_per_query=req.max_scrolls_per_query,
        max_runtime_seconds=req.max_runtime_seconds,
        headless=req.headless,
        enrich_websites=req.enrich_websites,
        export_json=req.export_json,
    )
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logger(Path(cfg.logs_dir), run_id)
    output_dir = Path(cfg.output_dir)
    checkpoints_dir = Path(cfg.checkpoint_dir)

    total_leads = 0
    total_emails = 0
    total_websites = 0

    for query in cfg.queries:
        try:
            leads, elapsed, csv_path = run_query(
                query=query,
                cfg=cfg,
                output_dir=output_dir,
                checkpoints_dir=checkpoints_dir,
                logger=logger,
                resume=req.resume,
            )
            job.leads.extend([_lead_to_out(l) for l in leads])
            total_leads += len(leads)
            total_emails += sum(1 for l in leads if l.email != "N/A")
            total_websites += sum(1 for l in leads if l.website != "N/A")
            job.results.append(
                QueryResult(
                    query=query,
                    leads_count=len(leads),
                    elapsed_seconds=round(elapsed, 1),
                    csv_path=str(csv_path),
                )
            )
        except Exception as exc:
            job.results.append(
                QueryResult(
                    query=query,
                    leads_count=0,
                    elapsed_seconds=0,
                    csv_path="",
                    error=str(exc),
                )
            )
        job.queries_done += 1

    job.summary = {
        "total_leads": total_leads,
        "emails_found": total_emails,
        "websites_found": total_websites,
        "queries_succeeded": sum(1 for r in job.results if r.error is None),
        "queries_failed": sum(1 for r in job.results if r.error is not None),
    }
    job.completed_at = datetime.now().isoformat()
    job.status = "failed" if all(r.error for r in job.results) else "completed"


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


@app.get("/config", response_model=ConfigOut, tags=["Configuration"])
def get_config():
    """Return the current default configuration from scraper_config.json."""
    cfg = AppConfig.from_file("scraper_config.json")
    return ConfigOut(
        queries=cfg.queries,
        max_results_per_query=cfg.max_results_per_query,
        max_scrolls_per_query=cfg.max_scrolls_per_query,
        max_runtime_seconds=cfg.max_runtime_seconds,
        output_dir=cfg.output_dir,
        logs_dir=cfg.logs_dir,
        checkpoint_dir=cfg.checkpoint_dir,
        archive_after_days=cfg.archive_after_days,
        headless=cfg.headless,
        enrich_websites=cfg.enrich_websites,
        export_json=cfg.export_json,
    )


@app.post("/scrape", response_model=JobStatus, status_code=202, tags=["Scraping"])
def start_scrape(req: ScrapeRequest):
    """
    Submit a new scraping job.

    The job runs in the background. Use the returned `job_id` to poll
    progress via `GET /scrape/{job_id}`.
    """
    job_id = uuid.uuid4().hex[:12]
    job = JobStatus(
        job_id=job_id,
        status="pending",
        created_at=datetime.now().isoformat(),
        queries_total=len(req.queries),
    )
    _jobs[job_id] = job
    Thread(target=_run_job, args=(job_id, req), daemon=True).start()
    return job


@app.get("/scrape/{job_id}", response_model=JobStatus, tags=["Scraping"])
def get_job(job_id: str):
    """
    Poll the status and results of a scraping job.

    Returns current progress, per-query results, and all scraped leads
    once the job completes.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@app.get("/scrape", response_model=list[JobStatus], tags=["Scraping"])
def list_jobs(
    status: str | None = Query(None, description="Filter by status: pending, running, completed, failed"),
    limit: int = Query(20, ge=1, le=100, description="Max jobs to return"),
):
    """List all scraping jobs, optionally filtered by status."""
    jobs = list(_jobs.values())
    if status:
        jobs = [j for j in jobs if j.status == status]
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs[:limit]


@app.get("/exports", response_model=list[ExportFile], tags=["Exports"])
def list_exports(
    limit: int = Query(20, ge=1, le=100, description="Max files to return"),
):
    """List recent CSV/JSON export files."""
    export_dir = Path("csv_exports")
    if not export_dir.exists():
        return []
    files = sorted(export_dir.glob("leads_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        ExportFile(
            filename=f.name,
            size_bytes=f.stat().st_size,
            modified_at=datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        )
        for f in files[:limit]
    ]


@app.get("/exports/{filename}", tags=["Exports"])
def download_export(filename: str):
    """Download a specific export file by name."""
    filepath = Path("csv_exports") / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")
    if filepath.suffix == ".json":
        media = "application/json"
    else:
        media = "text/csv"
    return StreamingResponse(
        filepath.open("rb"),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/scrape/{job_id}/csv", tags=["Scraping"])
def download_job_csv(job_id: str):
    """
    Download all leads from a completed job as a single combined CSV.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job.status not in ("completed", "failed"):
        raise HTTPException(status_code=409, detail="Job has not finished yet.")
    if not job.leads:
        raise HTTPException(status_code=404, detail="No leads in this job.")

    buf = io.StringIO()
    fields = list(LeadOut.model_fields.keys())
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for lead in job.leads:
        row = lead.model_dump()
        row["social_links"] = ";".join(row["social_links"])
        writer.writerow(row)

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=job_{job_id}.csv"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
