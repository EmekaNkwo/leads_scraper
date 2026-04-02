"use client";

import { MagnifyingGlass, Heart } from "@phosphor-icons/react";
import { useGetHealthQuery } from "@/lib/scraper-api";
import { Badge } from "@/components/ui/badge";

export function Header() {
  const { data: health } = useGetHealthQuery(undefined, {
    pollingInterval: 30000,
  });

  return (
    <header className="border-b bg-card px-6 py-4">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center rounded-md bg-primary p-2 text-primary-foreground">
            <MagnifyingGlass className="size-5" weight="bold" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight">
              Leads Scraper
            </h1>
            <p className="text-xs text-muted-foreground">
              Google Maps scraping pipeline
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {health ? (
            <Badge variant="outline" className="gap-1.5">
              <Heart className="size-3 text-green-500" weight="fill" />
              API v{health.version}
            </Badge>
          ) : (
            <Badge variant="destructive">API offline</Badge>
          )}
        </div>
      </div>
    </header>
  );
}
