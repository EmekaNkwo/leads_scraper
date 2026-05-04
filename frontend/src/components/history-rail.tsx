"use client";

import {
  CaretRight,
  CheckCircle,
  CircleNotch,
  Clock,
  Stop,
  Warning,
  XCircle,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { JobStatus } from "@/types";

interface HistoryRailProps {
  jobs: JobStatus[];
  viewedJobId: string | null;
  onViewJob: (job: JobStatus) => void;
  onCancelJob: (job: JobStatus) => void;
  cancellingJobId: string | null;
}

const TONE: Record<JobStatus["status"], { dot: string; label: string }> = {
  pending: { dot: "bg-muted-foreground/70", label: "pending" },
  running: { dot: "bg-primary pulse-soft", label: "running" },
  completed: { dot: "bg-success", label: "completed" },
  failed: { dot: "bg-destructive", label: "failed" },
  cancelled: { dot: "bg-muted-foreground/80", label: "cancelled" },
};

export function HistoryRail({
  jobs,
  viewedJobId,
  onViewJob,
  onCancelJob,
  cancellingJobId,
}: HistoryRailProps) {
  return (
    <aside className="sticky top-16 flex flex-col bg-card text-card-foreground ring-1 ring-foreground/10 lg:max-h-[calc(100vh-5rem)]">
      <div className="flex items-center gap-3 border-b border-border/60 px-5 py-3">
        <span className="eyebrow">History</span>
        <span className="hairline flex-1" />
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
          {jobs.length} {jobs.length === 1 ? "run" : "runs"}
        </span>
      </div>

      {jobs.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-10 text-center">
          <Clock className="size-5 text-muted-foreground/50" weight="regular" />
          <p className="text-xs text-muted-foreground">
            Past runs will accumulate here.
          </p>
        </div>
      ) : (
        <ol className="flex flex-1 flex-col overflow-y-auto divide-y divide-border/60">
          {jobs.map((job) => (
            <HistoryRow
              key={job.job_id}
              job={job}
              isSelected={job.job_id === viewedJobId}
              isCancelling={cancellingJobId === job.job_id}
              onView={() => onViewJob(job)}
              onCancel={() => onCancelJob(job)}
            />
          ))}
        </ol>
      )}
    </aside>
  );
}

function HistoryRow({
  job,
  isSelected,
  isCancelling,
  onView,
  onCancel,
}: {
  job: JobStatus;
  isSelected: boolean;
  isCancelling: boolean;
  onView: () => void;
  onCancel: () => void;
}) {
  const tone = TONE[job.status];
  const isLive = job.status === "pending" || job.status === "running";

  const StatusIcon =
    job.status === "running"
      ? CircleNotch
      : job.status === "completed"
        ? CheckCircle
        : job.status === "failed"
          ? Warning
          : job.status === "cancelled"
            ? XCircle
            : Clock;

  const firstQuery = job.queries_total > 0 ? job.queries[0] : null;
  const created = new Date(job.created_at);
  const createdLabel = created.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  const dayLabel = created.toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });

  return (
    <li className="group relative">
      {isSelected && (
        <span className="absolute inset-y-2 left-0 w-[2px] bg-primary" />
      )}

      <div className="relative flex items-stretch">
        <button
          type="button"
          onClick={onView}
          aria-current={isSelected ? "true" : undefined}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-3 py-3 pr-11 pl-5 text-left transition-colors duration-150 hover:bg-muted/25",
            isSelected && "bg-primary/[0.05]",
            isLive && "pr-[4.25rem]",
          )}
        >
          <span className="flex size-6 shrink-0 items-center justify-center rounded-[2px] bg-muted/50 text-muted-foreground transition-colors duration-150">
            <StatusIcon
              className={cn(
                "size-3",
                job.status === "running" && "animate-spin text-primary",
                job.status === "completed" && "text-success",
                job.status === "failed" && "text-destructive",
                job.status === "cancelled" && "text-muted-foreground",
              )}
              weight={job.status === "completed" ? "fill" : "regular"}
            />
          </span>

          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex items-center gap-1.5">
              <span className={cn("size-1.5 shrink-0 rounded-full", tone.dot)} />
              <span className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                {tone.label}
              </span>
              <span className="ml-auto numeral text-[10px] text-muted-foreground">
                {dayLabel} · {createdLabel}
              </span>
            </div>
            <p
              className="mt-0.5 truncate text-xs font-medium text-foreground/90"
              title={firstQuery ?? job.job_id}
            >
              {firstQuery ?? "—"}
              {job.queries_total > 1 && (
                <span className="font-normal text-muted-foreground">
                  {" "}+{job.queries_total - 1}
                </span>
              )}
            </p>
            <div className="mt-0.5 flex items-baseline gap-2">
              <span className="font-mono text-[10px] text-muted-foreground/80">
                {job.job_id}
              </span>
              <span className="numeral text-[10px] text-muted-foreground">
                · {job.summary?.total_leads ?? 0} leads
              </span>
            </div>
          </div>

          <CaretRight
            className={cn(
              "size-3 shrink-0 text-muted-foreground/40 transition-colors duration-150 group-hover:text-muted-foreground/70",
              isSelected && "text-primary",
            )}
          />
        </button>

        {isLive && (
          <div
            className={cn(
              "pointer-events-none absolute top-1/2 right-3 z-10 -translate-y-1/2 opacity-0 transition-opacity duration-150 group-hover:pointer-events-auto group-hover:opacity-100",
              isCancelling && "pointer-events-auto opacity-100",
            )}
          >
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={isCancelling}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onCancel();
              }}
              className="size-8 shrink-0 text-muted-foreground transition-colors duration-150 hover:bg-destructive/10 hover:text-destructive"
              aria-label={isCancelling ? "Cancelling" : "Stop run"}
              title={isCancelling ? "Cancelling…" : "Stop"}
            >
              <Stop className="size-4" weight="fill" />
            </Button>
          </div>
        )}
      </div>
    </li>
  );
}
