"use client";

import { useMemo, useState } from "react";
import { Globe, LinkSimpleHorizontal, Sparkle } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DataTable, type Column } from "@/components/data-table";
import type { AgentLeadInsight, AgentRunStatus } from "@/types";

interface AgentInsightsProps {
  run: AgentRunStatus | undefined;
}

const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;
const DEFAULT_PAGE_SIZE = PAGE_SIZE_OPTIONS[0];
type PageSizeOption = (typeof PAGE_SIZE_OPTIONS)[number];

function getSafeWebsiteUrl(value: string): string | null {
  if (!value || value === "N/A") {
    return null;
  }
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.toString()
      : null;
  } catch {
    return null;
  }
}

export function AgentInsights({ run }: AgentInsightsProps) {
  const rankedLeads = run?.analysis?.top_leads ?? [];
  const [pageSize, setPageSize] = useState<PageSizeOption>(DEFAULT_PAGE_SIZE);
  const hasRankedLeads = rankedLeads.length > 0;
  const emptyMessage = run?.analysis
    ? "No ranked leads matched this run."
    : "Ranked leads will appear after analysis finishes.";

  const columns = useMemo<Column<AgentLeadInsight>[]>(
    () => [
      {
        key: "name",
        header: "Lead",
        headerClassName: "min-w-[180px]",
        className: "font-medium",
        render: (row) => row.name,
      },
      {
        key: "query",
        header: "Planned Query",
        headerClassName: "min-w-[200px]",
        className: "text-xs text-muted-foreground",
        render: (row) => row.query,
      },
      {
        key: "score",
        header: "Score",
        headerClassName: "w-[72px] text-center",
        className: "text-center font-mono text-xs",
        render: (row) => {
          const safeScore = Number.isFinite(row.score) ? row.score : 0;
          return `${Math.round(safeScore * 100)}%`;
        },
      },
      {
        key: "contact",
        header: "Contact",
        headerClassName: "min-w-[180px]",
        render: (row) =>
          row.email !== "N/A" ? (
            <a
              href={`mailto:${row.email}`}
              className="text-primary underline-offset-4 hover:underline"
            >
              {row.email}
            </a>
          ) : (
            <span className="text-muted-foreground">No direct email</span>
          ),
      },
      {
        key: "website",
        header: "Website",
        headerClassName: "w-[90px]",
        render: (row) => {
          const safeUrl = getSafeWebsiteUrl(row.website);
          return safeUrl ? (
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline"
            >
              <Globe className="size-3.5" />
              Visit
            </a>
          ) : (
            <span className="text-muted-foreground">—</span>
          );
        },
      },
      {
        key: "reasons",
        header: "Why It Ranked",
        headerClassName: "min-w-[240px]",
        render: (row) => (
          <div className="flex flex-wrap gap-1.5">
            {row.reasons.map((reason, index) => (
              <Badge
                key={`${reason}-${index}`}
                variant="outline"
                className="font-normal"
              >
                {reason}
              </Badge>
            ))}
          </div>
        ),
      },
    ],
    [],
  );

  if (!run) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Ranked Lead Insights</CardTitle>
          <CardDescription>
            The agent will rank the strongest leads after the linked scrape job
            completes.
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
            <CardTitle>Ranked Lead Insights</CardTitle>
            <CardDescription>
              {run.analysis
                ? rankedLeads.length > 0
                  ? `Showing ${rankedLeads.length} ranked lead${rankedLeads.length === 1 ? "" : "s"} with client-side pagination.`
                  : "Analysis finished, but this run did not produce any ranked leads."
                : "Insights will appear here after the analyst finishes."}
            </CardDescription>
          </div>
          <Badge variant="outline" className="gap-1.5">
            <Sparkle className="size-3.5" weight="fill" />
            Analyst
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {run.analysis?.summary && (
          <div className="rounded-md border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
            <div className="flex items-start gap-2">
              <LinkSimpleHorizontal className="mt-0.5 size-4 text-foreground" />
              <p>{run.analysis.summary}</p>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between gap-3 rounded-md border px-4 py-3">
          <div className="text-sm text-muted-foreground">
            {hasRankedLeads
              ? "Choose how many ranked leads to show per page."
              : "Rows-per-page controls are disabled until ranked leads are available."}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Rows per page</span>
            <select
              value={pageSize}
              onChange={(event) => {
                const nextPageSize = Number.parseInt(event.target.value, 10);
                const matchedPageSize =
                  PAGE_SIZE_OPTIONS.find((size) => size === nextPageSize) ??
                  DEFAULT_PAGE_SIZE;
                setPageSize(matchedPageSize);
              }}
              className="rounded-md border bg-background px-2 py-1 text-sm"
              disabled={!hasRankedLeads}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        </div>

        <DataTable
          key={run.run_id}
          data={rankedLeads}
          columns={columns}
          pageSize={pageSize}
          maxHeight="440px"
          rowKey={(row, index) => `${row.name}-${row.query}-${index}`}
          emptyMessage={emptyMessage}
        />
      </CardContent>
    </Card>
  );
}
