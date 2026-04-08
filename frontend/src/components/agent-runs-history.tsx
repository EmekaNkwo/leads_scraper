"use client";

import { useMemo } from "react";
import {
  CheckCircle,
  Clock,
  Eye,
  Spinner,
  Sparkle,
  XCircle,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DataTable, type Column } from "@/components/data-table";
import type { AgentRunStatus } from "@/types";

interface AgentRunsHistoryProps {
  runs: AgentRunStatus[];
  activeRunId: string | null;
  onViewRun: (run: AgentRunStatus) => void;
  onCancelRun: (run: AgentRunStatus) => void;
  cancellingRunId: string | null;
}

const statusIcon = {
  pending: Clock,
  running: Spinner,
  cancel_requested: Spinner,
  completed: CheckCircle,
  failed: XCircle,
  cancelled: XCircle,
};

const statusVariant = {
  pending: "secondary" as const,
  running: "default" as const,
  cancel_requested: "secondary" as const,
  completed: "secondary" as const,
  failed: "destructive" as const,
  cancelled: "secondary" as const,
};

const defaultStatusIcon = Clock;
const defaultStatusVariant = "secondary" as const;

export function AgentRunsHistory({
  runs,
  activeRunId,
  onViewRun,
  onCancelRun,
  cancellingRunId,
}: AgentRunsHistoryProps) {
  const columns = useMemo<Column<AgentRunStatus>[]>(
    () => [
      {
        key: "run_id",
        header: "Run ID",
        className: "font-mono text-xs",
        render: (row) => row.run_id,
      },
      {
        key: "status",
        header: "Status",
        render: (row) => {
          const Icon = statusIcon[row.status] ?? defaultStatusIcon;
          const variant = statusVariant[row.status] ?? defaultStatusVariant;
          return (
            <Badge variant={variant} className="gap-1">
              <Icon
                className={
                  row.status === "running" || row.status === "cancel_requested"
                    ? "animate-spin"
                    : ""
                }
                weight={row.status === "completed" ? "fill" : "regular"}
              />
              {row.status.replaceAll("_", " ")}
            </Badge>
          );
        },
      },
      {
        key: "queries",
        header: "Queries",
        headerClassName: "text-right",
        className: "text-right",
        render: (row) => row.proposed_queries.length,
      },
      {
        key: "top_leads",
        header: "Top Leads",
        headerClassName: "text-right",
        className: "text-right",
        render: (row) => row.analysis?.top_leads.length ?? 0,
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
            {(row.status === "pending" ||
              row.status === "running" ||
              row.status === "cancel_requested") && (
              <Button
                variant="ghost"
                size="icon-xs"
                className="text-destructive hover:text-destructive"
                disabled={cancellingRunId === row.run_id}
                onClick={(event) => {
                  event.stopPropagation();
                  onCancelRun(row);
                }}
                aria-label={`Cancel run ${row.run_id}`}
                title="Cancel run"
              >
                <XCircle weight="fill" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={(event) => {
                event.stopPropagation();
                onViewRun(row);
              }}
              aria-label={`View run ${row.run_id}`}
            >
              <Eye />
            </Button>
          </div>
        ),
      },
    ],
    [cancellingRunId, onCancelRun, onViewRun],
  );

  if (runs.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Agent Runs</CardTitle>
          <CardDescription>
            Completed and in-flight agent runs will appear here.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>Agent Runs</CardTitle>
            <CardDescription>
              {runs.length} run{runs.length !== 1 && "s"}
            </CardDescription>
          </div>
          <Badge variant="outline" className="gap-1.5">
            <Sparkle className="size-3.5" weight="fill" />
            LangGraph Supervisor
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <DataTable
          data={runs}
          columns={columns}
          pageSize={5}
          maxHeight="280px"
          rowKey={(row) => row.run_id}
          selectedKey={activeRunId}
          onRowClick={onViewRun}
          emptyMessage="No agent runs yet."
        />
      </CardContent>
    </Card>
  );
}
