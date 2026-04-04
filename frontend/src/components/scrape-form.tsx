"use client";

import { useMemo } from "react";
import { Play, Spinner } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ScrapeRequest } from "@/types";

interface ScrapeFormProps {
  form: ScrapeRequest;
  queriesText: string;
  isSubmitting: boolean;
  isRunning: boolean;
  onUpdateForm: <K extends keyof ScrapeRequest>(
    field: K,
    value: ScrapeRequest[K],
  ) => void;
  onSetQueries: (raw: string) => void;
  onSubmit: () => void;
}

const TOGGLE_TOOLTIPS = {
  headless:
    "Runs the browser in the background without opening the Google Maps window. Turn this off if you want to watch the scraper work live.",
  enrich_websites:
    "Visits each business website after scraping to look for extra details like email addresses or owner hints. This usually improves data quality but makes runs slower.",
  resume:
    "Loads saved checkpoint data for the same query so the scraper can continue from earlier progress instead of starting over.",
} satisfies Record<"headless" | "enrich_websites" | "resume", string>;

export function ScrapeForm({
  form,
  queriesText,
  isSubmitting,
  isRunning,
  onUpdateForm,
  onSetQueries,
  onSubmit,
}: ScrapeFormProps) {
  const busy = isSubmitting || isRunning;
  const recommendedMaxScrolls = useMemo(() => {
    const results = Math.max(1, form.max_results_per_query || 1);
    return Math.min(100, Math.max(8, Math.ceil(results / 5)));
  }, [form.max_results_per_query]);

  const scrollRecommendation = useMemo(() => {
    const current = form.max_scrolls_per_query || 0;
    if (current < recommendedMaxScrolls) {
      return {
        className: "text-amber-600",
        message: `Recommended: about ${recommendedMaxScrolls} scrolls for ${form.max_results_per_query} results. Current value may stop early.`,
      };
    }
    if (current > recommendedMaxScrolls + 10) {
      return {
        className: "text-muted-foreground",
        message: `Recommended: about ${recommendedMaxScrolls} scrolls for ${form.max_results_per_query} results. Current value is higher than typical.`,
      };
    }
    return {
      className: "text-emerald-600",
      message: `Recommended: about ${recommendedMaxScrolls} scrolls for ${form.max_results_per_query} results. Current value looks reasonable.`,
    };
  }, [form.max_results_per_query, form.max_scrolls_per_query, recommendedMaxScrolls]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Run Configuration</CardTitle>
        <CardDescription>
          Set your queries and scraping parameters
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="queries">Queries (one per line)</Label>
          <Textarea
            id="queries"
            rows={5}
            placeholder={"electronics store lagos\ncomputer shop ikeja"}
            value={queriesText}
            onChange={(e) => onSetQueries(e.target.value)}
            disabled={busy}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="maxResults">Max results</Label>
            <Input
              id="maxResults"
              type="number"
              min={1}
              max={500}
              value={form.max_results_per_query}
              onChange={(e) =>
                onUpdateForm("max_results_per_query", Number(e.target.value))
              }
              disabled={busy}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="maxScrolls">Max scrolls</Label>
            <Input
              id="maxScrolls"
              type="number"
              min={1}
              max={100}
              value={form.max_scrolls_per_query}
              onChange={(e) =>
                onUpdateForm("max_scrolls_per_query", Number(e.target.value))
              }
              disabled={busy}
            />
            <p className={`text-xs ${scrollRecommendation.className}`}>
              {scrollRecommendation.message}
            </p>
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-2 gap-3">
          {([
            ["headless", "Headless mode"],
            ["enrich_websites", "Website enrichment"],
            ["resume", "Resume checkpoint"],
          ] as const).map(([key, label]) => (
            <Tooltip key={key}>
              <TooltipTrigger asChild>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox
                    checked={form[key]}
                    onCheckedChange={(v) =>
                      onUpdateForm(key, v === true)
                    }
                    disabled={busy}
                  />
                  {label}
                </label>
              </TooltipTrigger>
              <TooltipContent side="top" sideOffset={6}>
                {TOGGLE_TOOLTIPS[key]}
              </TooltipContent>
            </Tooltip>
          ))}
        </div>

        <Button
          className="w-full"
          size="lg"
          onClick={onSubmit}
          disabled={busy || queriesText.trim().length === 0}
        >
          {busy ? (
            <>
              <Spinner className="animate-spin" data-icon="inline-start" />
              Running...
            </>
          ) : (
            <>
              <Play weight="fill" data-icon="inline-start" />
              Run Scraper
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
