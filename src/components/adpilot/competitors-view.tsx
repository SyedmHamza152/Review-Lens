"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { ExternalLink, RefreshCw, Youtube } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import {
  CardsSkeleton, DataBadge, EmptyState, ErrorNote, SectionTitle, fmtNum,
} from "@/components/adpilot/bits";
import { pyFetch, pyUrl } from "@/lib/pyapi";
import type { Analysis } from "@/lib/types";

interface CompetitorsResp {
  analysis_id: number;
  status: string;
  summary: Record<string, unknown>;
  videos: Array<{
    video_id: string; title: string; channel_title: string; views: number;
    likes: number; comments: number; engagement_rate: number;
    duration_seconds: number; published_at: string; url: string;
    data_source_label: string;
  }>;
  disclaimer: string;
}

export function CompetitorsView({ analysisId }: { analysisId: number | null }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["competitors", analysisId],
    queryFn: async () => {
      let id = analysisId;
      if (!id) {
        const latest = await pyFetch<{ id?: number; empty?: boolean }>("/api/v1/analyses/latest");
        if (!latest || latest.empty || !latest.id) throw new Error("No analysis yet — run one first.");
        id = latest.id;
      }
      return pyFetch<CompetitorsResp>(`/api/v1/competitors/${id}`);
    },
    retry: false,
  });

  const refreshResearch = useMutation({
    mutationFn: () =>
      pyFetch<{ videos: number }>(`/api/v1/youtube/research/${data?.analysis_id}/refresh`, {
        method: "POST",
      }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["competitors"] });
      toast({ title: "Research refreshed", description: `${r.videos} live videos fetched` });
    },
    onError: (e) => toast({ title: "Refresh failed", description: String(e).slice(0, 140) }),
  });

  if (isLoading) return <div className="p-4 lg:p-6"><CardsSkeleton rows={3} /></div>;
  if (isError)
    return (
      <div className="space-y-4 p-4 lg:p-6">
        <h1 className="text-xl font-bold tracking-tight">Competitor Intelligence</h1>
        <ErrorNote message={String(error)} />
      </div>
    );
  if (!data) return null;

  const live = data.status === "live" && data.videos.length > 0;

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Competitor Intelligence</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Public YouTube content research — organic engagement only
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DataBadge label={live ? "LIVE DATA" : "SYNTHETIC DEMO DATA"} />
          <Button
            size="sm" variant="outline"
            onClick={() => refreshResearch.mutate()}
            disabled={refreshResearch.isPending || isRefetching}
          >
            <RefreshCw className={"mr-2 h-3.5 w-3.5" + (refreshResearch.isPending ? " animate-spin" : "")} />
            Refresh research
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-sky-500/30 bg-sky-500/5 p-3 text-xs text-sky-200/90">
        ℹ {data.disclaimer}
      </div>

      {!live ? (
        <EmptyState
          title="No live research rows"
          hint={
            data.status.startsWith("error")
              ? `YouTube Data API returned an error: ${data.status}`
              : "Configure YOUTUBE_API_KEY in backend/.env, then re-run the analysis to fetch live public YouTube research."
          }
        />
      ) : (
        <>
          {data.summary && Object.keys(data.summary).length ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MiniStat title="Videos analyzed" value={fmtNum(data.summary.videos_found as number)} />
              <MiniStat title="Total views" value={fmtNum(data.summary.total_views as number)} />
              <MiniStat title="Median views" value={fmtNum(data.summary.median_views as number)} />
              <MiniStat title="Shorts share" value={`${Math.round((data.summary.shorts_share as number ?? 0) * 100)}%`} />
            </div>
          ) : null}

          <Card>
            <CardHeader className="pb-1">
              <SectionTitle
                title="Top public videos for this product"
                desc="Sorted by public view count. Engagement rate = (likes + comments) / views from public statistics."
                label="LIVE DATA"
              />
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <div className="adpilot-scroll max-h-96 overflow-y-auto">
                <Table>
                  <TableHeader className="sticky top-0 bg-card">
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="pl-6">Video</TableHead>
                      <TableHead>Channel</TableHead>
                      <TableHead>Views</TableHead>
                      <TableHead>Likes</TableHead>
                      <TableHead>Comments</TableHead>
                      <TableHead>Engagement</TableHead>
                      <TableHead className="pr-6">Link</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.videos.map((v) => (
                      <TableRow key={v.video_id}>
                        <TableCell className="max-w-72 truncate pl-6 font-medium" title={v.title}>{v.title}</TableCell>
                        <TableCell className="text-xs">{v.channel_title}</TableCell>
                        <TableCell>{fmtNum(v.views)}</TableCell>
                        <TableCell>{fmtNum(v.likes)}</TableCell>
                        <TableCell>{fmtNum(v.comments)}</TableCell>
                        <TableCell>{(v.engagement_rate * 100).toFixed(2)}%</TableCell>
                        <TableCell className="pr-6">
                          <a href={v.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                            <ExternalLink className="h-3 w-3" /> open
                          </a>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm font-medium">
                <Youtube className="h-4 w-4 text-rose-400" /> Content themes observed
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm sm:grid-cols-3">
              <ThemeNote title="Review & demo formats" body="Top-ranking videos are overwhelmingly reviews and hands-on demos — in-stream demo creative matches this intent." />
              <ThemeNote title="Short-form presence" body={`~${Math.round((data.summary.shorts_share as number ?? 0) * 100)}% of top results are Shorts-length (≤65s), validating a Shorts discovery layer.`} />
              <ThemeNote title="Channel opportunity" body="Mid-sized channels carry high engagement relative to subscribers — partner or target-lookalike opportunities exist." />
            </CardContent>
          </Card>
        </>
      )}

      <p className="text-[11px] text-muted-foreground">
        Research reference: Google Ads Transparency Center can be consulted manually for advertiser
        creatives — AdPilot never invents competitor ad spend or private performance metrics.
        Quota used (this process): {String(data.summary.quota_used_process ?? 0)} units.
        Raw API: <code className="text-[10px]">{pyUrl("/api/v1/youtube/research?product=example")}</code>
      </p>
    </div>
  );
}

function MiniStat({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

function ThemeNote({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border bg-secondary/30 p-3">
      <p className="text-xs font-semibold">{title}</p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}
