"use client";

import { useMemo } from "react";
import { File, DownloadSimple, ArrowsClockwise } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DataTable, type Column } from "@/components/data-table";
import type { ExportFile } from "@/types";

interface ExportsListProps {
  exports: ExportFile[];
  isLoading: boolean;
  onRefresh: () => void;
  onDownload: (filename: string) => void;
  formatBytes: (bytes: number) => string;
  formatDate: (iso: string) => string;
}

export function ExportsList({
  exports: files,
  isLoading,
  onRefresh,
  onDownload,
  formatBytes,
  formatDate,
}: ExportsListProps) {
  const columns = useMemo<Column<ExportFile>[]>(
    () => [
      {
        key: "filename",
        header: "Filename",
        className: "font-mono text-xs",
        render: (row) => (
          <span className="flex items-center gap-2">
            <File className="size-4 shrink-0 text-muted-foreground" />
            <span className="truncate" title={row.filename}>
              {row.filename}
            </span>
          </span>
        ),
      },
      {
        key: "size",
        header: "Size",
        headerClassName: "w-[80px] text-right",
        className: "text-right text-xs text-muted-foreground",
        render: (row) => formatBytes(row.size_bytes),
      },
      {
        key: "expiry",
        header: "Expires",
        headerClassName: "w-[180px]",
        className: "text-xs text-muted-foreground",
        render: (row) => (row.expires_at ? formatDate(row.expires_at) : "No expiry"),
      },
      {
        key: "actions",
        header: "",
        headerClassName: "w-[50px]",
        render: (row) => (
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={(e) => {
              e.stopPropagation();
              onDownload(row.filename);
            }}
          >
            <DownloadSimple />
          </Button>
        ),
      },
    ],
    [formatBytes, formatDate, onDownload],
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Export Files</CardTitle>
            <CardDescription>
              {files.length} temporary file{files.length !== 1 && "s"} currently on disk
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={onRefresh}
            disabled={isLoading}
          >
            <ArrowsClockwise
              className={isLoading ? "animate-spin" : ""}
            />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <DataTable
          data={files}
          columns={columns}
          pageSize={8}
          maxHeight="320px"
          rowKey={(row) => row.filename}
          emptyMessage="No export files found yet."
        />
      </CardContent>
    </Card>
  );
}
