"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import { AlertTriangle, CheckCircle2, ChevronRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { pyFetch } from "@/lib/pyapi";
import type { AnalysisJob } from "@/lib/types";

export function ProgressView({ jobId, onDone }: { jobId: string; onDone: (analysisId: number) => void }) {
  const { data: job } = useQuery({
    queryKey: ["analysis-job", jobId],
    queryFn: () => pyFetch<AnalysisJob>(`/api/v1/analyses/jobs/${jobId}`),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "done" || s === "error" ? false : 1200;
    },
  });

  React.useEffect(() => {
    if (job?.status === "done" && job.analysis_id) {
      const t = setTimeout(() => onDone(job.analysis_id as number), 900);
      return () => clearTimeout(t);
    }
  }, [job?.status, job?.analysis_id, onDone]);

  const pct = job?.progress ?? 0;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 lg:px-8">
      <h1 className="text-2xl font-bold tracking-tight">Running analysis…</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Real pipeline progress — each step below is updated by the backend as it completes.
      </p>

      <Card className="mt-6">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Overall progress
            </CardTitle>
            <span className="text-sm font-semibold text-primary">{Math.round(pct)}%</span>
          </div>
          <Progress value={pct} className="mt-2" />
        </CardHeader>
        <CardContent className="space-y-1.5 pt-2">
          {(job?.steps ?? []).map((step, i) => (
            <div key={step.key} className="flex items-start gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-accent/40">
              <div className="mt-0.5">
                {step.status === "done" ? (
                  <CheckCircle2 className="h-4.5 w-4.5 h-[18px] w-[18px] text-emerald-400" />
                ) : step.status === "running" ? (
                  <Loader2 className="h-[18px] w-[18px] animate-spin text-primary" />
                ) : (
                  <ChevronRight className={cn("h-[18px] w-[18px] text-muted-foreground/50", step.status === "error" && "text-rose-400")} />
                )}
              </div>
              <div className="min-w-0">
                <p className={cn(
                  "text-sm",
                  step.status === "pending" ? "text-muted-foreground" : "font-medium text-foreground",
                )}>
                  <span className="mr-1.5 text-xs text-muted-foreground">{i + 1}.</span>
                  {step.label}
                </p>
                {step.detail ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{step.detail}</p>
                ) : null}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {job?.status === "error" ? (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">Analysis failed</p>
            <p className="mt-1 text-xs opacity-90">{job.error}</p>
            <Button size="sm" variant="outline" className="mt-3" onClick={() => history.back()}>
              Go back
            </Button>
          </div>
        </div>
      ) : null}

      {job?.status === "done" ? (
        <p className="mt-4 text-center text-sm text-primary">Opening dashboard…</p>
      ) : null}
    </div>
  );
}
