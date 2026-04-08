"use client";

import { Sparkle, Spinner } from "@phosphor-icons/react";
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
import type { AgentRunRequest } from "@/types";

interface AgentRunFormProps {
  form: AgentRunRequest;
  isSubmitting: boolean;
  isRunning: boolean;
  errorMessage: string | null;
  onUpdateForm: <K extends keyof AgentRunRequest>(
    field: K,
    value: AgentRunRequest[K],
  ) => void;
  onSubmit: () => void;
}

export function AgentRunForm({
  form,
  isSubmitting,
  isRunning,
  errorMessage,
  onUpdateForm,
  onSubmit,
}: AgentRunFormProps) {
  const busy = isSubmitting || isRunning;
  const parseClampedNumber = (
    raw: string,
    fallback: number,
    min: number,
    max: number,
  ) => {
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }
    return Math.min(max, Math.max(min, Math.round(parsed)));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent Goal</CardTitle>
        <CardDescription>
          Describe the leads you want, then let the agent plan queries and rank
          the best matches.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="agentGoal">Goal</Label>
          <Textarea
            id="agentGoal"
            rows={5}
            placeholder="Find wholesale electronics suppliers in Ikeja with reachable websites"
            value={form.goal}
            onChange={(event) => onUpdateForm("goal", event.target.value)}
            disabled={busy}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="agentMaxQueries">Max planned queries</Label>
            <Input
              id="agentMaxQueries"
              type="number"
              min={1}
              max={10}
              value={form.max_queries}
              onChange={(event) =>
                onUpdateForm(
                  "max_queries",
                  parseClampedNumber(event.target.value, form.max_queries, 1, 10),
                )
              }
              disabled={busy}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="agentMaxResults">Max results per query</Label>
            <Input
              id="agentMaxResults"
              type="number"
              min={1}
              max={500}
              value={form.max_results_per_query}
              onChange={(event) =>
                onUpdateForm(
                  "max_results_per_query",
                  parseClampedNumber(
                    event.target.value,
                    form.max_results_per_query,
                    1,
                    500,
                  ),
                )
              }
              disabled={busy}
            />
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-2 gap-3 text-sm">
          {([
            ["headless", "Headless mode"],
            ["enrich_websites", "Website enrichment"],
            ["resume", "Resume checkpoints"],
          ] as const).map(([key, label]) => (
            <label key={key} className="flex cursor-pointer items-center gap-2">
              <Checkbox
                checked={form[key]}
                onCheckedChange={(value) => onUpdateForm(key, value === true)}
                disabled={busy}
              />
              {label}
            </label>
          ))}
        </div>

        {errorMessage && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {errorMessage}
          </p>
        )}

        <Button
          className="w-full"
          size="lg"
          onClick={onSubmit}
          disabled={busy || form.goal.trim().length === 0}
        >
          {busy ? (
            <>
              <Spinner className="animate-spin" data-icon="inline-start" />
              Running Agent...
            </>
          ) : (
            <>
              <Sparkle weight="fill" data-icon="inline-start" />
              Run Agent
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
