"use client";

import { useCallback } from "react";
import { useListExportsQuery } from "@/lib/scraper-api";

function triggerDownload(href: string, filename?: string) {
  const link = document.createElement("a");
  link.href = href;
  if (filename) link.download = filename;
  link.target = "_blank";
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export function useExports() {
  const {
    data: exports = [],
    isLoading,
    isFetching,
    refetch,
  } = useListExportsQuery(20);

  const downloadFile = useCallback((filename: string) => {
    triggerDownload(`/api/exports/${encodeURIComponent(filename)}`, filename);
  }, []);

  const downloadJobCsv = useCallback((jobId: string) => {
    triggerDownload(
      `/api/scrape/${jobId}/csv`,
      `leads_${jobId}.csv`,
    );
  }, []);

  const formatBytes = useCallback((bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }, []);

  const formatDate = useCallback((iso: string) => {
    return new Date(iso).toLocaleString();
  }, []);

  return {
    exports,
    isLoading: isLoading || isFetching,
    refetch,
    downloadFile,
    downloadJobCsv,
    formatBytes,
    formatDate,
  };
}
