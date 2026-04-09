"use client";

import {
  CheckCircle,
  Clock,
  DownloadSimple,
  Spinner,
  XCircle,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import type { AgentRunStatus } from "@/types";

interface AgentRunTrackerProps {
  run: AgentRunStatus | undefined;
  isRunning: boolean;
  elapsed: number;
  formatElapsed: (seconds: number) => string;
  onDownloadCsv: (run: AgentRunStatus) => void;
}

const statusConfig = {
  pending: { icon: Clock, label: "Pending", variant: "secondary" as const },
  running: { icon: Spinner, label: "Running", variant: "default" as const },
  cancel_requested: {
    icon: Spinner,
    label: "Cancelling",
    variant: "secondary" as const,
  },
  completed: {
    icon: CheckCircle,
    label: "Completed",
    variant: "secondary" as const,
  },
  failed: { icon: XCircle, label: "Failed", variant: "destructive" as const },
  cancelled: { icon: XCircle, label: "Cancelled", variant: "secondary" as const },
};

const defaultStatusConfig = {
  icon: Clock,
  label: "Unknown",
  variant: "secondary" as const,
};

export function AgentRunTracker({
  run,
  isRunning,
  elapsed,
  formatElapsed,
  onDownloadCsv,
}: AgentRunTrackerProps) {
  if (!run) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Agent Status</CardTitle>
          <CardDescription>
            Describe a sourcing goal and start an agent run to see planned
            queries and ranked results.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const cfg = statusConfig[run.status] ?? defaultStatusConfig;
  const Icon = cfg.icon;
  const hasSummary = !!run.analysis;
  const hasLinkedExport = !!run.linked_export_filename;
  const progressValue = run.status === "completed"
    ? 100
    : run.status === "failed" || run.status === "cancelled"
      ? 100
      : run.proposed_queries.length > 0
        ? 60
        : 20;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>Agent Status</CardTitle>
            <CardDescription className="font-mono text-xs">
              Run {run.run_id}
            </CardDescription>
          </div>
          <Badge variant={cfg.variant} className="gap-1.5">
            <Icon
              weight={run.status === "completed" ? "fill" : "regular"}
              className={
                run.status === "running" || run.status === "cancel_requested"
                  ? "animate-spin"
                  : ""
              }
            />
            {cfg.label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="rounded-md border px-3 py-3">
          <p className="text-sm font-medium">{run.goal}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {run.progress?.message ?? "Waiting for supervisor updates."}
          </p>
          {run.error && (
            <p className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {run.error}
            </p>
          )}
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{run.progress?.phase?.replaceAll("_", " ") ?? "queued"}</span>
              <span className="font-mono">{formatElapsed(elapsed)}</span>
            </div>
            {isRunning && (
              <Progress value={progressValue} />
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-md border bg-muted/30 px-3 py-2">
            <div className="text-xs text-muted-foreground">Planned queries</div>
            <div className="text-lg font-semibold">{run.proposed_queries.length}</div>
          </div>
          <div className="rounded-md border bg-muted/30 px-3 py-2">
            <div className="text-xs text-muted-foreground">Linked scrape job</div>
            <div className="font-mono text-sm">
              {run.scrape_job_id ?? "Waiting"}
            </div>
          </div>
          <div className="rounded-md border bg-muted/30 px-3 py-2">
            <div className="text-xs text-muted-foreground">Scrape status</div>
            <div className="text-sm font-medium capitalize">
              {(run.scrape_job_status ?? "pending").replaceAll("_", " ")}
            </div>
          </div>
        </div>

        {run.proposed_queries.length > 0 && (
          <>
            <Separator />
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium">Planned Queries</p>
              <div className="flex flex-wrap gap-2">
                {run.proposed_queries.map((query, index) => (
                  <Badge
                    key={`${query}-${index}`}
                    variant="secondary"
                    className="max-w-full"
                  >
                    <span className="truncate">{query}</span>
                  </Badge>
                ))}
              </div>
            </div>
          </>
        )}

        {hasSummary && (
          <>
            <Separator />
            <div className="grid grid-cols-3 gap-3">
              {[
                ["Total Leads", run.analysis?.total_leads ?? 0],
                ["Emails", run.analysis?.emails_found ?? 0],
                ["Websites", run.analysis?.websites_found ?? 0],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="flex flex-col items-center rounded-md border py-3"
                >
                  <span className="text-lg font-bold">{value}</span>
                  <span className="text-xs text-muted-foreground">{label}</span>
                </div>
              ))}
            </div>
          </>
        )}

        {hasLinkedExport &&
          (run.status === "completed" ||
            run.status === "failed" ||
            run.status === "cancelled") && (
            <Button
              variant="outline"
              size="sm"
              className="w-fit"
              onClick={() => onDownloadCsv(run)}
            >
              <DownloadSimple data-icon="inline-start" />
              Download Linked CSV
            </Button>
          )}

        {run.recent_events.length > 0 && (
          <>
            <Separator />
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium">Recent Events</p>
              <div className="space-y-2">
                {run.recent_events
                  .slice()
                  .reverse()
                  .map((event, index) => (
                    <div
                      key={`${event}-${index}`}
                      className="rounded-md border px-3 py-2 text-xs text-muted-foreground"
                    >
                      {event}
                    </div>
                  ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
