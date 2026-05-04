"use client";

import { useMemo } from "react";
import { CircleNotch, Eye, EyeSlash, Globe, WarningCircle, ArrowsCounterClockwise, type Icon } from "@phosphor-icons/react";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { ScrapeRequest } from "@/types";

interface RunConsoleProps {
  form: ScrapeRequest;
  queriesText: string;
  isSubmitting: boolean;
  isRunning: boolean;
  submitError: string | null;
  onUpdateForm: <K extends keyof ScrapeRequest>(
    field: K,
    value: ScrapeRequest[K],
  ) => void;
  onSetQueries: (raw: string) => void;
  onSubmit: () => void;
}

export function RunConsole({
  form,
  queriesText,
  isSubmitting,
  isRunning,
  submitError,
  onUpdateForm,
  onSetQueries,
  onSubmit,
}: RunConsoleProps) {
  const busy = isSubmitting || isRunning;
  const hasQueries = queriesText.trim().length > 0;

  const lineNumbers = useMemo(() => {
    const lines = queriesText.split("\n");
    const count = Math.max(lines.length, 4);
    return Array.from({ length: count }, (_, i) => i + 1);
  }, [queriesText]);

  const filledQueries = queriesText
    .split("\n")
    .map((q) => q.trim())
    .filter(Boolean).length;

  const recommendedScrolls = useMemo(() => {
    const n = Math.max(1, form.max_results_per_query || 1);
    return Math.min(100, Math.max(8, Math.ceil(n / 5)));
  }, [form.max_results_per_query]);

  const scrollHelper =
    form.max_scrolls_per_query < recommendedScrolls
      ? {
          tone: "warn" as const,
          msg: `Recommend ~${recommendedScrolls} scrolls for ${form.max_results_per_query} leads — current may stop early.`,
        }
      : form.max_scrolls_per_query > recommendedScrolls + 10
        ? {
            tone: "muted" as const,
            msg: `Recommend ~${recommendedScrolls} scrolls — current is higher than typical.`,
          }
        : {
            tone: "ok" as const,
            msg: `Recommend ~${recommendedScrolls} scrolls — current looks healthy.`,
          };

  const actionHint =
    filledQueries > 0
      ? `${filledQueries} ${filledQueries === 1 ? "query" : "queries"} queued`
      : "Add one or more query lines to start";

  return (
    <section className="relative bg-card text-card-foreground ring-1 ring-foreground/10">
      <div className="flex items-center gap-3 border-b border-border/60 px-5 py-3">
        <span className="eyebrow">New Run</span>
        <span className="hairline flex-1" />
        <span className="eyebrow">
          {filledQueries > 0
            ? `${filledQueries} ${filledQueries === 1 ? "line" : "lines"}`
            : "No lines yet"}
        </span>
      </div>

      <div className="grid gap-0 lg:grid-cols-[1fr_minmax(280px,360px)]">
        <div className="flex min-h-[220px] flex-col border-b border-border/60 lg:border-r lg:border-b-0">
          <label
            htmlFor="queries"
            className="flex items-end justify-between gap-3 px-5 pt-4 pb-2"
          >
            <div className="flex flex-col gap-0.5">
              <span className="eyebrow">Queries</span>
              <span className="text-sm font-medium text-foreground/90">
                Search strings
              </span>
            </div>
            <span className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
              one per line
            </span>
          </label>
          <div className="flex flex-1 px-5 pb-4">
            <div
              aria-hidden
              className="select-none pr-3 text-right font-mono text-xs leading-7 text-muted-foreground/40"
            >
              {lineNumbers.map((n) => (
                <div key={n}>{String(n).padStart(2, "0")}</div>
              ))}
            </div>
            <textarea
              id="queries"
              rows={Math.max(4, lineNumbers.length)}
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              placeholder={"electronics store lagos\ncomputer shop ikeja"}
              value={queriesText}
              onChange={(e) => onSetQueries(e.target.value)}
              disabled={busy}
              className={cn(
                "min-h-[140px] w-full flex-1 resize-none border-0 bg-transparent font-mono text-sm leading-7 text-foreground outline-none placeholder:text-muted-foreground/45",
                "focus:outline-none focus-visible:outline-none",
                "disabled:cursor-not-allowed disabled:opacity-60",
              )}
            />
          </div>
        </div>

        <div className="flex flex-col gap-5 border-b border-border/60 px-5 py-4 lg:border-b-0">
          <div className="grid grid-cols-2 gap-3">
            <NumberField
              label="Max leads"
              hint="per query"
              id="maxResults"
              value={form.max_results_per_query}
              min={1}
              max={500}
              disabled={busy}
              onChange={(v) => onUpdateForm("max_results_per_query", v)}
            />
            <NumberField
              label="Max scrolls"
              hint="per query"
              id="maxScrolls"
              value={form.max_scrolls_per_query}
              min={1}
              max={100}
              disabled={busy}
              onChange={(v) => onUpdateForm("max_scrolls_per_query", v)}
            />
          </div>
          <p
            className={cn(
              "text-[11px] leading-snug transition-colors duration-150",
              scrollHelper.tone === "warn" && "text-warning",
              scrollHelper.tone === "ok" && "text-success",
              scrollHelper.tone === "muted" && "text-muted-foreground",
            )}
          >
            {scrollHelper.msg}
          </p>

          <div className="hairline" />

          <div className="flex flex-col gap-2.5">
            <OptionRow
              label="Headless"
              hint="Run the browser invisibly. Turn off to watch the scrape live."
              icon={form.headless ? EyeSlash : Eye}
              checked={form.headless}
              disabled={busy}
              onCheckedChange={(v) => onUpdateForm("headless", v)}
            />
            <OptionRow
              label="Enrich from websites"
              hint="Visit each business website afterward to fill emails, owners, and social links."
              icon={Globe}
              checked={form.enrich_websites}
              disabled={busy}
              onCheckedChange={(v) => onUpdateForm("enrich_websites", v)}
            />
            <OptionRow
              label="Resume from checkpoint"
              hint="Continue a previous run for the same query — including saved scroll progress."
              icon={ArrowsCounterClockwise}
              checked={form.resume}
              disabled={busy}
              onCheckedChange={(v) => onUpdateForm("resume", v)}
            />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2 border-t border-border/60 px-5 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <span className="text-[11px] text-muted-foreground">{actionHint}</span>
        <div className="flex shrink-0 justify-end sm:justify-start">
          <button
            type="button"
            onClick={onSubmit}
            disabled={busy || !hasQueries}
            className={cn(
              "inline-flex h-10 items-center justify-center gap-2 rounded-[2px] bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors duration-150 hover:bg-primary/90",
              "disabled:cursor-not-allowed disabled:opacity-50",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring/60",
            )}
          >
            {busy ? (
              <CircleNotch className="size-4 animate-spin" weight="bold" />
            ) : null}
            {busy ? "Running…" : "Run scrape"}
          </button>
        </div>
      </div>

      {submitError && (
        <div
          role="alert"
          className="flex items-start gap-2 border-t border-destructive/30 bg-destructive/5 px-5 py-2 text-xs text-destructive transition-colors duration-150"
        >
          <WarningCircle className="mt-0.5 size-3.5 shrink-0" weight="fill" />
          <span>
            <span className="font-medium">Submit failed.</span> {submitError}
          </span>
        </div>
      )}
    </section>
  );
}

function NumberField({
  label,
  hint,
  id,
  value,
  min,
  max,
  disabled,
  onChange,
}: {
  label: string;
  hint?: string;
  id: string;
  value: number;
  min?: number;
  max?: number;
  disabled?: boolean;
  onChange: (v: number) => void;
}) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5">
      <span className="flex items-baseline justify-between">
        <span className="eyebrow">{label}</span>
        {hint && (
          <span className="text-[10px] text-muted-foreground/80">{hint}</span>
        )}
      </span>
      <Input
        id={id}
        type="number"
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="font-mono text-sm transition-colors duration-150"
      />
    </label>
  );
}

function OptionRow({
  label,
  hint,
  icon: IconCmp,
  checked,
  disabled,
  onCheckedChange,
}: {
  label: string;
  hint: string;
  icon: Icon;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 border border-transparent px-0 py-1.5 transition-colors duration-150 hover:bg-muted/25">
      <IconCmp className="mt-0.5 size-4 shrink-0 text-muted-foreground" weight="regular" />
      <span className="flex flex-1 flex-col">
        <span className="text-sm font-medium leading-tight">{label}</span>
        <span className="text-[11px] leading-snug text-muted-foreground">
          {hint}
        </span>
      </span>
      <Switch
        checked={checked}
        disabled={disabled}
        onCheckedChange={(v) => onCheckedChange(v === true)}
        className="mt-1.5"
      />
    </label>
  );
}
