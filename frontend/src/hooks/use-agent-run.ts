"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { skipToken } from "@reduxjs/toolkit/query";
import {
  useCancelAgentRunMutation,
  useGetAgentRunQuery,
  useListAgentRunsQuery,
  useStartAgentRunMutation,
} from "@/lib/scraper-api";
import type { AgentRunRequest, AgentRunStatus } from "@/types";

const DEFAULT_FORM: AgentRunRequest = {
  goal: "",
  max_queries: 4,
  max_results_per_query: 20,
  max_scrolls_per_query: 15,
  max_runtime_seconds: 0,
  headless: true,
  enrich_websites: true,
  resume: false,
};

function getRunElapsed(run: AgentRunStatus): number {
  const startedAt = Date.parse(run.created_at);
  if (Number.isNaN(startedAt)) {
    return 0;
  }
  const endedAt = run.completed_at ? Date.parse(run.completed_at) : Date.now();
  if (Number.isNaN(endedAt)) {
    return 0;
  }
  return Math.max(0, Math.floor((endedAt - startedAt) / 1000));
}

export function useAgentRun() {
  const [form, setForm] = useState<AgentRunRequest>(DEFAULT_FORM);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [cancellingRunId, setCancellingRunId] = useState<string | null>(null);
  const [runsPollingInterval, setRunsPollingInterval] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isAwaitingActiveRun, setIsAwaitingActiveRun] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [startAgentRun, { isLoading: isSubmitting }] = useStartAgentRunMutation();
  const [cancelAgentRun] = useCancelAgentRunMutation();

  const {
    data: activeRun,
    refetch: refetchRun,
    isError: hasActiveRunError,
  } = useGetAgentRunQuery(activeRunId ?? skipToken);

  const { data: runs = [], refetch: refetchRuns } = useListAgentRunsQuery(
    { limit: 50 },
    { pollingInterval: runsPollingInterval },
  );

  const isRunning = isAwaitingActiveRun ||
    (!!activeRun &&
      (activeRun.status === "pending" ||
        activeRun.status === "running" ||
        activeRun.status === "cancel_requested"));

  const hasActiveRuns = runs.some(
    (run) =>
      run.status === "pending" ||
      run.status === "running" ||
      run.status === "cancel_requested",
  );

  useEffect(() => {
    setRunsPollingInterval(hasActiveRuns ? 5000 : 0);
  }, [hasActiveRuns]);

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => {
      refetchRun();
    }, 3000);
    return () => clearInterval(interval);
  }, [isRunning, refetchRun]);

  useEffect(() => {
    if (isRunning) {
      timerRef.current = setInterval(() => setElapsed((seconds) => seconds + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning]);

  useEffect(() => {
    if (activeRun && !isRunning) {
      refetchRuns();
    }
  }, [activeRun, isRunning, refetchRuns]);

  useEffect(() => {
    if (activeRun) {
      setIsAwaitingActiveRun(false);
    }
  }, [activeRun]);

  useEffect(() => {
    if (isAwaitingActiveRun && hasActiveRunError) {
      setIsAwaitingActiveRun(false);
      setErrorMessage(
        "The agent run started, but its live status could not be loaded. Try selecting it from the run history.",
      );
    }
  }, [hasActiveRunError, isAwaitingActiveRun]);

  const updateForm = useCallback(
    <K extends keyof AgentRunRequest>(field: K, value: AgentRunRequest[K]) => {
      setForm((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const submit = useCallback(async () => {
    const goal = form.goal.trim();
    if (!goal || isAwaitingActiveRun) return;
    try {
      setErrorMessage(null);
      setIsAwaitingActiveRun(true);
      setActiveRunId(null);
      setElapsed(0);
      const run = await startAgentRun({ ...form, goal }).unwrap();
      setActiveRunId(run.run_id);
    } catch {
      setIsAwaitingActiveRun(false);
      setErrorMessage("Could not start the agent run. Please try again.");
    }
  }, [form, isAwaitingActiveRun, startAgentRun]);

  const viewRun = useCallback((run: AgentRunStatus) => {
    setErrorMessage(null);
    setIsAwaitingActiveRun(false);
    setElapsed(getRunElapsed(run));
    setActiveRunId(run.run_id);
  }, []);

  const cancelRun = useCallback(
    async (run: AgentRunStatus) => {
      if (
        run.status !== "pending" &&
        run.status !== "running" &&
        run.status !== "cancel_requested"
      ) {
        return;
      }
      try {
        setErrorMessage(null);
        setCancellingRunId(run.run_id);
        const updated = await cancelAgentRun(run.run_id).unwrap();
        setActiveRunId(updated.run_id);
      } catch {
        setErrorMessage("Could not cancel that run. Please refresh and try again.");
      } finally {
        setCancellingRunId(null);
      }
    },
    [cancelAgentRun],
  );

  const formatElapsed = useCallback((seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;
    return minutes > 0 ? `${minutes}m ${remaining}s` : `${remaining}s`;
  }, []);

  return {
    form,
    updateForm,
    submit,
    isSubmitting,
    errorMessage,
    activeRun,
    activeRunId,
    isRunning,
    elapsed,
    formatElapsed,
    runs,
    viewRun,
    cancelRun,
    cancellingRunId,
  };
}
