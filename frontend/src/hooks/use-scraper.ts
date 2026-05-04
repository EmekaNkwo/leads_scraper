"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  useCancelScrapeMutation,
  useGetJobQuery,
  useListJobsQuery,
  useStartScrapeMutation,
} from "@/lib/scraper-api";
import type { JobStatus, ScrapeRequest } from "@/types";

const DEFAULT_FORM: ScrapeRequest = {
  queries: [""],
  max_results_per_query: 30,
  max_scrolls_per_query: 15,
  max_runtime_seconds: 0,
  headless: true,
  enrich_websites: true,
  resume: false,
};

const ACTIVE_STATUSES = new Set<JobStatus["status"]>(["pending", "running"]);

function getJobElapsed(job: JobStatus, now: number): number {
  const startedAt = Date.parse(job.created_at);
  if (Number.isNaN(startedAt)) return 0;
  const endedAt = job.completed_at ? Date.parse(job.completed_at) : now;
  if (Number.isNaN(endedAt)) return 0;
  return Math.max(0, Math.floor((endedAt - startedAt) / 1000));
}

function describeError(error: unknown): string {
  if (!error) return "Unknown error.";
  if (typeof error === "string") return error;
  if (typeof error === "object") {
    const maybe = error as {
      data?: { detail?: string };
      message?: string;
      status?: number | string;
    };
    if (maybe.data?.detail) return maybe.data.detail;
    if (maybe.message) return maybe.message;
    if (typeof maybe.status === "number") {
      return `Request failed (${maybe.status}).`;
    }
  }
  return "Request failed. Please try again.";
}

export function useScraper() {
  const [form, setForm] = useState<ScrapeRequest>(DEFAULT_FORM);
  const [viewedJobId, setViewedJobId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [listPollMs, setListPollMs] = useState(0);
  const [jobPollMs, setJobPollMs] = useState(0);

  const [startScrape, { isLoading: isSubmitting }] = useStartScrapeMutation();
  const [cancelScrape] = useCancelScrapeMutation();

  // Jobs list — single policy: poll only while there are active jobs
  const { data: jobs = [] } = useListJobsQuery(
    { limit: 50 },
    { pollingInterval: listPollMs },
  );

  const runningJob = useMemo(
    () => jobs.find((j) => ACTIVE_STATUSES.has(j.status)) ?? null,
    [jobs],
  );
  const isAnyJobRunning = !!runningJob;

  // Active job detail — poll only while the viewed job is running
  const { data: viewedJob } = useGetJobQuery(viewedJobId ?? "", {
    skip: !viewedJobId,
    pollingInterval: jobPollMs,
  });

  const isViewedRunning = !!viewedJob && ACTIVE_STATUSES.has(viewedJob.status);

  useEffect(() => {
    setListPollMs(isAnyJobRunning ? 5000 : 0);
  }, [isAnyJobRunning]);

  useEffect(() => {
    setJobPollMs(isViewedRunning ? 3000 : 0);
  }, [isViewedRunning]);

  // Auto-focus the running job if nothing is selected
  useEffect(() => {
    if (!viewedJobId && runningJob) {
      setViewedJobId(runningJob.job_id);
    }
  }, [runningJob, viewedJobId]);

  // Tick `now` once a second while a viewed job is running so elapsed re-derives
  useEffect(() => {
    if (!isViewedRunning) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isViewedRunning]);

  // When the viewed job finishes, snap `now` to its completed_at so elapsed freezes
  useEffect(() => {
    if (viewedJob?.completed_at) {
      const finishedAt = Date.parse(viewedJob.completed_at);
      if (!Number.isNaN(finishedAt)) setNow(finishedAt);
    }
  }, [viewedJob?.completed_at]);

  const elapsed = useMemo(
    () => (viewedJob ? getJobElapsed(viewedJob, now) : 0),
    [viewedJob, now],
  );

  const updateForm = useCallback(
    <K extends keyof ScrapeRequest>(field: K, value: ScrapeRequest[K]) => {
      setForm((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const setQueries = useCallback((raw: string) => {
    setForm((prev) => ({
      ...prev,
      queries: raw.split("\n"),
    }));
  }, []);

  const queriesText = form.queries.join("\n");

  const submit = useCallback(async () => {
    const cleaned = form.queries.map((q) => q.trim()).filter(Boolean);
    if (cleaned.length === 0) return;
    setSubmitError(null);
    try {
      setNow(Date.now());
      const job = await startScrape({ ...form, queries: cleaned }).unwrap();
      setViewedJobId(job.job_id);
    } catch (err) {
      setSubmitError(describeError(err));
    }
  }, [form, startScrape]);

  const viewJob = useCallback((job: JobStatus) => {
    setViewedJobId(job.job_id);
    setNow(
      job.completed_at
        ? Date.parse(job.completed_at) || Date.now()
        : Date.now(),
    );
  }, []);

  const cancelJob = useCallback(
    async (job: JobStatus) => {
      if (!ACTIVE_STATUSES.has(job.status)) return;
      try {
        setCancellingJobId(job.job_id);
        const updated = await cancelScrape(job.job_id).unwrap();
        setViewedJobId(updated.job_id);
      } finally {
        setCancellingJobId(null);
      }
    },
    [cancelScrape],
  );

  const cancelViewedJob = useCallback(() => {
    if (viewedJob) {
      void cancelJob(viewedJob);
    }
  }, [viewedJob, cancelJob]);

  const formatElapsed = useCallback((s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${String(sec).padStart(2, "0")}s` : `${sec}s`;
  }, []);

  const runStateLabel = useMemo<{
    label: string;
    tone: "idle" | "running" | "done" | "error";
  }>(() => {
    if (runningJob) {
      const total = runningJob.queries_total || 1;
      const done = runningJob.queries_done || 0;
      return {
        label: `Running · ${Math.min(done + 1, total)}/${total}`,
        tone: "running",
      };
    }
    const lastFinished = jobs.find((j) => !ACTIVE_STATUSES.has(j.status));
    if (lastFinished) {
      const tone =
        lastFinished.status === "failed"
          ? "error"
          : lastFinished.status === "cancelled"
            ? "idle"
            : "done";
      const finishedAt = lastFinished.completed_at
        ? new Date(lastFinished.completed_at)
        : null;
      const minsAgo = finishedAt
        ? Math.max(0, Math.round((Date.now() - finishedAt.getTime()) / 60000))
        : null;
      return {
        label:
          minsAgo === null
            ? `Idle · last ${lastFinished.status}`
            : minsAgo === 0
              ? `Idle · just ${lastFinished.status}`
              : `Idle · ${lastFinished.status} ${minsAgo}m ago`,
        tone,
      };
    }
    return { label: "Idle · no runs yet", tone: "idle" };
  }, [runningJob, jobs]);

  return {
    form,
    queriesText,
    updateForm,
    setQueries,
    submit,
    isSubmitting,
    submitError,
    viewedJob,
    viewedJobId,
    isViewedRunning,
    isAnyJobRunning,
    runningJob,
    elapsed,
    formatElapsed,
    jobs,
    viewJob,
    cancelJob,
    cancelViewedJob,
    cancellingJobId,
    runStateLabel,
  };
}
