"use client";

import { useMemo } from "react";
import { Eye, CheckCircle, XCircle, Clock, Spinner } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataTable, type Column } from "@/components/data-table";
import type { JobStatus } from "@/types";

interface JobsHistoryProps {
  jobs: JobStatus[];
  activeJobId: string | null;
  onViewJob: (job: JobStatus) => void;
  onCancelJob: (job: JobStatus) => void;
  cancellingJobId: string | null;
}

const statusIcon = {
  pending: Clock,
  running: Spinner,
  completed: CheckCircle,
  failed: XCircle,
  cancelled: XCircle,
};

const statusVariant = {
  pending: "secondary" as const,
  running: "default" as const,
  completed: "secondary" as const,
  failed: "destructive" as const,
  cancelled: "secondary" as const,
};

export function JobsHistory({
  jobs,
  activeJobId,
  onViewJob,
  onCancelJob,
  cancellingJobId,
}: JobsHistoryProps) {
  const columns = useMemo<Column<JobStatus>[]>(
    () => [
      {
        key: "job_id",
        header: "Job ID",
        className: "font-mono text-xs",
        render: (row) => row.job_id,
      },
      {
        key: "status",
        header: "Status",
        render: (row) => {
          const Icon = statusIcon[row.status];
          return (
            <Badge variant={statusVariant[row.status]} className="gap-1">
              <Icon
                className={row.status === "running" ? "animate-spin" : ""}
                weight={row.status === "completed" ? "fill" : "regular"}
              />
              {row.status}
            </Badge>
          );
        },
      },
      {
        key: "leads",
        header: "Leads",
        headerClassName: "text-right",
        className: "text-right",
        render: (row) => row.summary?.total_leads ?? 0,
      },
      {
        key: "created",
        header: "Created",
        headerClassName: "w-[120px]",
        className: "text-xs text-muted-foreground",
        render: (row) => new Date(row.created_at).toLocaleTimeString(),
      },
      {
        key: "actions",
        header: "",
        headerClassName: "w-[84px]",
        render: (row) => (
          <div className="flex items-center justify-end gap-1">
            {(row.status === "pending" || row.status === "running") && (
              <Button
                variant="ghost"
                size="icon-xs"
                className="text-destructive hover:text-destructive"
                disabled={cancellingJobId === row.job_id}
                onClick={(e) => {
                  e.stopPropagation();
                  onCancelJob(row);
                }}
                aria-label={`Cancel job ${row.job_id}`}
                title="Cancel job"
              >
                <XCircle weight="fill" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={(e) => {
                e.stopPropagation();
                onViewJob(row);
              }}
              aria-label={`View job ${row.job_id}`}
            >
              <Eye />
            </Button>
          </div>
        ),
      },
    ],
    [cancellingJobId, onCancelJob, onViewJob],
  );

  if (jobs.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Job History</CardTitle>
          <CardDescription>
            Past scraping jobs will appear here.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Job History</CardTitle>
        <CardDescription>
          {jobs.length} job{jobs.length !== 1 && "s"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <DataTable
          data={jobs}
          columns={columns}
          pageSize={5}
          maxHeight="280px"
          rowKey={(row) => row.job_id}
          selectedKey={activeJobId}
          onRowClick={onViewJob}
          emptyMessage="No jobs yet."
        />
      </CardContent>
    </Card>
  );
}
