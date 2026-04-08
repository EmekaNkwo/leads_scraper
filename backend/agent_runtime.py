from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from pydantic import BaseModel, Field

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - exercised only when langgraph is unavailable.
    END = "__end__"

    class _FallbackCompiledGraph:
        def __init__(self, nodes: dict[str, Callable[[dict[str, Any]], Any]], edges: dict[str, str], entry: str):
            self._nodes = nodes
            self._edges = edges
            self._entry = entry

        async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
            current = self._entry
            result = dict(state)
            while current != END:
                step = self._nodes[current]
                update = await step(result)
                if update:
                    result.update(update)
                current = self._edges[current]
            return result

    class StateGraph:
        def __init__(self, _state_type: type[Any]):
            self._nodes: dict[str, Callable[[dict[str, Any]], Any]] = {}
            self._edges: dict[str, str] = {}
            self._entry: str | None = None

        def add_node(self, name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
            self._nodes[name] = handler

        def add_edge(self, source: str, destination: str) -> None:
            self._edges[source] = destination

        def set_entry_point(self, name: str) -> None:
            self._entry = name

        def compile(self) -> _FallbackCompiledGraph:
            if self._entry is None:
                raise RuntimeError("Graph entry point was not configured.")
            return _FallbackCompiledGraph(self._nodes, self._edges, self._entry)


TERMINAL_SCRAPE_STATUSES = {"completed", "failed", "cancelled"}


class AgentRunRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=500, description="Natural-language lead sourcing goal.")
    max_queries: int = Field(5, ge=1, le=10, description="Maximum query variants the planner may produce.")
    max_results_per_query: int = Field(30, ge=1, le=500)
    max_scrolls_per_query: int = Field(15, ge=1, le=100)
    max_runtime_seconds: int = Field(0, ge=0, le=3600)
    headless: bool = True
    enrich_websites: bool = True
    resume: bool = False


class AgentProgress(BaseModel):
    phase: str = "queued"
    message: str | None = None
    updated_at: str | None = None


class AgentLeadInsight(BaseModel):
    name: str
    query: str
    score: float
    email: str = "N/A"
    website: str = "N/A"
    reasons: list[str] = Field(default_factory=list)


class AgentAnalysis(BaseModel):
    total_leads: int = 0
    emails_found: int = 0
    websites_found: int = 0
    top_leads: list[AgentLeadInsight] = Field(default_factory=list)
    summary: str = ""


class AgentRunStatus(BaseModel):
    run_id: str
    status: str = Field(description="pending | running | cancel_requested | completed | failed | cancelled")
    created_at: str
    completed_at: str | None = None
    goal: str
    proposed_queries: list[str] = Field(default_factory=list)
    scrape_request: dict[str, Any] | None = None
    scrape_job_id: str | None = None
    scrape_job_status: str | None = None
    linked_export_filename: str | None = None
    linked_export_expires_at: str | None = None
    progress: AgentProgress | None = None
    analysis: AgentAnalysis | None = None
    recent_events: list[str] = Field(default_factory=list)
    error: str | None = None


class AgentRunStore:
    _replace_retries = 5
    _replace_retry_delay_seconds = 0.05
    _retryable_winerrors = {5, 32}
    _retryable_errnos = {13}

    def __init__(self, directory: Path):
        self.directory = directory

    def _is_valid_run_id(self, run_id: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_-]+", run_id))

    def _path_for(self, run_id: str) -> Path:
        if not self._is_valid_run_id(run_id):
            raise ValueError(f"Invalid run id: {run_id}")
        return self.directory / f"{run_id}.json"

    def _temp_path_for(self, run_id: str) -> Path:
        if not self._is_valid_run_id(run_id):
            raise ValueError(f"Invalid run id: {run_id}")
        return self.directory / f"{run_id}.{uuid.uuid4().hex}.tmp"

    def _is_retryable_replace_error(self, exc: OSError) -> bool:
        if isinstance(exc, PermissionError):
            return True
        winerror = getattr(exc, "winerror", None)
        errno = getattr(exc, "errno", None)
        return winerror in self._retryable_winerrors or errno in self._retryable_errnos

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

    def save(self, run: AgentRunStatus) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for(run.run_id)
        temp_path = self._temp_path_for(run.run_id)
        try:
            temp_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
            self._replace_with_retry(temp_path, path)
        finally:
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)

    def load(self, run_id: str) -> AgentRunStatus | None:
        if not self._is_valid_run_id(run_id):
            return None
        path = self._path_for(run_id)
        if not path.exists():
            return None
        return AgentRunStatus.model_validate_json(path.read_text(encoding="utf-8"))

    def list_runs(self, limit: int = 20) -> list[AgentRunStatus]:
        if not self.directory.exists():
            return []
        runs: list[AgentRunStatus] = []
        for path in self.directory.glob("*.json"):
            try:
                runs.append(AgentRunStatus.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        runs.sort(key=lambda run: run.created_at, reverse=True)
        return runs[:limit]


def build_agent_queries(goal: str, max_queries: int) -> list[str]:
    cleaned = " ".join(goal.strip().split())
    normalized = re.sub(r"^(find|search for|get me|look for)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    base = normalized or cleaned
    primary = re.split(r"\s+with\s+", base, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    seed_queries = [
        base,
        primary,
        f"{primary} contacts",
        f"{primary} website",
        f"{primary} owner",
        f"{primary} suppliers",
        f"{primary} wholesalers",
    ]
    queries: list[str] = []
    seen: set[str] = set()
    for candidate in seed_queries:
        compact = " ".join(candidate.split()).strip(" ,.-")
        key = compact.casefold()
        if not compact or key in seen:
            continue
        seen.add(key)
        queries.append(compact)
        if len(queries) >= max_queries:
            break
    return queries


def analyze_scrape_payload(scrape_job: dict[str, Any] | None) -> AgentAnalysis:
    if not scrape_job:
        return AgentAnalysis(summary="No scrape job data was available for analysis.")
    leads = list(scrape_job.get("leads") or [])
    if not leads:
        return AgentAnalysis(
            total_leads=0,
            emails_found=0,
            websites_found=0,
            summary="The scrape finished without any leads to rank.",
        )

    scored: list[tuple[float, AgentLeadInsight]] = []
    emails_found = 0
    websites_found = 0
    for lead in leads:
        email = str(lead.get("email", "N/A"))
        website = str(lead.get("website", "N/A"))
        owner_name = str(lead.get("owner_name", "N/A"))
        try:
            confidence = float(lead.get("confidence_score") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        weighted = confidence
        reasons: list[str] = []
        if email != "N/A":
            emails_found += 1
            weighted += 0.35
            reasons.append("has direct email")
        if website != "N/A":
            websites_found += 1
            weighted += 0.2
            reasons.append("has website")
        if owner_name != "N/A":
            weighted += 0.15
            reasons.append("owner hint found")
        if confidence >= 0.7:
            reasons.append("high confidence match")
        scored.append(
            (
                weighted,
                AgentLeadInsight(
                    name=str(lead.get("name", "N/A")),
                    query=str(lead.get("query", "N/A")),
                    score=round(weighted, 2),
                    email=email,
                    website=website,
                    reasons=reasons or ["basic location-only match"],
                ),
            )
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    ranked_leads = [item[1] for item in scored]
    job_status = scrape_job.get("status", "completed")
    summary = (
        f"Scrape job {job_status} with {len(leads)} leads. "
        f"{emails_found} leads include email addresses and {websites_found} include websites."
    )
    return AgentAnalysis(
        total_leads=len(leads),
        emails_found=emails_found,
        websites_found=websites_found,
        top_leads=ranked_leads,
        summary=summary,
    )


class AgentWorkflowState(TypedDict, total=False):
    request: dict[str, Any]
    proposed_queries: list[str]
    scrape_request: dict[str, Any]
    scrape_job_id: str
    scrape_job_status: str
    scrape_job: dict[str, Any]
    analysis: dict[str, Any]


class AgentWorkflowRunner:
    def __init__(
        self,
        run_id: str,
        update_run: Callable[..., AgentRunStatus],
        is_cancel_requested: Callable[[], bool],
        create_scrape_job: Callable[[dict[str, Any]], Any],
        get_scrape_job: Callable[[str], dict[str, Any] | None],
        cancel_scrape_job: Callable[[str], Any],
        poll_interval_seconds: float = 1.0,
    ):
        self.run_id = run_id
        self._update_run = update_run
        self._is_cancel_requested = is_cancel_requested
        self._create_scrape_job = create_scrape_job
        self._get_scrape_job = get_scrape_job
        self._cancel_scrape_job = cancel_scrape_job
        self._poll_interval_seconds = poll_interval_seconds

    def _timestamp(self) -> str:
        return datetime.now().isoformat()

    def _event(self, message: str) -> AgentRunStatus:
        return self._update_run(recent_event=message)

    def _ensure_not_cancelled(self, phase: str) -> None:
        if self._is_cancel_requested():
            raise AgentRunCancelled(f"Agent run cancelled during {phase}.")

    def _linked_export_updates(self, scrape_job: dict[str, Any] | None) -> dict[str, Any]:
        if not scrape_job:
            return {}
        return {
            "linked_export_filename": scrape_job.get("combined_csv_filename"),
            "linked_export_expires_at": scrape_job.get("combined_csv_expires_at"),
        }

    async def _plan_queries(self, state: AgentWorkflowState) -> AgentWorkflowState:
        self._ensure_not_cancelled("planning")
        request = AgentRunRequest.model_validate(state["request"])
        proposed_queries = build_agent_queries(request.goal, request.max_queries)
        scrape_request = {
            "queries": proposed_queries,
            "max_results_per_query": request.max_results_per_query,
            "max_scrolls_per_query": request.max_scrolls_per_query,
            "max_runtime_seconds": request.max_runtime_seconds,
            "headless": request.headless,
            "enrich_websites": request.enrich_websites,
            "resume": request.resume,
        }
        self._update_run(
            status="running",
            proposed_queries=proposed_queries,
            scrape_request=scrape_request,
            progress=AgentProgress(
                phase="planning",
                message=f"Planner produced {len(proposed_queries)} Google Maps queries.",
                updated_at=self._timestamp(),
            ),
            recent_event=f"Planner produced {len(proposed_queries)} query variants.",
        )
        return {"proposed_queries": proposed_queries, "scrape_request": scrape_request}

    async def _submit_scrape(self, state: AgentWorkflowState) -> AgentWorkflowState:
        self._ensure_not_cancelled("scrape submission")
        scrape_job = await asyncio.to_thread(self._create_scrape_job, state["scrape_request"])
        self._update_run(
            scrape_job_id=scrape_job.job_id,
            scrape_job_status=scrape_job.status,
            **self._linked_export_updates(getattr(scrape_job, "model_dump", lambda: {})()),
            progress=AgentProgress(
                phase="scrape_submitted",
                message=f"Submitted scrape job {scrape_job.job_id}.",
                updated_at=self._timestamp(),
            ),
            recent_event=f"Submitted scrape job {scrape_job.job_id}.",
        )
        return {"scrape_job_id": scrape_job.job_id, "scrape_job_status": scrape_job.status}

    async def _monitor_scrape(self, state: AgentWorkflowState) -> AgentWorkflowState:
        scrape_job_id = state["scrape_job_id"]
        cancel_requested = False
        while True:
            if self._is_cancel_requested() and not cancel_requested:
                cancel_requested = True
                await asyncio.to_thread(self._cancel_scrape_job, scrape_job_id)
                self._update_run(
                    status="cancel_requested",
                    progress=AgentProgress(
                        phase="cancel_requested",
                        message="Cancellation requested. Waiting for scrape job to stop.",
                        updated_at=self._timestamp(),
                    ),
                    recent_event=f"Cancellation requested for scrape job {scrape_job_id}.",
                )

            scrape_job = await asyncio.to_thread(self._get_scrape_job, scrape_job_id)
            if scrape_job is None:
                raise RuntimeError(f"Scrape job '{scrape_job_id}' disappeared before the agent could finish monitoring it.")

            scrape_status = str(scrape_job.get("status", "pending"))
            progress = scrape_job.get("progress") or {}
            message = progress.get("message") or f"Scrape job {scrape_status}."
            run_status = "running"
            if scrape_status == "failed":
                run_status = "failed"
            elif scrape_status == "cancelled":
                run_status = "cancelled"
            elif cancel_requested:
                run_status = "cancel_requested"
            self._update_run(
                status=run_status,
                scrape_job_status=scrape_status,
                **self._linked_export_updates(scrape_job),
                progress=AgentProgress(
                    phase="monitoring",
                    message=str(message),
                    updated_at=self._timestamp(),
                ),
            )
            if scrape_status in TERMINAL_SCRAPE_STATUSES:
                return {"scrape_job_status": scrape_status, "scrape_job": scrape_job}
            await asyncio.sleep(self._poll_interval_seconds)

    async def _analyze_results(self, state: AgentWorkflowState) -> AgentWorkflowState:
        scrape_job = state.get("scrape_job")
        analysis = analyze_scrape_payload(scrape_job)
        scrape_status = state.get("scrape_job_status", "completed")
        final_status = "completed"
        if scrape_status == "failed":
            final_status = "failed"
        elif scrape_status == "cancelled":
            final_status = "cancelled"
        self._update_run(
            status=final_status,
            completed_at=self._timestamp(),
            analysis=analysis,
            **self._linked_export_updates(scrape_job),
            progress=AgentProgress(
                phase="completed" if final_status == "completed" else final_status,
                message=analysis.summary,
                updated_at=self._timestamp(),
            ),
            recent_event="Lead analyst finished ranking the scrape results.",
        )
        return {"analysis": analysis.model_dump()}

    def _build_graph(self):
        graph = StateGraph(AgentWorkflowState)
        graph.add_node("planner", self._plan_queries)
        graph.add_node("executor", self._submit_scrape)
        graph.add_node("monitor", self._monitor_scrape)
        graph.add_node("analyzer", self._analyze_results)
        graph.set_entry_point("planner")
        graph.add_edge("planner", "executor")
        graph.add_edge("executor", "monitor")
        graph.add_edge("monitor", "analyzer")
        graph.add_edge("analyzer", END)
        return graph.compile()

    async def run(self, request: AgentRunRequest) -> AgentWorkflowState:
        self._update_run(
            status="running",
            progress=AgentProgress(
                phase="queued",
                message="Agent supervisor queued the workflow.",
                updated_at=self._timestamp(),
            ),
        )
        graph = self._build_graph()
        return await graph.ainvoke({"request": request.model_dump()})


class AgentRunCancelled(Exception):
    """Raised when a user cancels an in-flight agent workflow."""

