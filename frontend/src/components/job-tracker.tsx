"use client";

import {
  CheckCircle,
  Clock,
  DownloadSimple,
  Info,
  Spinner,
  Warning,
  XCircle,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useGetDedupeStatusQuery } from "@/lib/scraper-api";
import type { JobStatus } from "@/types";

interface JobTrackerProps {
  job: JobStatus | undefined;
  onDownloadCsv: (jobId: string) => void;
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
  cancelled: { icon: XCircle, label: "Cancelled", variant: "secondary" as const },
};

export function JobTracker({
  job,
  onDownloadCsv,
  isRunning,
  elapsed,
  formatElapsed,
}: JobTrackerProps) {
  const { data: dedupeStatus } = useGetDedupeStatusQuery(undefined, {
    pollingInterval: 30000,
  });

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
  const liveProgress = job.progress;
  const queryProgress =
    liveProgress && liveProgress.leads_target > 0
      ? Math.min(
          100,
          Math.round((liveProgress.leads_collected / liveProgress.leads_target) * 100),
        )
      : 0;
  const overallProgress =
    job.queries_total > 0
      ? Math.round((job.queries_done / job.queries_total) * 100)
      : 0;
  const progress = liveProgress?.query ? Math.max(queryProgress, overallProgress) : overallProgress;
  const latestExportExpiry = job.results
    .map((result) => result.export_expires_at)
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => new Date(left).getTime() - new Date(right).getTime())[0];
  const shouldShowDownloadPrompt =
    !isRunning &&
    job.leads.length > 0 &&
    (job.status === "completed" || job.status === "failed" || job.status === "cancelled");
  const formatExpiry = (iso: string) => new Date(iso).toLocaleString();
  const hasSummaryStats =
    (job.summary?.total_leads ?? 0) > 0 ||
    (job.summary?.queries_failed ?? 0) > 0 ||
    (job.summary?.queries_cancelled ?? 0) > 0 ||
    (job.summary?.queries_succeeded ?? 0) > 0;

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
        {dedupeStatus ? (
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span>
                Persistent memory:{" "}
                <span className="font-mono font-medium text-foreground">
                  {dedupeStatus.alias_count.toLocaleString()}
                </span>{" "}
                businesses seen
              </span>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="inline-flex items-center text-muted-foreground transition-colors hover:text-foreground"
                    aria-label="Explain persistent memory"
                  >
                    <Info className="size-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[260px]">
                  This count comes from SQLite dedupe keys used to remember
                  previously seen businesses. It is not a count of full CSV rows
                  stored on disk.
                </TooltipContent>
              </Tooltip>
            </div>
          </div>
        ) : null}

        {shouldShowDownloadPrompt && (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">
                  {job.status === "completed"
                    ? "Scrape finished successfully. Download your CSV now."
                    : "Partial results are ready. Download your CSV now."}
                </p>
                <p className="text-xs text-muted-foreground">
                  {job.exports_are_temporary
                    ? `Temporary CSV files are removed automatically after ${job.export_retention_minutes} minutes${latestExportExpiry ? `, and may disappear as early as ${formatExpiry(latestExportExpiry)}` : ""}.`
                    : "Download this CSV now to keep a local copy of the results."}
                </p>
                {!job.master_csv_enabled && (
                  <p className="text-xs text-muted-foreground">
                    Long-term export archiving is disabled on this deployment.
                  </p>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={() => onDownloadCsv(job.job_id)}>
                <DownloadSimple data-icon="inline-start" />
                Download CSV
              </Button>
            </div>
          </div>
        )}

        {isRunning && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {liveProgress?.query
                  ? `${liveProgress.query} · ${liveProgress.leads_collected}/${liveProgress.leads_target} leads`
                  : `Query ${job.queries_done} of ${job.queries_total}`}
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                {formatElapsed(elapsed)}
              </span>
            </div>
            <Progress value={progress} />
          </div>
        )}

        {liveProgress && (
          <>
            <div className="rounded-md border px-3 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">
                    {liveProgress.query ?? "Awaiting query"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {liveProgress.message ?? "Waiting for progress updates"}
                  </p>
                </div>
                <Badge variant="outline" className="font-mono text-[10px] uppercase">
                  {liveProgress.phase.replaceAll("_", " ")}
                </Badge>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                <div className="rounded-md bg-muted/40 px-2 py-2">
                  <div className="text-muted-foreground">Leads</div>
                  <div className="font-mono">
                    {liveProgress.leads_collected}/{liveProgress.leads_target || "?"}
                  </div>
                </div>
                <div className="rounded-md bg-muted/40 px-2 py-2">
                  <div className="text-muted-foreground">Visible cards</div>
                  <div className="font-mono">{liveProgress.visible_cards}</div>
                </div>
                <div className="rounded-md bg-muted/40 px-2 py-2">
                  <div className="text-muted-foreground">Scrolls</div>
                  <div className="font-mono">
                    {liveProgress.scrolls_used}/{liveProgress.max_scrolls || "?"}
                  </div>
                </div>
                <div className="rounded-md bg-muted/40 px-2 py-2">
                  <div className="text-muted-foreground">Stale</div>
                  <div className="font-mono">{liveProgress.stale_scrolls}</div>
                </div>
              </div>

              {(liveProgress.end_reason || liveProgress.csv_path) && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  {liveProgress.end_reason && (
                    <span>End reason: {liveProgress.end_reason.replaceAll("_", " ")}</span>
                  )}
                  {liveProgress.csv_path && <span>Latest CSV: {liveProgress.csv_path}</span>}
                  {liveProgress.export_expires_at && (
                    <span>Expires: {formatExpiry(liveProgress.export_expires_at)}</span>
                  )}
                </div>
              )}
            </div>
          </>
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
                    {r.status === "failed" ? (
                      <Warning className="size-4 text-destructive" weight="fill" />
                    ) : r.status === "cancelled" ? (
                      <XCircle className="size-4 text-muted-foreground" weight="fill" />
                    ) : (
                      <CheckCircle className="size-4 text-green-500" weight="fill" />
                    )}
                    <span className="font-medium">{r.query}</span>
                  </div>
                  {r.status === "failed" ? (
                    <span className="text-xs text-destructive">{r.error}</span>
                  ) : r.status === "cancelled" ? (
                    <span className="text-xs text-muted-foreground">
                      Cancelled after {r.elapsed_seconds}s
                    </span>
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

        {job.recent_events.length > 0 && (
          <>
            <Separator />
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium">Recent Events</p>
              <div className="space-y-2">
                {job.recent_events
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

        {hasSummaryStats && (
          <>
            <Separator />
            <div className="grid grid-cols-6 gap-3">
              {[
                ["Total", job.summary.total_leads],
                ["Emails", job.summary.emails_found],
                ["Websites", job.summary.websites_found],
                ["Completed", job.summary.queries_succeeded],
                ["Cancelled", job.summary.queries_cancelled],
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
