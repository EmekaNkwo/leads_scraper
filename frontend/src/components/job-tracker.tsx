"use client";

import {
  CheckCircle,
  Clock,
  Spinner,
  Warning,
  XCircle,
} from "@phosphor-icons/react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { JobStatus } from "@/types";

interface JobTrackerProps {
  job: JobStatus | undefined;
  isRunning: boolean;
  elapsed: number;
  formatElapsed: (s: number) => string;
}

const statusConfig = {
  pending: { icon: Clock, label: "Pending", variant: "secondary" as const },
  running: { icon: Spinner, label: "Running", variant: "default" as const },
  completed: {
    icon: CheckCircle,
    label: "Completed",
    variant: "secondary" as const,
  },
  failed: { icon: XCircle, label: "Failed", variant: "destructive" as const },
};

export function JobTracker({
  job,
  isRunning,
  elapsed,
  formatElapsed,
}: JobTrackerProps) {
  if (!job) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Run Status</CardTitle>
          <CardDescription>
            Configure settings and click Run Scraper to begin.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const cfg = statusConfig[job.status];
  const Icon = cfg.icon;
  const progress =
    job.queries_total > 0
      ? Math.round((job.queries_done / job.queries_total) * 100)
      : 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Run Status</CardTitle>
          <Badge variant={cfg.variant} className="gap-1.5">
            <Icon
              weight={job.status === "completed" ? "fill" : "regular"}
              className={job.status === "running" ? "animate-spin" : ""}
            />
            {cfg.label}
          </Badge>
        </div>
        <CardDescription className="font-mono text-xs">
          Job {job.job_id}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isRunning && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Query {job.queries_done} of {job.queries_total}
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                {formatElapsed(elapsed)}
              </span>
            </div>
            <Progress value={progress} />
          </div>
        )}

        {job.results.length > 0 && (
          <>
            <Separator />
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium">Query Results</p>
              {job.results.map((r, i) => (
                <div
                  key={i}
                  className="flex items-start justify-between rounded-md border px-3 py-2 text-sm"
                >
                  <div className="flex items-center gap-2">
                    {r.error ? (
                      <Warning className="size-4 text-destructive" weight="fill" />
                    ) : (
                      <CheckCircle className="size-4 text-green-500" weight="fill" />
                    )}
                    <span className="font-medium">{r.query}</span>
                  </div>
                  {r.error ? (
                    <span className="text-xs text-destructive">{r.error}</span>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {r.leads_count} leads in {r.elapsed_seconds}s
                    </span>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {job.summary?.total_leads > 0 && (
          <>
            <Separator />
            <div className="grid grid-cols-4 gap-3">
              {[
                ["Total", job.summary.total_leads],
                ["Emails", job.summary.emails_found],
                ["Websites", job.summary.websites_found],
                ["Failed", job.summary.queries_failed],
              ].map(([label, val]) => (
                <div
                  key={label as string}
                  className="flex flex-col items-center rounded-md border py-2"
                >
                  <span className="text-lg font-bold">{val}</span>
                  <span className="text-xs text-muted-foreground">
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
