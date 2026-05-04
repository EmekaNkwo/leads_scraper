"use client";

import { useState } from "react";
import {
  CaretDown,
  CheckCircle,
  Circle,
  CircleNotch,
  DownloadSimple,
  Pause,
  Pulse,
  Stop,
  Warning,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { JobStatus, QueryResult } from "@/types";

interface ActiveRunProps {
  job: JobStatus | undefined;
  isRunning: boolean;
  cancelling: boolean;
  elapsed: number;
  formatElapsed: (s: number) => string;
  onDownloadCsv: (jobId: string) => void;
  onCancel: () => void;
}

const STATUS_TONE: Record<
  JobStatus["status"],
  { dotClass: string; pillClass: string; label: string }
> = {
  pending: {
    dotClass: "bg-muted-foreground/70",
    pillClass: "border-border/60 bg-muted/20 text-muted-foreground",
    label: "Pending",
  },
  running: {
    dotClass: "bg-primary pulse-soft",
    pillClass: "border-primary/35 bg-primary/10 text-primary",
    label: "Running",
  },
  completed: {
    dotClass: "bg-success",
    pillClass: "border-success/35 bg-success/10 text-success",
    label: "Completed",
  },
  failed: {
    dotClass: "bg-destructive",
    pillClass: "border-destructive/35 bg-destructive/10 text-destructive",
    label: "Failed",
  },
  cancelled: {
    dotClass: "bg-muted-foreground/80",
    pillClass:
      "border-muted-foreground/30 bg-muted/25 text-muted-foreground",
    label: "Cancelled",
  },
};

export function ActiveRun({
  job,
  isRunning,
  cancelling,
  elapsed,
  formatElapsed,
  onDownloadCsv,
  onCancel,
}: ActiveRunProps) {
  const [showDetails, setShowDetails] = useState(false);

  if (!job) {
    return (
      <section className="relative bg-card text-card-foreground ring-1 ring-foreground/10">
        <div className="flex items-center gap-3 border-b border-border/60 px-5 py-3">
          <span className="eyebrow">Active Run</span>
          <span className="hairline flex-1" />
        </div>
        <div className="flex min-h-[220px] flex-col items-center justify-center gap-2 px-6 py-12 text-center">
          <Pulse className="size-6 text-muted-foreground/50" weight="regular" />
          <p className="text-sm font-semibold text-foreground/90">
            No active run
          </p>
          <p className="max-w-xs text-xs text-muted-foreground">
            Start a scrape above to follow it here.
          </p>
        </div>
      </section>
    );
  }

  const tone = STATUS_TONE[job.status];
  const live = job.progress;
  const queryProgress =
    live && live.leads_target > 0
      ? Math.min(
          100,
          Math.round((live.leads_collected / live.leads_target) * 100),
        )
      : 0;
  const overallProgress =
    job.queries_total > 0
      ? Math.round((job.queries_done / job.queries_total) * 100)
      : 0;
  const progressPct = live?.query
    ? Math.max(queryProgress, overallProgress)
    : overallProgress;

  const downloadable =
    job.leads.length > 0 &&
    (job.status === "completed" ||
      job.status === "failed" ||
      job.status === "cancelled");

  const latestExpiry = job.results
    .map((r) => r.export_expires_at)
    .filter((v): v is string => Boolean(v))
    .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())[0];

  const csvTitle =
    job.status === "completed"
      ? "CSV ready"
      : job.status === "cancelled"
        ? "Partial CSV ready"
        : "Recoverable CSV";

  return (
    <section className="relative bg-card text-card-foreground ring-1 ring-foreground/10">
      <div className="flex items-center gap-3 border-b border-border/60 px-5 py-3">
        <span className="eyebrow">Active Run</span>
        <span className="hairline flex-1" />
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-[2px] border px-2 py-0.5 text-[11px] font-medium transition-colors duration-150",
            tone.pillClass,
          )}
        >
          <span className={cn("size-1.5 shrink-0 rounded-full", tone.dotClass)} />
          {tone.label}
        </span>
        {(job.status === "pending" || job.status === "running") && (
          <Button
            variant="ghost"
            size="xs"
            onClick={onCancel}
            disabled={cancelling}
            className="text-destructive transition-colors duration-150 hover:bg-destructive/10 hover:text-destructive"
          >
            <Stop weight="fill" data-icon="inline-start" />
            {cancelling ? "Cancelling…" : "Cancel"}
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-0 sm:grid-cols-3">
        <HeroStat
          label="Leads"
          value={live ? live.leads_collected : job.summary.total_leads}
          sub={
            live
              ? `of ${live.leads_target || "?"}`
              : `${job.summary.queries_succeeded} ${
                  job.summary.queries_succeeded === 1 ? "query" : "queries"
                } done`
          }
        />
        <HeroStat
          label="Elapsed"
          value={
            <span className="font-sans text-3xl font-semibold tabular-nums tracking-tight">
              {formatElapsed(elapsed)}
            </span>
          }
          sub={
            isRunning
              ? "running"
              : job.completed_at
                ? `ended ${new Date(job.completed_at).toLocaleTimeString()}`
                : "—"
          }
          highlight={isRunning}
        />
        <HeroStat
          label="Progress"
          value={
            <span className="font-sans text-3xl font-semibold tabular-nums tracking-tight">
              {progressPct}
              <span className="ml-0.5 text-xl font-semibold text-muted-foreground">
                %
              </span>
            </span>
          }
          sub={`${job.queries_done}/${job.queries_total} queries`}
          right
        />
      </div>

      <div className="hairline" />

      {(isRunning || live) && (
        <div className="flex flex-col gap-3 px-5 py-4">
          <div className="flex items-baseline justify-between gap-3">
            <p className="truncate font-mono text-[11px] text-muted-foreground">
              {live?.query ? (
                <>
                  <span className="text-muted-foreground/80">Now:</span>{" "}
                  <span className="font-medium text-foreground/85">
                    {live.query}
                  </span>
                </>
              ) : (
                <span>Awaiting first query…</span>
              )}
            </p>
            <p className="numeral text-[11px] text-muted-foreground">
              {live ? phaseLabel(live.phase) : ""}
            </p>
          </div>

          <div className="h-1 w-full overflow-hidden bg-muted/60">
            <div
              className="h-full bg-primary transition-[width] duration-500 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          {live && (
            <p className="text-[11px] leading-snug text-muted-foreground">
              {live.message ?? "Waiting for the next progress update…"}
            </p>
          )}
        </div>
      )}

      {job.results.length > 0 && (
        <>
          <div className="hairline" />
          <div className="flex flex-col gap-2 px-5 py-4">
            <span className="eyebrow">Queries</span>
            <div className="flex flex-wrap gap-2">
              {job.results.map((r) => (
                <QueryChip key={r.query} result={r} />
              ))}
              {Array.from({
                length: Math.max(
                  0,
                  job.queries_total - job.results.length - (isRunning ? 1 : 0),
                ),
              }).map((_, i) => (
                <span
                  key={`pending-${i}`}
                  className="inline-flex items-center gap-1.5 rounded-[2px] border border-dashed border-border/60 px-2 py-1 text-[11px] text-muted-foreground/80"
                >
                  <Circle className="size-3" />
                  pending
                </span>
              ))}
              {isRunning && live?.query && (
                <span className="inline-flex items-center gap-1.5 rounded-[2px] border border-primary/35 bg-primary/5 px-2 py-1 text-[11px] text-primary">
                  <CircleNotch className="size-3 animate-spin" />
                  {live.query}
                </span>
              )}
            </div>
          </div>
        </>
      )}

      {downloadable && (
        <>
          <div className="hairline" />
          <div className="flex flex-col gap-3 border-t border-primary/20 bg-primary/[0.04] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-foreground">{csvTitle}</p>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                {job.exports_are_temporary
                  ? `Temporary. Removed after ${job.export_retention_minutes} min${
                      latestExpiry
                        ? ` — earliest expires ${new Date(latestExpiry).toLocaleString()}`
                        : ""
                    }.`
                  : "Persistent on the server."}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onDownloadCsv(job.job_id)}
              className="inline-flex h-10 shrink-0 items-center gap-2 rounded-[2px] bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors duration-150 hover:bg-primary/90"
            >
              <DownloadSimple className="size-4" weight="bold" />
              Download CSV
            </button>
          </div>
        </>
      )}

      <div className="border-t border-border/60">
        <button
          type="button"
          onClick={() => setShowDetails((v) => !v)}
          className="flex w-full items-center gap-2 px-5 py-2.5 text-left transition-colors duration-150 hover:bg-muted/30"
        >
          <span className="eyebrow">Technical details</span>
          <span className="hairline flex-1" />
          <span className="font-mono text-[10px] text-muted-foreground">
            <span className="numeral mr-1">{job.job_id}</span>
          </span>
          <CaretDown
            className={cn(
              "size-3 shrink-0 text-muted-foreground transition-transform duration-150",
              showDetails && "rotate-180",
            )}
          />
        </button>

        {showDetails && (
          <div className="grid gap-4 border-t border-border/60 px-5 py-4 lg:grid-cols-2">
            <DetailField
              label="Phase"
              value={live ? phaseLabel(live.phase) : "—"}
            />
            <DetailField
              label="End reason"
              value={live?.end_reason ? phaseLabel(live.end_reason) : "—"}
            />
            <DetailField
              label="Visible cards"
              value={
                live
                  ? `${live.visible_cards.toLocaleString()}`
                  : `${job.summary.total_leads}`
              }
            />
            <DetailField
              label="Scrolls"
              value={
                live
                  ? `${live.scrolls_used}/${live.max_scrolls || "?"}`
                  : "—"
              }
            />
            <DetailField
              label="Stale scrolls"
              value={live ? `${live.stale_scrolls}` : "—"}
            />
            <DetailField
              label="Latest CSV"
              value={live?.csv_path ? truncatePath(live.csv_path) : "—"}
              mono
            />

            {job.summary.total_leads > 0 && (
              <div className="lg:col-span-2">
                <span className="eyebrow">Summary</span>
                <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-6">
                  <SummaryStat label="Total" value={job.summary.total_leads} />
                  <SummaryStat
                    label="Emails"
                    value={job.summary.emails_found}
                  />
                  <SummaryStat
                    label="Sites"
                    value={job.summary.websites_found}
                  />
                  <SummaryStat
                    label="OK"
                    value={job.summary.queries_succeeded}
                    tone="success"
                  />
                  <SummaryStat
                    label="Cancel"
                    value={job.summary.queries_cancelled}
                  />
                  <SummaryStat
                    label="Fail"
                    value={job.summary.queries_failed}
                    tone="destructive"
                  />
                </div>
              </div>
            )}

            {job.recent_events.length > 0 && (
              <div className="lg:col-span-2">
                <span className="eyebrow">Recent events</span>
                <div className="mt-2 max-h-44 space-y-1 overflow-auto rounded-[2px] border border-border/60 bg-muted/30 p-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
                  {job.recent_events
                    .slice()
                    .reverse()
                    .map((e, i) => (
                      <div key={`${i}-${e.slice(0, 32)}`} className="flex gap-2">
                        <span className="text-muted-foreground/50">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span>{e}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function HeroStat({
  label,
  value,
  sub,
  right,
  highlight,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  right?: boolean;
  highlight?: boolean;
}) {
  const isPrimitive = typeof value === "number" || typeof value === "string";
  return (
    <div
      className={cn(
        "relative flex flex-col gap-1.5 px-5 py-5 sm:px-6 sm:py-6",
        right ? "sm:items-end" : "items-start",
        highlight && "bg-primary/[0.04]",
      )}
    >
      <span className="eyebrow">{label}</span>
      {isPrimitive ? (
        <span className="font-sans text-3xl font-semibold tabular-nums tracking-tight">
          {value}
        </span>
      ) : (
        <span className="leading-none">{value}</span>
      )}
      {sub && (
        <span className="text-[11px] text-muted-foreground">{sub}</span>
      )}
    </div>
  );
}

function QueryChip({ result }: { result: QueryResult }) {
  const tone =
    result.status === "completed"
      ? {
          icon: <CheckCircle className="size-3" weight="fill" />,
          cls: "border-success/35 bg-success/8 text-success",
        }
      : result.status === "failed"
        ? {
            icon: <Warning className="size-3" weight="fill" />,
            cls: "border-destructive/35 bg-destructive/8 text-destructive",
          }
        : {
            icon: <Pause className="size-3" weight="fill" />,
            cls: "border-border/60 bg-muted/25 text-muted-foreground",
          };

  return (
    <span
      className={cn(
        "inline-flex max-w-[260px] items-center gap-1.5 rounded-[2px] border px-2 py-1 text-[11px] transition-colors duration-150",
        tone.cls,
      )}
      title={result.error ?? `${result.leads_count} leads`}
    >
      {tone.icon}
      <span className="truncate">{result.query}</span>
      <span className="numeral text-[10px] opacity-90">
        {result.status === "failed"
          ? "fail"
          : `${result.leads_count} · ${result.elapsed_seconds}s`}
      </span>
    </span>
  );
}

function DetailField({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="eyebrow">{label}</span>
      <span
        className={cn(
          "text-xs text-foreground/90",
          mono && "font-mono break-all",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "success" | "destructive";
}) {
  return (
    <div className="flex flex-col items-center rounded-[2px] border border-border/60 bg-muted/20 px-2 py-2">
      <span
        className={cn(
          "font-sans text-xl font-semibold tabular-nums tracking-tight",
          tone === "success" && "text-success",
          tone === "destructive" && "text-destructive",
        )}
      >
        {value}
      </span>
      <span className="eyebrow mt-0.5">{label}</span>
    </div>
  );
}

function phaseLabel(value: string) {
  return value.replaceAll("_", " ");
}

function truncatePath(value: string) {
  if (value.length <= 56) return value;
  return `…${value.slice(-55)}`;
}
