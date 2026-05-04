"use client";

import { useCallback, useSyncExternalStore } from "react";
import { Moon, Sun } from "@phosphor-icons/react";
import {
  useGetDedupeStatusQuery,
  useGetHealthQuery,
} from "@/lib/scraper-api";
import { cn } from "@/lib/utils";

type Theme = "dark" | "light";

const themeListeners = new Set<() => void>();
function subscribeTheme(cb: () => void) {
  themeListeners.add(cb);
  return () => {
    themeListeners.delete(cb);
  };
}
function getTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.classList.contains("light")
    ? "light"
    : "dark";
}
function getServerTheme(): Theme {
  return "dark";
}
function applyTheme(next: Theme) {
  document.documentElement.classList.toggle("light", next === "light");
  document.documentElement.classList.toggle("dark", next === "dark");
  try {
    window.localStorage.setItem("ls.theme", next);
  } catch {
    // noop — storage may be blocked
  }
  themeListeners.forEach((l) => l());
}

interface TopTapeProps {
  runState: {
    label: string;
    tone: "idle" | "running" | "done" | "error";
  };
}

export function TopTape({ runState }: TopTapeProps) {
  const { data: health } = useGetHealthQuery(undefined, {
    pollingInterval: 30000,
  });
  const { data: dedupeStatus } = useGetDedupeStatusQuery(undefined, {
    pollingInterval: 30000,
  });

  const theme = useSyncExternalStore(subscribeTheme, getTheme, getServerTheme);

  const toggleTheme = useCallback(() => {
    applyTheme(theme === "dark" ? "light" : "dark");
  }, [theme]);

  const toneDotPlain =
    runState.tone === "error"
      ? "bg-destructive"
      : runState.tone === "done"
        ? "bg-success"
        : "bg-muted-foreground/60";

  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/85 backdrop-blur-sm">
      <div className="mx-auto flex h-12 max-w-[1320px] items-center gap-4 px-5 sm:px-8">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="flex size-6 items-center justify-center rounded-[2px] bg-primary/10 ring-1 ring-primary/30"
          >
            <span className="size-1.5 bg-primary" />
          </span>
          <span className="text-base font-semibold leading-none tracking-tight">
            leads<span className="text-muted-foreground">/</span>scraper
          </span>
          <span className="hidden h-3 w-px bg-border sm:block" />
          <span className="hidden text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground sm:inline">
            Console
          </span>
        </div>

        <div className="hairline mx-2 hidden flex-1 md:block" />

        <div className="flex flex-1 items-center justify-center md:flex-none">
          <span className="inline-flex items-center gap-1.5 rounded-[2px] border border-border/60 px-2 py-0.5 text-[11px] text-foreground/85 transition-colors duration-150">
            <span
              className={cn(
                "size-1.5 shrink-0 rounded-full",
                runState.tone === "running"
                  ? cn("bg-primary pulse-soft")
                  : toneDotPlain,
              )}
            />
            {runState.label}
          </span>
        </div>

        <div className="hairline mx-2 hidden flex-1 md:block" />

        <div className="hidden items-center gap-5 md:flex">
          <span className="inline-flex items-center gap-3 font-mono text-[11px] text-foreground/85">
            <span>{dedupeStatus ? `${dedupeStatus.alias_count.toLocaleString()} keys` : "—"}</span>
            <span className="text-muted-foreground/50">/</span>
            <span className="inline-flex items-center gap-1.5">
              <span
                aria-hidden
                className={cn(
                  "size-1 shrink-0 rounded-full",
                  health ? "bg-success" : "bg-destructive",
                )}
              />
              <span>{health ? `v${health.version}` : "offline"}</span>
            </span>
          </span>

          <button
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            className="flex size-8 items-center justify-center text-muted-foreground transition-colors duration-150 hover:text-foreground"
          >
            {theme === "dark" ? (
              <Sun className="size-4" weight="regular" />
            ) : (
              <Moon className="size-4" weight="regular" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
