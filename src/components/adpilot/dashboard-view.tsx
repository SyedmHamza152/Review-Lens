"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Pie, PieChart,
  ResponsiveContainer, XAxis, YAxis,
} from "recharts";
import { Eye, MousePointerClick, PlayCircle, ShoppingBag, Target, TrendingUp, Wallet, Youtube } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  CardsSkeleton, ChartTooltip, DataBadge, EmptyState, ErrorNote, SectionTitle, formatColor,
  fmtMoney, fmtNum, fmtPct,
} from "@/components/adpilot/bits";
import { pyFetch } from "@/lib/pyapi";
import type { Analysis, Recommendation } from "@/lib/types";

interface DashboardResp {
  empty?: boolean;
  message?: string;
  analysis_id?: number;
  product?: { name: string; budget: number; currency: string };
  objective?: string;
  category?: string;
  confidence?: number;
  data_source_label?: string;
  allocation?: Array<{ format_key: string; label: string; share: number; amount: number; confidence: number }>;
  predicted?: Recommendation["predicted_totals"];
  cold_start?: boolean;
  research?: {
    videos_found: number;
    total_views: number;
    median_views: number;
    shorts_share: number;
    avg_engagement_rate: number;
    top_channels: Array<{ channel_id: string; title: string; subscribers: number }>;
    is_live: boolean;
  };
}

export function DashboardView({ analysisId, backendOk }: { analysisId: number | null; backendOk: boolean }) {
  const { data: dash, isLoading, isError, error } = useQuery({
    queryKey: ["dashboard", analysisId],
    queryFn: () =>
      pyFetch<DashboardResp>(
        `/api/v1/dashboard${analysisId ? `?analysis_id=${analysisId}` : ""}`,
      ),
    enabled: backendOk,
    refetchInterval: 30_000,
  });

  const { data: analysis } = useQuery({
    queryKey: ["analysis", dash?.analysis_id],
    queryFn: () => pyFetch<Analysis>(`/api/v1/analyses/${dash?.analysis_id}`),
    enabled: !!dash?.analysis_id,
  });

  if (isLoading) {
    return (
      <div className="space-y-4 p-4 lg:p-6">
        <CardsSkeleton rows={4} />
        <CardsSkeleton rows={2} />
      </div>
    );
  }
  if (isError) return <div className="p-6"><ErrorNote message={String(error)} /></div>;
  if (!dash || dash.empty) {
    return (
      <div className="p-4 lg:p-6">
        <EmptyState
          title="No analysis yet"
          hint="Run your first product analysis — AdPilot will infer the audience, research YouTube live, predict performance and optimize the budget."
        />
      </div>
    );
  }

  const pt = dash.predicted;
  const hasPt = pt && Object.keys(pt).length > 0;
  const pieData = (dash.allocation ?? []).map((a) => ({ name: a.label, key: a.format_key, value: Math.round(a.amount) }));
  const funnelData = hasPt
    ? ([
        { stage: "Impressions", value: pt.impressions, fill: "#38bdf8" },
        { stage: "Video views", value: pt.video_views ?? 0, fill: "#34d399" },
        { stage: "Clicks", value: pt.clicks, fill: "#f59e0b" },
        { stage: "Conversions", value: pt.conversions, fill: "#a78bfa" },
      ] as const).filter((d) => Number(d.value) > 0)
    : [];
  const research = dash.research;
  const researchLive = !!research?.is_live && (research?.videos_found ?? 0) > 0;

  return (
    <div className="space-y-6 p-4 lg:p-6">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">{dash.product?.name}</h1>
          <p className="text-sm text-muted-foreground">
            {dash.category} · Objective: <span className="text-foreground">{dash.objective}</span>
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {dash.cold_start ? <DataBadge label="MODEL PREDICTION" /> : <DataBadge label={dash.data_source_label ?? "MODEL PREDICTION"} />}
        </div>
      </div>

      {/* KPI row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard title="Total budget" value={fmtMoney(dash.product?.budget, dash.product?.currency)} icon={<Wallet className="h-4 w-4" />} label="USER INPUT" />
        <KpiCard title="Predicted impressions" value={fmtNum(pt?.impressions)} sub="MODEL PREDICTION" icon={<Eye className="h-4 w-4" />} />
        <KpiCard title="Predicted clicks" value={fmtNum(pt?.clicks)} sub={`CTR ${fmtPctRaw(pt?.ctr)}`} icon={<MousePointerClick className="h-4 w-4" />} />
        <KpiCard title="Predicted conversions" value={fmtNum(pt?.conversions, 0)} sub={`CPA ${fmtMoney(pt?.cpa, dash.product?.currency)}`} icon={<ShoppingBag className="h-4 w-4" />} />
        <KpiCard title="Expected revenue" value={fmtMoney(pt?.revenue, dash.product?.currency)} icon={<TrendingUp className="h-4 w-4" />} />
        <KpiCard title="Predicted ROAS" value={pt?.roas != null ? `${pt.roas.toFixed(2)}×` : "—"} sub="revenue / cost" icon={<Target className="h-4 w-4" />} />
        <KpiCard title="Conversion rate" value={fmtPctRaw(pt?.conversion_rate)} sub="conversions / clicks" />
        <KpiCard title="Confidence" value={fmtPct((dash.confidence ?? 0) / 1, 0)} sub="analysis confidence" />
      </div>

      {/* allocation + funnel */}
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Budget split</CardTitle>
          </CardHeader>
          <CardContent>
            {pieData.length ? (
              <>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3} strokeWidth={0}>
                        {pieData.map((d) => (
                          <Cell key={d.key} fill={formatColor(d.key)} />
                        ))}
                      </Pie>
                      <ChartTooltip
                        formatter={(v: number, n: string) => [fmtMoney(v, dash.product?.currency), n]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-2 space-y-1.5">
                  {dash.allocation?.map((a) => (
                    <div key={a.format_key} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full" style={{ background: formatColor(a.format_key) }} />
                        {a.label}
                      </span>
                      <span className="font-medium">{(a.share * 100).toFixed(0)}% · {fmtMoney(a.amount, dash.product?.currency)}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <EmptyState title="No allocation" hint="The recommendation has not been generated yet." />
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Predicted funnel</CardTitle>
          </CardHeader>
          <CardContent>
            {funnelData.length ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={funnelData} layout="vertical" margin={{ left: 8, right: 28 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" horizontal={false} />
                    <XAxis type="number" tick={{ fill: "#7c8db0", fontSize: 11 }} axisLine={{ stroke: "#1c2a44" }} tickLine={false} tickFormatter={(v) => fmtNum(v)} />
                    <YAxis type="category" dataKey="stage" width={92} tick={{ fill: "#c3cfe6", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <ChartTooltip
                      formatter={(v: number) => [fmtNum(v, 1), "MODEL PREDICTION"]}
                      cursor={{ fill: "rgba(56,189,248,0.06)" }}
                    />
                    <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={34}>
                      {funnelData.map((d) => (
                        <Cell key={d.stage} fill={d.fill} />
                      ))}
                      <LabelList
                        dataKey="value"
                        position="right"
                        formatter={(v: number) => fmtNum(v)}
                        style={{ fill: "#c3cfe6", fontSize: 11 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState title="No predictions" />
            )}
            <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
              {(analysis?.suitable_formats ?? []).map((f) => (
                <span key={f.format_key} className="rounded-full border bg-secondary/50 px-2.5 py-1 text-[11px]">
                  {f.label}: <span className="text-primary">{f.verdict}</span>
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Live market signals — REAL public YouTube data for this product */}
      <Card>
        <CardHeader className="pb-1">
          <SectionTitle
            title="Live market signals"
            desc="Public YouTube content captured for this product by the live research step. These numbers move the optimizer's allocation — a Shorts-heavy, highly engaged niche shifts budget toward Shorts."
            label={researchLive ? "LIVE DATA" : "NO DATA"}
          />
        </CardHeader>
        <CardContent>
          {researchLive && research ? (
            <div className="grid gap-4 lg:grid-cols-4">
              <LiveStat icon={<PlayCircle className="h-4 w-4 text-sky-400" />} title="Videos found" value={fmtNum(research.videos_found)} />
              <LiveStat icon={<Eye className="h-4 w-4 text-emerald-400" />} title="Combined public views" value={fmtNum(research.total_views)} />
              <LiveStat icon={<Youtube className="h-4 w-4 text-rose-400" />} title="Shorts-length share" value={`${Math.round((research.shorts_share ?? 0) * 100)}%`} />
              <LiveStat
                icon={<TrendingUp className="h-4 w-4 text-amber-400" />}
                title="Median engagement"
                value={`${((research.avg_engagement_rate ?? 0) * 100).toFixed(2)}%`}
                sub="(likes + comments) / views"
              />
            </div>
          ) : (
            <EmptyState
              title="No live research rows yet"
              hint="Configure YOUTUBE_API_KEY in backend/.env and re-run the analysis — the niche signals above then feed the optimizer as LIVE DATA."
            />
          )}
        </CardContent>
      </Card>

      {analysis ? (
        <Card>
          <CardHeader className="pb-2">
            <SectionTitle
              title="Why this objective"
              desc={analysis.objective_rationale}
              label="INFERENCE"
            />
          </CardHeader>
          <CardContent className="grid gap-4 text-sm sm:grid-cols-3">
            <div>
              <p className="text-xs font-medium text-muted-foreground">Value proposition</p>
              <p className="mt-1 text-muted-foreground">{analysis.value_proposition}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Problems solved</p>
              <ul className="mt-1 list-disc pl-4 text-muted-foreground">
                {analysis.problems_solved.slice(0, 3).map((p) => <li key={p}>{p}</li>)}
              </ul>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Pipeline status</p>
              <div className="mt-1.5 flex flex-col items-start gap-1.5">
                <span className="text-xs text-muted-foreground">YouTube research: {analysis.youtube_research_status}</span>
                <span className="text-xs text-muted-foreground">Ads history: {analysis.ads_history_status}</span>
                <span className="text-xs text-muted-foreground">Inference: {analysis.inference_method}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function KpiCard({ title, value, sub, icon, label }: {
  title: string; value: React.ReactNode; sub?: string; icon?: React.ReactNode; label?: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">{title}</p>
        <span className="text-muted-foreground">{icon}</span>
      </div>
      <p className="mt-1.5 text-xl font-semibold tracking-tight">{value}</p>
      <div className="mt-1 flex items-center justify-between gap-2">
        {sub ? <p className="text-xs text-muted-foreground">{sub}</p> : <span />}
        {label ? <DataBadge label={label} /> : null}
      </div>
    </div>
  );
}

function LiveStat({ icon, title, value, sub }: { icon: React.ReactNode; title: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border bg-secondary/30 p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        {title}
      </div>
      <p className="mt-1 text-lg font-semibold">{value}</p>
      {sub ? <p className="text-[11px] text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

function fmtPctRaw(v: number | null | undefined) {
  return v == null ? "—" : `${v.toFixed(2)}%`;
}
