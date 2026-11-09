"use client";

import * as React from "react";
import {
  Activity, BarChart3, Bot, CircuitBoard, Database, FileBarChart, LayoutDashboard,
  Menu, PieChart, Radio, Settings, Target, Users, X,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type ViewKey =
  | "dashboard" | "allocation" | "campaigns" | "audience" | "competitors"
  | "bigdata" | "ml" | "reports" | "settings";

export const NAV: Array<{ key: ViewKey; label: string; icon: React.ElementType; group: string }> = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, group: "Campaign" },
  { key: "allocation", label: "Budget Allocation", icon: PieChart, group: "Campaign" },
  { key: "campaigns", label: "Campaign Analytics", icon: BarChart3, group: "Campaign" },
  { key: "audience", label: "Audience Intelligence", icon: Users, group: "Intelligence" },
  { key: "competitors", label: "Competitor Research", icon: Target, group: "Intelligence" },
  { key: "bigdata", label: "Big Data Lab", icon: Database, group: "Labs" },
  { key: "ml", label: "ML Model Lab", icon: Bot, group: "Labs" },
  { key: "reports", label: "Reports", icon: FileBarChart, group: "Workspace" },
  { key: "settings", label: "Settings", icon: Settings, group: "Workspace" },
];

function NavList({
  current,
  onNewAnalysis,
  onNavigate,
  onAfterNavigate,
}: {
  current: ViewKey;
  onNewAnalysis: () => void;
  /** Called on click — navigates via the router so the view ALWAYS switches,
   *  even when the browser suppresses hashchange (e.g. same-hash edge cases). */
  onNavigate?: (key: ViewKey) => void;
  onAfterNavigate?: () => void;
}) {
  const groups = Array.from(new Set(NAV.map((n) => n.group)));
  return (
    <nav className="adpilot-scroll flex-1 space-y-4 overflow-y-auto px-3 pb-4">
      <button
        onClick={() => {
          onNewAnalysis();
          onAfterNavigate?.();
        }}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90"
      >
        <CircuitBoard className="h-4 w-4" /> New Analysis
      </button>
      {groups.map((g) => (
        <div key={g}>
          <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {g}
          </p>
          <div className="space-y-0.5">
            {NAV.filter((n) => n.group === g).map((n) => {
              const Icon = n.icon;
              const active = current === n.key;
              return (
                <a
                  key={n.key}
                  href={`#/${n.key}`}
                  onClick={(e) => {
                    // preventDefault + explicit navigation: identical result to
                    // native hash nav, but deterministic in every environment.
                    e.preventDefault();
                    if (onNavigate) onNavigate(n.key);
                    onAfterNavigate?.();
                  }}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                    active
                      ? "bg-accent font-medium text-foreground"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                  )}
                >
                  <Icon className={cn("h-4 w-4", active && "text-primary")} />
                  {n.label}
                </a>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function Sidebar({
  current,
  onNewAnalysis,
  onNavigate,
}: {
  current: ViewKey;
  onNewAnalysis: () => void;
  onNavigate?: (key: ViewKey) => void;
}) {
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r bg-sidebar md:flex">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <Radio className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-bold tracking-tight">AdPilot AI</p>
          <p className="text-[10px] text-muted-foreground">YouTube Budget Optimizer</p>
        </div>
      </div>
      {/* Navigation is driven by onNavigate (router) — the href stays for
          semantics and open-in-new-tab. */}
      <NavList current={current} onNewAnalysis={onNewAnalysis} onNavigate={onNavigate} />
      <div className="border-t px-5 py-3 text-[10px] leading-relaxed text-muted-foreground">
        Only YouTube inventory is supported:
        <br />In-Stream · Shorts · In-Feed
      </div>
    </aside>
  );
}

export function MobileNav({
  current,
  onNewAnalysis,
  onNavigate,
}: {
  current: ViewKey;
  onNewAnalysis: () => void;
  onNavigate?: (key: ViewKey) => void;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <>
      <button
        aria-label="Open navigation"
        onClick={() => setOpen(true)}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border bg-card text-foreground md:hidden"
      >
        <Menu className="h-4.5 w-4.5" />
      </button>
      {open ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="adpilot-scroll absolute left-0 top-0 flex h-full w-64 flex-col border-r bg-sidebar shadow-xl">
            <div className="flex items-center justify-between px-5 py-4">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
                  <Radio className="h-4 w-4" />
                </div>
                <p className="text-sm font-bold">AdPilot AI</p>
              </div>
              <button aria-label="Close navigation" onClick={() => setOpen(false)}>
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
            <NavList
              current={current}
              onNewAnalysis={onNewAnalysis}
              onNavigate={onNavigate}
              onAfterNavigate={() => setOpen(false)}
            />
            <div className="border-t px-5 py-3 text-[10px] leading-relaxed text-muted-foreground">
              Only YouTube inventory is supported:
              <br />In-Stream · Shorts · In-Feed
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}

export function Topbar({
  backendOk,
  productName,
  budgetLabel,
  onHome,
  mobileNav,
}: {
  backendOk: boolean;
  productName?: string;
  budgetLabel?: string;
  onHome: () => void;
  mobileNav?: React.ReactNode;
}) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur lg:px-6">
      {mobileNav}
      <a
        href="#"
        onClick={(e) => {
          e.preventDefault();
          onHome();
        }}
        className="flex items-center gap-2 md:hidden"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/15 text-primary">
          <Radio className="h-4 w-4" />
        </div>
        <span className="text-sm font-bold">AdPilot AI</span>
      </a>
      <div className="hidden min-w-0 flex-1 items-center gap-2 lg:flex">
        <Activity className="h-4 w-4 text-muted-foreground" />
        <span className="truncate text-sm text-muted-foreground">
          {productName ? (
            <>
              Active product: <span className="font-medium text-foreground">{productName}</span>
              {budgetLabel ? <span className="ml-1 text-xs">· {budgetLabel}</span> : null}
            </>
          ) : (
            "No active product — run an analysis to populate the workspace."
          )}
        </span>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <span className="hidden text-[11px] text-muted-foreground sm:inline">
          YouTube In-Stream · Shorts · In-Feed only
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
            backendOk
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
              : "border-amber-500/40 bg-amber-500/10 text-amber-300",
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", backendOk ? "bg-emerald-400" : "bg-amber-400 animate-pulse")} />
          {backendOk ? "Backend online" : "Starting backend…"}
        </span>
      </div>
    </header>
  );
}
