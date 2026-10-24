"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Report } from "@/lib/types";
import {
  AspectChart, LanguagePie, PlatformStackedBar, SentimentByLanguageBar,
  SentimentDonut, TrendLine, VolumeBar,
} from "./charts";
import { AlertTriangle, CheckCircle2, Gauge, Info, Languages, MessageSquare, ShieldCheck, Store, ThumbsDown, ThumbsUp, TrendingUp } from "lucide-react";

export function OverviewTab({ report }: { report: Report }) {
  const { verdict, totals, distribution, aspects, advantages, complaints } = report;
  const isSample = report.job.data_mode === "sample";
  const listings = report.marketplace_listings ?? [];

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
          value={`${verdict.score}`}
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
          icon={<ShieldCheck className="size-4" />}
          label="Platforms analyzed"
          value={`${totals.platforms_with_data}`}
          sub={`of ${totals.platforms_requested} requested`}
        />
      </div>

      {/* Marketplace rating snapshots (real storefront aggregates) */}
      {listings.length > 0 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Store className="size-4 text-primary" /> Marketplace rating snapshots
            </CardTitle>
            <p className="text-xs font-normal text-muted-foreground">
              Real product listings with the marketplace's own average rating and review
              counts, collected live from the storefront. These are platform-side counters —
              NOT our sentiment analysis and NOT part of the verdict score.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {listings.map((g) => (
              <div key={g.platform} className="space-y-2">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <Badge variant="outline" className="border-emerald-500/40 text-emerald-700">
                    {g.platform_name} · {g.listing_count} listings
                  </Badge>
                  {g.avg_rating !== null ? (
                    <span className="text-xs text-muted-foreground">
                      avg rating {g.avg_rating}/5 · {g.total_review_count.toLocaleString()} total ratings
                    </span>
                  ) : null}
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  {g.items.map((it, i) => (
                    <a key={i} href={it.url ?? "#"} target="_blank" rel="noreferrer"
                      className="rounded-md border px-3 py-2 text-xs transition-colors hover:bg-muted/50">
                      <p className="line-clamp-1 font-medium">{it.name}</p>
                      <p className="mt-0.5 text-muted-foreground">
                        {it.rating !== null ? `★ ${it.rating.toFixed(1)}` : "unrated"}
                        {" · "}{it.review_count.toLocaleString()} ratings
                        {it.price_text ? ` · ${it.price_text}` : ""}
                        {it.sold_count_text ? ` · ${it.sold_count_text}` : ""}
                      </p>
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

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
                · score {verdict.score}/100
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
            <CardTitle className="text-base">Platform sentiment comparison</CardTitle>
            <p className="text-xs font-normal text-muted-foreground">
              Sample sizes shown alongside - low-sample platforms are flagged in the comparison tab
            </p>
          </CardHeader>
          <CardContent>
            <PlatformStackedBar
              rows={report.comparison.map((c) => ({
                platform_name: c.platform_name + (c.low_sample ? "*" : ""),
                positive_pct: c.positive_pct,
                negative_pct: c.negative_pct,
                neutral_pct: c.neutral_pct,
                mixed_pct: c.mixed_pct,
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
