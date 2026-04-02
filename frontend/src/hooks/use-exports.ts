"use client";

import { useCallback } from "react";
import { useListExportsQuery } from "@/lib/scraper-api";

export function useExports() {
  const { data: exports = [], isLoading, refetch } = useListExportsQuery(20);

  const downloadFile = useCallback((filename: string) => {
    window.open(`/api/exports/${encodeURIComponent(filename)}`, "_blank");
  }, []);

  const downloadJobCsv = useCallback((jobId: string) => {
    window.open(`/api/scrape/${jobId}/csv`, "_blank");
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
    isLoading,
    refetch,
    downloadFile,
    downloadJobCsv,
    formatBytes,
    formatDate,
  };
}
