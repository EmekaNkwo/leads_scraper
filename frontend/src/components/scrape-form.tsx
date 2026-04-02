"use client";

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
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-2 gap-3">
          {([
            ["headless", "Headless mode"],
            ["enrich_websites", "Website enrichment"],
            ["export_json", "Export JSON"],
            ["resume", "Resume checkpoint"],
          ] as const).map(([key, label]) => (
            <label
              key={key}
              className="flex items-center gap-2 text-sm cursor-pointer"
            >
              <Checkbox
                checked={form[key]}
                onCheckedChange={(v) =>
                  onUpdateForm(key, v === true)
                }
                disabled={busy}
              />
              {label}
            </label>
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
