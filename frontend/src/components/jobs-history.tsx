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
}

const statusIcon = {
  pending: Clock,
  running: Spinner,
  completed: CheckCircle,
  failed: XCircle,
};

const statusVariant = {
  pending: "secondary" as const,
  running: "default" as const,
  completed: "secondary" as const,
  failed: "destructive" as const,
};

export function JobsHistory({ jobs, activeJobId, onViewJob }: JobsHistoryProps) {
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
        headerClassName: "w-[40px]",
        render: (row) => (
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={(e) => {
              e.stopPropagation();
              onViewJob(row);
            }}
          >
            <Eye />
          </Button>
        ),
      },
    ],
    [onViewJob],
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
