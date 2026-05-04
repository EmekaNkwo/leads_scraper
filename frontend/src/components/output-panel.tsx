"use client";

import { useState } from "react";
import {
  ArrowsClockwise,
  CaretLeft,
  CaretRight,
  DownloadSimple,
  File,
  GlobeSimple,
  Hash,
  Table as TableIcon,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type { ExportFile, JobStatus, Lead } from "@/types";

interface OutputPanelProps {
  job: JobStatus | undefined;
  exports: ExportFile[];
  exportsLoading: boolean;
  onRefreshExports: () => void;
  onDownloadJobCsv: (jobId: string) => void;
  onDownloadFile: (filename: string) => void;
  formatBytes: (bytes: number) => string;
  formatDate: (iso: string) => string;
}

const PAGE_SIZE = 10;

export function OutputPanel({
  job,
  exports,
  exportsLoading,
  onRefreshExports,
  onDownloadJobCsv,
  onDownloadFile,
  formatBytes,
  formatDate,
}: OutputPanelProps) {
  const leads = job?.leads ?? [];
  const hasJobCsv =
    !!job &&
    job.leads.length > 0 &&
    (job.status === "completed" ||
      job.status === "failed" ||
      job.status === "cancelled");
  const downloadCount = (hasJobCsv ? 1 : 0) + exports.length;

  return (
    <section className="relative bg-card text-card-foreground ring-1 ring-foreground/10">
      <Tabs defaultValue="leads">
        <div className="flex items-center gap-3 border-b border-border/60 px-3 py-2 sm:px-5">
          <TabsList variant="line" className="-mb-[3px] gap-3 px-0">
            <TabsTrigger
              value="leads"
              className="px-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground/80 data-active:text-foreground"
            >
              Leads
              <span className="ml-1.5 font-mono text-[10px] tabular-nums text-muted-foreground/70">
                {leads.length}
              </span>
            </TabsTrigger>
            <TabsTrigger
              value="downloads"
              className="px-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground/80 data-active:text-foreground"
            >
              Downloads
              <span className="ml-1.5 font-mono text-[10px] tabular-nums text-muted-foreground/70">
                {downloadCount}
              </span>
            </TabsTrigger>
          </TabsList>
          <span className="hairline flex-1" />
          <button
            type="button"
            onClick={onRefreshExports}
            disabled={exportsLoading}
            className="flex size-6 items-center justify-center text-muted-foreground transition-colors duration-150 hover:text-foreground disabled:opacity-50"
            aria-label="Refresh export list"
            title="Refresh export list"
          >
            <ArrowsClockwise
              className={cn("size-3.5", exportsLoading && "animate-spin")}
              weight="bold"
            />
          </button>
        </div>

        <TabsContent value="leads" className="mt-0">
          <LeadsView key={job?.job_id ?? "empty"} leads={leads} />
        </TabsContent>

        <TabsContent value="downloads" className="mt-0">
          {downloadCount === 0 ? (
            <div className="flex min-h-[200px] flex-col items-center justify-center gap-2 px-6 py-10 text-center">
              <File className="size-6 text-muted-foreground/45" />
              <p className="text-sm font-semibold text-foreground/90">
                No exports yet
              </p>
              <p className="max-w-xs text-xs text-muted-foreground">
                Files appear after a run finishes.
              </p>
            </div>
          ) : (
            <div>
              {hasJobCsv && job && (
                <DownloadRow
                  featured
                  icon={<Hash className="size-3.5" weight="bold" />}
                  title={`This run · ${job.job_id}`}
                  sub={`${job.leads.length} ${
                    job.leads.length === 1 ? "lead" : "leads"
                  } · ${job.status}`}
                  actionLabel="Download CSV"
                  onAction={() => onDownloadJobCsv(job.job_id)}
                />
              )}
              {exports.map((file) => (
                <DownloadRow
                  key={file.filename}
                  icon={<File className="size-3.5" weight="regular" />}
                  title={file.filename}
                  titleMono
                  sub={[
                    formatBytes(file.size_bytes),
                    file.expires_at
                      ? `expires ${formatDate(file.expires_at)}`
                      : "no expiry",
                  ].join(" · ")}
                  actionLabel="Download"
                  onAction={() => onDownloadFile(file.filename)}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </section>
  );
}

function LeadsView({ leads }: { leads: Lead[] }) {
  const [page, setPage] = useState(0);

  if (leads.length === 0) {
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center gap-2 px-6 py-10 text-center">
        <TableIcon className="size-6 text-muted-foreground/45" />
        <p className="text-sm font-semibold text-foreground/90">
          No leads yet
        </p>
        <p className="max-w-xs text-xs text-muted-foreground">
          Pick or start a run to see results stream in.
        </p>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(leads.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const start = safePage * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, leads.length);
  const pageLeads = leads.slice(start, end);

  return (
    <>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-border/60 hover:bg-transparent [&>th]:eyebrow [&>th]:px-5 [&>th]:py-2">
              <TableHead className="min-w-[160px]">Name</TableHead>
              <TableHead className="min-w-[120px]">Phone</TableHead>
              <TableHead className="min-w-[200px]">Address</TableHead>
              <TableHead className="min-w-[140px]">Email</TableHead>
              <TableHead className="min-w-[100px]">Category</TableHead>
              <TableHead className="min-w-[80px]">Web</TableHead>
              <TableHead className="w-[64px] text-right">Score</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageLeads.map((lead, i) => (
              <LeadRow
                key={`${lead.name}-${lead.phone}-${start + i}`}
                lead={lead}
              />
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border/60 px-5 py-2">
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {start + 1}–{end}{" "}
          <span className="text-muted-foreground/60">of</span> {leads.length}
        </span>
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="icon-xs"
            disabled={safePage === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            aria-label="Previous page"
          >
            <CaretLeft weight="bold" />
          </Button>
          <span className="min-w-[52px] text-center font-mono text-[11px] tabular-nums text-muted-foreground">
            {safePage + 1} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="icon-xs"
            disabled={safePage >= totalPages - 1}
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            aria-label="Next page"
          >
            <CaretRight weight="bold" />
          </Button>
        </div>
      </div>
    </>
  );
}

function LeadRow({ lead }: { lead: Lead }) {
  return (
    <TableRow className="border-b border-border/30 transition-colors duration-150 last:border-b-0 hover:bg-muted/15 [&>td]:px-5 [&>td]:py-2">
      <TableCell className="font-medium">
        <div className="flex flex-col leading-snug">
          <span className="text-foreground/90">{lead.name}</span>
          {lead.owner_name !== "N/A" && (
            <span className="text-[10px] text-muted-foreground">
              {lead.owner_name}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell className="font-mono text-xs text-foreground/80">
        {lead.phone}
      </TableCell>
      <TableCell className="max-w-[260px]">
        <span
          className="block truncate text-xs text-foreground/80"
          title={lead.address}
        >
          {lead.address}
        </span>
      </TableCell>
      <TableCell>
        {lead.email !== "N/A" ? (
          <a
            href={`mailto:${lead.email}`}
            className="text-xs text-primary underline-offset-4 transition-colors duration-150 hover:underline"
          >
            {lead.email}
          </a>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell>
        {lead.category !== "N/A" ? (
          <span className="inline-flex rounded-[2px] border border-border bg-muted/40 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            {lead.category}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell>
        {lead.website !== "N/A" ? (
          <a
            href={lead.website}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary underline-offset-4 transition-colors duration-150 hover:underline"
          >
            <GlobeSimple className="size-3" />
            visit
          </a>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-right">
        <ConfidenceBadge value={lead.confidence_score} />
      </TableCell>
    </TableRow>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  const tone =
    pct >= 75
      ? "border-success/35 bg-success/10 text-success"
      : pct >= 45
        ? "border-warning/35 bg-warning/10 text-warning"
        : "border-border/60 bg-muted/30 text-muted-foreground";
  return (
    <span
      className={cn(
        "inline-flex min-w-[42px] justify-center rounded-[2px] border px-1.5 py-0.5 font-mono text-[10px] tabular-nums transition-colors duration-150",
        tone,
      )}
    >
      {pct}%
    </span>
  );
}

function DownloadRow({
  icon,
  title,
  titleMono,
  sub,
  featured,
  actionLabel,
  onAction,
}: {
  icon: React.ReactNode;
  title: string;
  titleMono?: boolean;
  sub: string;
  featured?: boolean;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b border-border/30 px-5 py-3 transition-colors duration-150 last:border-b-0",
        featured && "border-l-2 border-l-primary bg-primary/[0.04]",
      )}
    >
      <span className="flex size-6 shrink-0 items-center justify-center rounded-[2px] bg-muted/50 text-muted-foreground">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "truncate text-xs text-foreground/90",
            titleMono ? "font-mono" : "font-medium",
          )}
        >
          {title}
        </p>
        <p className="text-[11px] text-muted-foreground">{sub}</p>
      </div>
      <Button
        variant={featured ? "default" : "outline"}
        size="sm"
        onClick={onAction}
        className="gap-1.5 rounded-[2px]"
      >
        <DownloadSimple weight="bold" data-icon="inline-start" />
        {actionLabel}
      </Button>
    </div>
  );
}
