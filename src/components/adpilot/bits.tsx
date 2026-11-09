"use client";

import * as React from "react";
import { AlertTriangle, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

/* ------------------------------------------------------------------ labels */
const LABEL_STYLES: Record<string, string> = {
  "LIVE DATA": "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  "SYNTHETIC DEMO DATA": "bg-amber-500/15 text-amber-300 border-amber-500/40",
  "MODEL PREDICTION": "bg-violet-500/15 text-violet-300 border-violet-500/40",
  INFERENCE: "bg-slate-500/15 text-slate-300 border-slate-400/40",
  "USER INPUT": "bg-sky-500/15 text-sky-300 border-sky-500/40",
};

export function DataBadge({ label, className }: { label: string; className?: string }) {
  const style = LABEL_STYLES[label] ?? "bg-slate-500/15 text-slate-300 border-slate-400/40";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase",
        style,
        className,
      )}
      title={`Source classification: ${label}`}
    >
      {label}
    </span>
  );
}

/* ------------------------------------------------------- format constants */
export const FORMAT_COLORS: Record<string, string> = {
  in_stream: "#38bdf8",   // sky
  shorts: "#34d399",      // emerald
  in_feed: "#f59e0b",     // amber
};

export const FORMAT_SHORT: Record<string, string> = {
  in_stream: "In-Stream",
  shorts: "Shorts",
  in_feed: "In-Feed",
};

export function formatColor(key: string): string {
  return FORMAT_COLORS[key] ?? "#a78bfa";
}

/* --------------------------------------------------------------- formatters */
export function fmtMoney(v: number | null | undefined, currency = "PKR", digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${currency} ${Number(v).toLocaleString("en-US", { maximumFractionDigits: digits })}`;
}

export function fmtNum(v: number | null | undefined, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function fmtPct(v: number | null | undefined, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtPctRaw(v: number | null | undefined, digits = 2) {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(digits)}%`;
}

/* ---------------------------------------------------------------- stat card */
export function StatCard({
  title,
  value,
  sub,
  icon,
  label,
  accent,
}: {
  title: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon?: React.ReactNode;
  label?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{title}</p>
        {icon ? <span className={cn("text-muted-foreground", accent)}>{icon}</span> : null}
      </div>
      <div className="mt-1.5 text-xl font-semibold tracking-tight">{value}</div>
      {sub ? <div className="mt-1 text-xs text-muted-foreground">{sub}</div> : null}
      {label ? <div className="mt-2"><DataBadge label={label} /></div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------- states */
export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed p-10 text-center">
      <Inbox className="h-8 w-8 text-muted-foreground" />
      <p className="font-medium">{title}</p>
      {hint ? <p className="max-w-md text-sm text-muted-foreground">{hint}</p> : null}
      {action}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function CardsSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-xl" />
      ))}
    </div>
  );
}

export function SectionTitle({
  title,
  desc,
  right,
  label,
}: {
  title: string;
  desc?: string;
  right?: React.ReactNode;
  label?: string;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold tracking-tight">{title}</h2>
          {label ? <DataBadge label={label} /> : null}
        </div>
        {desc ? <p className="mt-0.5 max-w-2xl text-xs text-muted-foreground">{desc}</p> : null}
      </div>
      {right}
    </div>
  );
}
