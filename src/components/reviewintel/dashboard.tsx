"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { exportUrl, pyFetch } from "@/lib/pyapi";
import type { BelowMinimumPlatform, JobStatus, Report } from "@/lib/types";
import { AssistantTab } from "./assistant-tab";
import { ComparisonTab } from "./comparison-tab";
import { ExplorerTab } from "./explorer-tab";
import { MethodologyTab } from "./methodology-tab";
import { OverviewTab } from "./overview-tab";
import { Bot, Download, FileSpreadsheet, RefreshCw, Scale } from "lucide-react";

export function DashboardView({ jobId }: { jobId: string }) {
  const [tab, setTab] = useState("overview");

  const { data: report, isLoading, error, refetch } = useQuery({
    queryKey: ["report", jobId],
    queryFn: () => pyFetch<Report>(`/api/jobs/${jobId}/report`),
    refetchInterval: (q) => (q.state.data ? false : 1500),
  });

  const { data: job } = useQuery({
    queryKey: ["job-lite", jobId],
    queryFn: () => pyFetch<JobStatus>(`/api/jobs/${jobId}`),
    refetchInterval: 5000,
  });

  if (isLoading || !report) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 px-4 py-8 sm:px-6">
        {error ? (
          <Card>
            <CardContent className="p-6 text-sm text-destructive">
              Failed to load report: {(error as Error).message}
              <Button variant="outline" size="sm" className="ml-3" onClick={() => refetch()}>
                <RefreshCw className="size-3.5" /> Retry
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <Skeleton className="h-8 w-72" />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
            </div>
            <Skeleton className="h-72" />
          </>
        )}
      </div>
    );
  }

  const v = report.verdict;
  const isSample = report.job.data_mode === "sample";

  return (
    <div className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6">
      {/* Report header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-xl font-bold tracking-tight sm:text-2xl">
              {report.job.product_name}
            </h2>
            <Badge
              variant="outline"
              className={v.label === "Insufficient Data"
                ? "border-slate-400/50 text-slate-600"
                : v.label.includes("Negative")
                  ? "border-red-500/40 text-red-600"
                  : v.label.includes("Mixed")
                    ? "border-amber-500/40 text-amber-600"
                    : "border-emerald-500/40 text-emerald-700"}
            >
              {v.label} · {v.score !== null ? `${v.score}/100` : "no score"}
            </Badge>
            {isSample ? (
              <Badge variant="outline" className="border-amber-500/40 text-amber-700">
                SAMPLE DATA MODE
              </Badge>
            ) : report.job.data_mode === "mixed" ? (
              <Badge variant="outline" className="border-teal-500/40 text-teal-700">
                LIVE + SAMPLE
              </Badge>
            ) : (
              <Badge variant="outline" className="border-emerald-500/40 text-emerald-700">
                LIVE DATA
              </Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {report.totals.analyzed} comments analyzed · {report.totals.analyzed_for_verdict ?? report.totals.analyzed} counted
            toward the verdict (platforms meeting the {report.totals.min_comments_required ?? 50}-comment minimum) ·
            searched {new Date(report.job.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <a href={exportUrl(jobId, "csv")} download>
            <Button variant="outline" size="sm">
              <FileSpreadsheet className="size-4" /> CSV
            </Button>
          </a>
          <a href={exportUrl(jobId, "pdf")} download>
            <Button variant="outline" size="sm">
              <Download className="size-4" /> PDF
            </Button>
          </a>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="h-auto w-full flex-wrap justify-start gap-0 sm:w-auto">
          <TabsTrigger value="overview" className="text-xs sm:text-sm">Overview</TabsTrigger>
          <TabsTrigger value="comparison" className="text-xs sm:text-sm">Platform comparison</TabsTrigger>
          <TabsTrigger value="explorer" className="text-xs sm:text-sm">Review explorer</TabsTrigger>
          <TabsTrigger value="assistant" className="text-xs sm:text-sm">
            <Bot className="mr-1 size-3.5" /> AI assistant
          </TabsTrigger>
          <TabsTrigger value="methodology" className="text-xs sm:text-sm">
            <Scale className="mr-1 size-3.5" /> Methodology
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <OverviewTab report={report} jobId={jobId} />
        </TabsContent>
        <TabsContent value="comparison" className="mt-4">
          <ComparisonTab report={report} />
        </TabsContent>
        <TabsContent value="explorer" className="mt-4">
          <ExplorerTab jobId={jobId} belowMinimum={report.below_minimum_platforms} />
        </TabsContent>
        <TabsContent value="assistant" className="mt-4">
          <AssistantTab jobId={jobId} report={report} />
        </TabsContent>
        <TabsContent value="methodology" className="mt-4">
          <MethodologyTab report={report} />
        </TabsContent>
      </Tabs>

      {/* live-collection status strip */}
      {job?.platforms.some((p) => ["needs_credentials", "blocked", "unsupported"].includes(p.status)) ? (
        <Card className="border-muted">
          <CardContent className="p-3 text-xs leading-relaxed text-muted-foreground">
            <b className="text-foreground/80">Integration status:</b>{" "}
            {job.platforms
              .filter((p) => ["needs_credentials", "blocked", "unsupported"].includes(p.status))
              .map((p) => `${p.platform_name} (${p.status.replace("_", " ")})`)
              .join(" · ")}
            . Configure API credentials in backend/.env to enable live collection for
            those platforms - see the Methodology tab.
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
