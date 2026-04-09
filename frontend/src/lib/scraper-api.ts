import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type {
  AgentRunRequest,
  AgentRunStatus,
  AppConfig,
  DedupeStatus,
  ExportFile,
  HealthStatus,
  JobStatus,
  ScrapeRequest,
} from "@/types";

export const scraperApi = createApi({
  reducerPath: "scraperApi",
  baseQuery: fetchBaseQuery({ baseUrl: "/api" }),
  tagTypes: ["Jobs", "Exports", "Agents"],
  endpoints: (builder) => ({
    getHealth: builder.query<HealthStatus, void>({
      query: () => "/health",
    }),

    getDedupeStatus: builder.query<DedupeStatus, void>({
      query: () => "/dedupe/status",
    }),

    getConfig: builder.query<AppConfig, void>({
      query: () => "/config",
    }),

    startScrape: builder.mutation<JobStatus, ScrapeRequest>({
      query: (body) => ({ url: "/scrape", method: "POST", body }),
      invalidatesTags: ["Jobs"],
    }),

    cancelScrape: builder.mutation<JobStatus, string>({
      query: (jobId) => ({ url: `/scrape/${jobId}`, method: "DELETE" }),
      invalidatesTags: (_result, _err, jobId) => [
        "Jobs",
        { type: "Jobs", id: jobId },
      ],
    }),

    listJobs: builder.query<JobStatus[], { status?: string; limit?: number }>({
      query: ({ status, limit = 20 } = {}) => {
        const params = new URLSearchParams();
        if (status) params.set("status", status);
        params.set("limit", String(limit));
        return `/scrape?${params}`;
      },
      providesTags: ["Jobs"],
    }),

    getJob: builder.query<JobStatus, string>({
      query: (jobId) => `/scrape/${jobId}`,
      providesTags: (_result, _err, jobId) => [{ type: "Jobs", id: jobId }],
    }),

    startAgentRun: builder.mutation<AgentRunStatus, AgentRunRequest>({
      query: (body) => ({ url: "/agent/runs", method: "POST", body }),
      invalidatesTags: ["Agents"],
    }),

    cancelAgentRun: builder.mutation<AgentRunStatus, string>({
      query: (runId) => ({ url: `/agent/runs/${runId}`, method: "DELETE" }),
      invalidatesTags: (_result, _err, runId) => [
        "Agents",
        { type: "Agents", id: runId },
      ],
    }),

    listAgentRuns: builder.query<AgentRunStatus[], { limit?: number }>({
      query: ({ limit = 20 } = {}) => `/agent/runs?limit=${limit}`,
      providesTags: ["Agents"],
    }),

    getAgentRun: builder.query<AgentRunStatus, string>({
      query: (runId) => `/agent/runs/${runId}`,
      providesTags: (_result, _err, runId) => [{ type: "Agents", id: runId }],
    }),

    listExports: builder.query<ExportFile[], number | void>({
      query: (limit = 20) => `/exports?limit=${limit}`,
      providesTags: ["Exports"],
    }),
  }),
});

export const {
  useGetHealthQuery,
  useGetDedupeStatusQuery,
  useGetConfigQuery,
  useStartScrapeMutation,
  useCancelScrapeMutation,
  useListJobsQuery,
  useGetJobQuery,
  useStartAgentRunMutation,
  useCancelAgentRunMutation,
  useListAgentRunsQuery,
  useGetAgentRunQuery,
  useListExportsQuery,
} = scraperApi;
