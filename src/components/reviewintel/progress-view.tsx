"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { pyFetch } from "@/lib/pyapi";
import type { JobStatus, PlatformStatus } from "@/lib/types";
import {
  AlertCircle, Ban, CheckCircle2, Clock, Eye, KeyRound, Loader2,
  PlugZap, ShieldAlert, Sparkles,
} from "lucide-react";

const STATUS_UI: Record<string, { icon: React.ReactNode; cls: string; label: string }> = {
  pending: { icon: <Clock className="size-4" />, cls: "text-muted-foreground", label: "Queued" },
  searching: { icon: <Loader2 className="size-4 animate-spin" />, cls: "text-primary", label: "Searching" },
  success: { icon: <CheckCircle2 className="size-4" />, cls: "text-emerald-600", label: "Live data" },
  success_sample: { icon: <Sparkles className="size-4" />, cls: "text-amber-600", label: "SAMPLE data" },
  no_results: { icon: <Eye className="size-4" />, cls: "text-muted-foreground", label: "No results" },
  needs_credentials: { icon: <KeyRound className="size-4" />, cls: "text-amber-600", label: "Needs API credentials" },
  blocked: { icon: <ShieldAlert className="size-4" />, cls: "text-red-500", label: "Access blocked" },
  unsupported: { icon: <Ban className="size-4" />, cls: "text-muted-foreground", label: "No authorized API" },
  error: { icon: <AlertCircle className="size-4" />, cls: "text-red-500", label: "Error" },
};

export function ProgressView({
  jobId,
  onOpenReport,
}: {
  jobId: string;
  onOpenReport: () => void;
}) {
  const { data } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => pyFetch<JobStatus>(`/api/jobs/${jobId}`),
    refetchInterval: (q) =>
      q.state.data?.status === "completed" || q.state.data?.status === "failed"
        ? false
        : 1200,
  });

  const done = data?.status === "completed" || data?.status === "failed";

  useEffect(() => {
    if (done) {
      const t = setTimeout(onOpenReport, 600);
      return () => clearTimeout(t);
    }
  }, [done, onOpenReport]);

  const completedCount = data?.platforms.filter(
    (p) => !["pending", "searching"].includes(p.status),
  ).length ?? 0;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <div className="mb-6 text-center">
        <h2 className="text-xl font-semibold sm:text-2xl">
          Analyzing “{data?.product_name ?? "..."}”
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Querying platforms, collecting available feedback and running the multilingual
          sentiment pipeline.
        </p>
      </div>

      <Card>
        <CardContent className="p-5 sm:p-6">
          {!data ? (
            <div className="space-y-3">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : (
            <div className="space-y-5">
              <div>
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 font-medium">
                    {!done ? <Loader2 className="size-4 animate-spin text-primary" /> : null}
                    {data.stage}
                  </span>
                  <span className="tabular-nums text-muted-foreground">{data.progress}%</span>
                </div>
                <Progress value={data.progress} />
                <p className="mt-2 text-xs text-muted-foreground">
                  {completedCount}/{data.platforms.length} platforms processed
                  {data.totals?.collected ? ` · ${data.totals.collected} items collected` : ""}
                </p>
              </div>

              <ul className="grid gap-2 sm:grid-cols-2">
                {data.platforms.map((p) => (
                  <PlatformRow key={p.platform} p={p} />
                ))}
              </ul>

              {data.status === "failed" ? (
                <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  Search failed: {data.error}
                </p>
              ) : null}

              {done ? (
                <Button onClick={onOpenReport} className="w-full sm:w-auto">
                  <PlugZap className="size-4" /> Open full report
                </Button>
              ) : null}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function PlatformRow({ p }: { p: PlatformStatus }) {
  const ui = STATUS_UI[p.status] ?? STATUS_UI.pending;
  return (
    <li className="flex items-start gap-3 rounded-lg border p-3">
      <span className={`mt-0.5 ${ui.cls}`}>{ui.icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{p.platform_name}</span>
          {p.is_sample ? (
            <Badge variant="outline" className="h-4 border-amber-500/40 px-1 text-[9px] text-amber-700">
              SAMPLE
            </Badge>
          ) : null}
          <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
            {p.items_collected > 0 ? `${p.items_collected} items` : ""}
          </span>
        </div>
        <p className="mt-0.5 line-clamp-2 text-xs leading-snug text-muted-foreground" title={p.message}>
          {ui.label}{p.message ? ` · ${p.message}` : ""}
        </p>
      </div>
    </li>
  );
}
