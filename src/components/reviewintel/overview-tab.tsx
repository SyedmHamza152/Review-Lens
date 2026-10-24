"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { pyFetch } from "@/lib/pyapi";
import type { PaginatedReviews, Report } from "@/lib/types";
import {
  AspectChart, LanguagePie, PlatformStackedBar, SentimentByLanguageBar,
  SentimentDonut, TrendLine, VolumeBar,
} from "./charts";
import { AlertTriangle, CheckCircle2, ExternalLink, Gauge, Info, Languages, MessageSquare, ShieldCheck, ThumbsDown, ThumbsUp, TrendingUp, Youtube } from "lucide-react";

export function OverviewTab({ report, jobId }: { report: Report; jobId: string }) {
  const { verdict, totals, distribution, aspects, advantages, complaints } = report;
  const isSample = report.job.data_mode === "sample";
  const videos = report.source_videos ?? [];

  // real collected comments preview (transparency: comments visible up front)
  const { data: preview } = useQuery({
    queryKey: ["comment-preview", jobId],
    queryFn: () => pyFetch<PaginatedReviews>(
      `/api/jobs/${jobId}/reviews?page=1&page_size=8&sort=relevance&include_flagged=false`),
    staleTime: 60_000,
  });

  return (
    <div className="space-y-6">
      {isSample ? (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
          <p>
            <b>Sample data mode.</b> This is a legacy demonstration job built on the
            clearly-labelled synthetic sample corpus. New searches collect live data
            from platform APIs only.
          </p>
        </div>
      ) : (
        <div className="flex items-start gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" />
          <p>
            <b>Live data.</b> All reviews and comments in this report were collected
            directly from platform APIs at analysis time — no synthetic or demo data is
            included. Sources that could not be accessed are listed with their exact
            status below.
          </p>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Gauge className="size-4" />}
          label="Overall sentiment score"
          value={verdict.score !== null ? `${verdict.score}` : "—"}
          sub={`/100 · ${verdict.label}`}
        />
        <StatCard
          icon={<MessageSquare className="size-4" />}
          label="Unique reviews analyzed"
          value={`${totals.analyzed}`}
          sub={`${totals.collected} collected · ${totals.spam_filtered} spam filtered`}
        />
        <StatCard
          icon={<ThumbsUp className="size-4" />}
          label="Positive feedback"
          value={`${verdict.positive_pct}%`}
          sub={`negative ${verdict.negative_pct}% · mixed ${verdict.mixed_pct}%`}
          tone="pos"
        />
        <StatCard
          icon={<Youtube className="size-4" />}
          label="Source videos"
          value={`${videos.length}`}
          sub={`YouTube review videos · every comment links to its video`}
        />
      </div>

      {/* Source videos — where the comments came from */}
      {videos.length > 0 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Youtube className="size-4 text-primary" /> Source videos
            </CardTitle>
            <p className="text-xs font-normal text-muted-foreground">
              The YouTube review videos the comments were collected from. Titles link
              straight to the video on YouTube.
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 md:grid-cols-2">
              {videos.map((v) => (
                <a key={v.video_id} href={v.url} target="_blank" rel="noreferrer"
                  className="rounded-md border px-3 py-2 text-xs transition-colors hover:bg-muted/50">
                  <p className="line-clamp-1 font-medium">{v.title}</p>
                  <p className="mt-0.5 text-muted-foreground">
                    {v.channel ? `${v.channel} · ` : ""}
                    {v.comments_analyzed} comment{v.comments_analyzed === 1 ? "" : "s"} analyzed
                    {v.views_text ? ` · ${v.views_text}` : ""}
                  </p>
                  <p className="mt-1 inline-flex items-center gap-0.5 text-primary">
                    watch source <ExternalLink className="size-2.5" />
                  </p>
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Real collected comments — always visible, straight from the platforms */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="size-4 text-primary" /> Real comments collected
          </CardTitle>
          <p className="text-xs font-normal text-muted-foreground">
            A sample of the actual comments/reviews collected from platform APIs. Open the
            Review explorer tab for the full searchable list with filters.
          </p>
        </CardHeader>
        <CardContent>
          {!preview ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
            </div>
          ) : preview.total === 0 ? (
            <p className="text-sm text-muted-foreground">
              No comments matched this product on YouTube — try a more common
              product name or a slightly broader spelling.
            </p>
          ) : (
            <div className="grid gap-2 md:grid-cols-2">
              {preview.items.map((r) => (
                <div key={r.id} className="rounded-md border px-3 py-2">
                  <p className="line-clamp-3 text-sm leading-snug" dir="auto">{r.text_original}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <Badge variant="outline" className="h-4.5 px-1 text-[9px] font-medium">
                      {r.platform_name}
                    </Badge>
                    <span className={`rounded-full border px-1.5 text-[9px] font-semibold uppercase ${
                      r.sentiment === "positive" ? "border-emerald-500/40 text-emerald-700"
                      : r.sentiment === "negative" ? "border-red-500/40 text-red-600"
                      : r.sentiment === "mixed" ? "border-amber-500/40 text-amber-700"
                      : "border-slate-400/40 text-slate-600"}`}>
                      {r.sentiment}
                    </span>
                    {r.variant ? <span className="line-clamp-1 max-w-48">{r.variant}</span> : null}
                    {r.source_url ? (
                      <a href={r.source_url} target="_blank" rel="noreferrer"
                        className="inline-flex items-center gap-0.5 text-primary hover:underline">
                        video <ExternalLink className="size-2.5" />
                      </a>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Verdict + donut */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="size-4 text-primary" /> Overall verdict
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-lg font-semibold">
              {verdict.label}{" "}
              <span className="font-normal text-muted-foreground">
                {verdict.score !== null ? `· score ${verdict.score}/100` : "· no score (insufficient data)"}
              </span>
            </p>
            <div className="space-y-2">
              {distribution.map((d) => (
                <div key={d.label} className="flex items-center gap-3 text-sm">
                  <span className="w-16 capitalize text-muted-foreground">{d.label}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={d.pct} aria-label={`${d.label} ${d.pct}%`}>
                    <div className="h-full rounded-full transition-all" style={{ width: `${d.pct}%`, background: SENTIM_HEX[d.label] }} />
                  </div>
                  <span className="w-14 text-right tabular-nums text-muted-foreground">
                    {d.pct}% · {d.count}
                  </span>
                </div>
              ))}
            </div>
            <Separator />
            <p className="text-sm leading-relaxed text-muted-foreground">
              <Info className="mr-1 inline size-3.5" />
              {report.summary}
            </p>
            <p className="text-xs text-muted-foreground/80">{verdict.methodology_note}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-0">
            <CardTitle className="text-base">Sentiment distribution</CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            <SentimentDonut data={distribution} />
            <div className="mt-2 flex justify-center gap-3 text-xs">
              {(["positive", "negative", "mixed", "neutral"] as const).map((l) => (
                <span key={l} className="flex items-center gap-1.5">
                  <span aria-hidden className="size-2.5 rounded-full" style={{ background: SENTIM_HEX[l] }} />
                  <span className="capitalize text-muted-foreground">{l}</span>
                </span>
              ))}
            </div>
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Avg. analysis confidence: {(verdict.avg_confidence * 100).toFixed(0)}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Advantages / complaints */}
      <div className="grid gap-4 md:grid-cols-2">
        <AdvantageList
          title="Most mentioned advantages"
          icon={<ThumbsUp className="size-4 text-emerald-600" />}
          items={advantages.map((a) => ({ phrase: a.phrase, count: a.count, detail: a.detail }))}
          empty="No clear advantages detected in the collected sample."
        />
        <AdvantageList
          title="Most mentioned complaints"
          icon={<ThumbsDown className="size-4 text-red-500" />}
          items={complaints.map((c) => ({ phrase: c.phrase, count: c.count, detail: c.detail }))}
          empty="No recurring complaints detected in the collected sample."
        />
      </div>

      {/* Charts grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Aspect-based sentiment</CardTitle>
            <p className="text-xs font-normal text-muted-foreground">
              Positive vs negative mentions per product aspect (seller/marketplace aspects included)
            </p>
          </CardHeader>
          <CardContent>
            <AspectChart aspects={aspects} />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {aspects.slice(0, 6).map((a) => (
                <Tooltip key={a.aspect}>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="text-[10px] font-normal">
                      {a.scope === "product" ? "📦" : a.scope === "seller" ? "🏬" : "🚚"} {a.label} · {a.mentions}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent className="text-xs">
                    {a.positive} positive · {a.negative} negative · avg polarity {a.avg_polarity}
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Languages className="size-4 text-primary" /> Language distribution
            </CardTitle>
            <p className="text-xs font-normal text-muted-foreground">
              Detected comment languages across the sample
            </p>
          </CardHeader>
          <CardContent>
            <LanguagePie data={report.languages} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Sentiment by language</CardTitle>
          </CardHeader>
          <CardContent>
            <SentimentByLanguageBar data={report.languages} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Review volume by platform</CardTitle>
          </CardHeader>
          <CardContent>
            <VolumeBar
              rows={report.comparison.map((c) => ({ name: c.platform_name, count: c.total }))}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Sentiment comparison</CardTitle>
            <p className="text-xs font-normal text-muted-foreground">
              Positive / negative / neutral / mixed shares of the analyzed sample
            </p>
          </CardHeader>
          <CardContent>
            <PlatformStackedBar
              rows={report.comparison
                .map((c) => ({
                  platform_name: c.platform_name,
                  positive_pct: c.positive_pct ?? 0,
                  negative_pct: c.negative_pct ?? 0,
                  neutral_pct: c.neutral_pct ?? 0,
                  mixed_pct: c.mixed_pct ?? 0,
                }))}
              height={300}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Sentiment trend over time</CardTitle>
            <p className="text-xs font-normal text-muted-foreground">
              Weekly average score (-1..1) where review dates are available
            </p>
          </CardHeader>
          <CardContent>
            <TrendLine data={report.trends} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

const SENTIM_HEX: Record<string, string> = {
  positive: "#10b981",
  negative: "#ef4444",
  mixed: "#f59e0b",
  neutral: "#94a3b8",
};

function StatCard({ icon, label, value, sub, tone }: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  tone?: "pos";
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <span className={tone === "pos" ? "text-emerald-600" : "text-primary"}>{icon}</span>
          {label}
        </div>
        <p className="mt-2 text-2xl font-bold tabular-nums">{value}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
      </CardContent>
    </Card>
  );
}

function AdvantageList({ title, icon, items, empty }: {
  title: string;
  icon: React.ReactNode;
  items: { phrase: string; count: number; detail: string }[];
  empty: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">{icon} {title}</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul className="space-y-2">
            {items.map((it) => (
              <li key={it.phrase} className="flex items-start gap-2 text-sm">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600/70" />
                <span className="capitalize">{it.phrase}</span>
                <Badge variant="secondary" className="ml-auto shrink-0 text-[10px] tabular-nums">
                  {it.count}×
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
