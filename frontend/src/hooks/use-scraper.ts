"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  useStartScrapeMutation,
  useGetJobQuery,
  useListJobsQuery,
} from "@/lib/scraper-api";
import type { ScrapeRequest, JobStatus } from "@/types";

const DEFAULT_FORM: ScrapeRequest = {
  queries: [""],
  max_results_per_query: 30,
  max_scrolls_per_query: 15,
  max_runtime_seconds: 0,
  headless: true,
  enrich_websites: true,
  resume: false,
};

function getJobElapsed(job: JobStatus): number {
  const startedAt = Date.parse(job.created_at);
  if (Number.isNaN(startedAt)) {
    return 0;
  }
  const endedAt = job.completed_at ? Date.parse(job.completed_at) : Date.now();
  if (Number.isNaN(endedAt)) {
    return 0;
  }
  return Math.max(0, Math.floor((endedAt - startedAt) / 1000));
}

export function useScraper() {
  const [form, setForm] = useState<ScrapeRequest>(DEFAULT_FORM);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [startScrape, { isLoading: isSubmitting }] = useStartScrapeMutation();

  const {
    data: activeJob,
    refetch: refetchJob,
  } = useGetJobQuery(activeJobId!, { skip: !activeJobId });

  const { data: jobs = [], refetch: refetchJobs } = useListJobsQuery({
    limit: 50,
  });

  const isRunning =
    !!activeJob && (activeJob.status === "pending" || activeJob.status === "running");

  // Poll active job while running
  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => {
      refetchJob();
    }, 3000);
    return () => clearInterval(interval);
  }, [isRunning, refetchJob]);

  // Elapsed timer
  useEffect(() => {
    if (isRunning) {
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning]);

  // Refresh job list when active job completes
  useEffect(() => {
    if (activeJob && !isRunning) {
      refetchJobs();
    }
  }, [activeJob, isRunning, refetchJobs]);

  const updateForm = useCallback(
    <K extends keyof ScrapeRequest>(field: K, value: ScrapeRequest[K]) => {
      setForm((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const setQueries = useCallback((raw: string) => {
    setForm((prev) => ({
      ...prev,
      queries: raw.split("\n").filter((q) => q.trim()),
    }));
  }, []);

  const queriesText = form.queries.join("\n");

  const submit = useCallback(async () => {
    const cleaned = form.queries.map((q) => q.trim()).filter(Boolean);
    if (cleaned.length === 0) return;
    try {
      setElapsed(0);
      const job = await startScrape({ ...form, queries: cleaned }).unwrap();
      setActiveJobId(job.job_id);
    } catch {
      // error is available via RTK Query hook state
    }
  }, [form, startScrape]);

  const viewJob = useCallback((job: JobStatus) => {
    setElapsed(getJobElapsed(job));
    setActiveJobId(job.job_id);
  }, []);

  const formatElapsed = useCallback((s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  }, []);

  return {
    form,
    queriesText,
    updateForm,
    setQueries,
    submit,
    isSubmitting,
    activeJob,
    activeJobId,
    isRunning,
    elapsed,
    formatElapsed,
    jobs,
    viewJob,
  };
}
