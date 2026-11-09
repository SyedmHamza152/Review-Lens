"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { RefreshCw, Timer } from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart,
  PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import {
  CardsSkeleton, DataBadge, EmptyState, ErrorNote, SectionTitle, formatColor,
  fmtMoney, fmtNum, fmtPct,
} from "@/components/adpilot/bits";
import { pyFetch } from "@/lib/pyapi";
import type { DurationPlan, Recommendation } from "@/lib/types";

const TOOLTIP_STYLE = { background: "#0c1526", border: "1px solid #1c2a44", borderRadius: 8, fontSize: 12 };
const CURVE_COLORS = ["#38bdf8", "#34d399", "#f59e0b"];

export function AllocationView({ analysisId }: { analysisId: number | null }) {
  const [strategy, setStrategy] = React.useState("balanced");
  const qc = useQueryClient();
  const { toast } = useToast();

  const { data: rec, isLoading, isError, error } = useQuery({
    queryKey: ["recommendation", analysisId],
    queryFn: () => {
      if (analysisId) return pyFetch<Recommendation>(`/api/v1/analyses/${analysisId}/recommendation`);
      return pyFetch<{ id?: number; empty?: boolean }>("/api/v1/analyses/latest").then((a) => {
        if (!a || a.empty || !a.id) throw new Error("No analysis yet — run one first.");
        return pyFetch<Recommendation>(`/api/v1/analyses/${a.id}/recommendation`);
      });
    },
    retry: false,
  });

  // Duration intelligence lives with the recommendation (same analysis context)
  const { data: plan } = useQuery({
    queryKey: ["durations", analysisId],
    queryFn: async () => {
      let id = analysisId;
      if (!id) {
        const l = await pyFetch<{ id?: number; empty?: boolean }>("/api/v1/analyses/latest");
        if (!l || l.empty || !l.id) throw new Error("No analysis yet");
        id = l.id;
      }
      return pyFetch<DurationPlan>(`/api/v1/analyses/${id}/durations`);
    },
    enabled: !!rec,
    retry: false,
  });

  const reopt = useMutation({
    mutationFn: (strategy: string) =>
      pyFetch<Recommendation>(`/api/v1/analyses/${rec?.analysis_id}/recommendation/reoptimize`, {
        method: "POST",
        body: JSON.stringify({ strategy }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recommendation"] });
      toast({ title: "Re-optimized", description: `Strategy: ${strategy}` });
    },
  });

  if (isLoading) return <div className="p-4 lg:p-6"><CardsSkeleton rows={3} /></div>;
  if (isError)
    return (
      <div className="space-y-4 p-4 lg:p-6">
        <h1 className="text-xl font-bold tracking-tight">Budget Allocation</h1>
        <EmptyState
          title="No recommendation available"
          hint={String(error).replace("Error: ", "")}
        />
      </div>
    );
  if (!rec) return null;

  const total = rec.allocations.reduce((s, a) => s + a.amount, 0);
  const utilities = (rec.optimizer_meta?.effective_utilities ?? {}) as Record<string, number>;
  const utilityData = Object.entries(utilities).map(([key, u]) => ({
    key,
    name: rec.allocations.find((a) => a.format_key === key)?.label ?? key,
    utility: Math.round(u * 1000) / 1000,
  }));

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Budget Allocation</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Total {fmtMoney(rec.total_budget, rec.currency)} → distributed across{" "}
            {rec.allocations.length} YouTube format{rec.allocations.length > 1 ? "s" : ""} ·{" "}
            {rec.algorithm}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={strategy} onValueChange={setStrategy}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="balanced">Balanced</SelectItem>
              <SelectItem value="performance">Performance</SelectItem>
              <SelectItem value="exploratory">Exploratory</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" disabled={reopt.isPending} onClick={() => reopt.mutate(strategy)}>
            <RefreshCw className={"mr-2 h-3.5 w-3.5" + (reopt.isPending ? " animate-spin" : "")} />
            Re-optimize
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <DataBadge label={rec.data_source_label} />
        {rec.cold_start ? (
          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-300">
            Cold-start strategy active — priors documented in methodology
          </span>
        ) : null}
        <span className="rounded-full border px-2.5 py-1 text-[11px] text-muted-foreground">
          Confidence: {fmtPct(rec.confidence, 0)}
        </span>
        <span className="rounded-full border px-2.5 py-1 text-[11px] text-muted-foreground">
          Sum check: {fmtMoney(total, rec.currency)} {Math.abs(total - rec.total_budget) < 0.01 ? "✓ exact" : "✗"}
        </span>
      </div>

      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="text-sm font-medium">Recommended allocation</CardTitle>
        </CardHeader>
        <CardContent className="px-0 pb-0">
          <div className="adpilot-scroll overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-6">Advertising format</TableHead>
                  <TableHead>Share</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Predicted perf.</TableHead>
                  <TableHead>Best duration</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rec.allocations.map((a) => {
                  const best = plan?.recommendations.find((r) => r.format_key === a.format_key)?.best;
                  return (
                    <TableRow key={a.format_key}>
                      <TableCell className="pl-6 font-medium">{a.label}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-secondary">
                            <div className="h-full rounded-full" style={{ width: `${a.share * 100}%`, background: formatColor(a.format_key) }} />
                          </div>
                          {(a.share * 100).toFixed(0)}%
                        </div>
                      </TableCell>
                      <TableCell>{fmtMoney(a.amount, rec.currency)}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {fmtNum(a.predicted.impressions)} impr · {fmtNum(a.predicted.clicks)} clicks ·{" "}
                        {fmtNum(a.predicted.conversions, 0)} conv · ROAS {a.predicted.roas ?? "—"}
                      </TableCell>
                      <TableCell>
                        {best ? (
                          <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[11px] text-sky-300">
                            <Timer className="h-3 w-3" /> {best.seconds_label}
                          </span>
                        ) : "—"}
                      </TableCell>
                      <TableCell>{fmtPct(a.confidence, 0)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* ---------------- fit decomposition + utility ---------------- */}
      <div className="grid gap-4 lg:grid-cols-2">
        {rec.allocations.some((a) => a.fit_factors) ? (
          <Card>
            <CardHeader className="pb-2">
              <SectionTitle
                title="Why each format scores the way it does"
                desc="Fit multipliers per format: audience age mix, selected objective, product category, and the live YouTube niche signal (1.0 = neutral)."
                label="MODEL PREDICTION"
              />
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={["audience", "objective", "category", "research"].map((dim) => ({
                  dim,
                  ...Object.fromEntries(
                    rec.allocations
                      .filter((a) => a.fit_factors)
                      .map((a) => [a.format_key, a.fit_factors![dim as keyof typeof a.fit_factors]]),
                  ),
                }))}>
                  <PolarGrid stroke="#1c2a44" />
                  <PolarAngleAxis dataKey="dim" tick={{ fill: "#7c8db0", fontSize: 11 }} />
                  <PolarRadiusAxis domain={[0.5, 1.5]} tick={{ fill: "#7c8db0", fontSize: 9 }} axisLine={false} />
                  {rec.allocations.filter((a) => a.fit_factors).map((a) => (
                    <Radar
                      key={a.format_key}
                      name={a.label}
                      dataKey={a.format_key}
                      stroke={formatColor(a.format_key)}
                      fill={formatColor(a.format_key)}
                      fillOpacity={0.15}
                      strokeWidth={2}
                    />
                  ))}
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </RadarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        ) : null}

        {utilityData.length ? (
          <Card>
            <CardHeader className="pb-2">
              <SectionTitle
                title="Objective-aligned utility per format"
                desc={`Value per currency unit the optimizer maximizes for “${rec.objective}” — views for attention goals, clicks for traffic, revenue for leads/sales.`}
                label="MODEL PREDICTION"
              />
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={utilityData} layout="vertical" margin={{ left: 8, right: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" horizontal={false} />
                  <XAxis type="number" tick={{ fill: "#7c8db0", fontSize: 10 }} axisLine={{ stroke: "#1c2a44" }} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={150} tick={{ fill: "#c3cfe6", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [v, "utility"]} cursor={{ fill: "rgba(56,189,248,0.06)" }} />
                  <Bar dataKey="utility" radius={[0, 6, 6, 0]} barSize={30}>
                    {utilityData.map((d) => (
                      <Cell key={d.key} fill={formatColor(d.key)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        ) : null}
      </div>

      {/* predicted outcomes: conversions vs ROAS */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Predicted outcomes per format</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rec.allocations.map((a) => ({
              name: a.label.replace("YouTube ", "").replace(" Ads", ""),
              conversions: a.predicted.conversions,
              roas: a.predicted.roas,
              key: a.format_key,
            }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" />
              <XAxis dataKey="name" tick={{ fill: "#7c8db0", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#1c2a44" }} />
              <YAxis yAxisId="l" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => fmtNum(v)} width={56} />
              <YAxis yAxisId="r" orientation="right" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} width={40} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar yAxisId="l" dataKey="conversions" name="Conversions (MODEL PREDICTION)" radius={[4, 4, 0, 0]}>
                {rec.allocations.map((a) => (
                  <Cell key={a.format_key} fill={formatColor(a.format_key)} />
                ))}
              </Bar>
              <Line yAxisId="r" type="monotone" dataKey="roas" name="ROAS (×)" stroke="#e879f9" strokeWidth={2} dot={{ r: 4 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* ---------------- Ad Duration Intelligence ---------------- */}
      {plan ? (
        <Card>
          <CardHeader className="pb-1">
            <SectionTitle
              title="Ad duration intelligence — how many seconds work best"
              desc={plan.methodology}
              label={plan.data_source_label}
              right={plan.overall_best ? (
                <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-right">
                  <p className="text-[10px] uppercase tracking-wide text-emerald-300/80">Best overall pick</p>
                  <p className="text-sm font-semibold text-emerald-200">
                    {plan.overall_best.seconds_label} · {plan.overall_best.format_label.replace("YouTube ", "")}
                  </p>
                </div>
              ) : undefined}
            />
          </CardHeader>
          <CardContent className="space-y-5">
            {/* per-format recommendation cards */}
            <div className="grid gap-4 md:grid-cols-3">
              {plan.recommendations.map((r) => (
                <div key={r.format_key} className="rounded-lg border bg-secondary/30 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold" style={{ color: formatColor(r.format_key) }}>
                      {r.format_label.replace("YouTube ", "")}
                    </p>
                    <span className="rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[11px] font-medium text-sky-300">
                      {r.best.seconds_label}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{r.best.label}</p>
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>Expected hold rate</span>
                      <span className="font-semibold text-foreground">{r.best.expected_hold_rate}%</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-secondary">
                      <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400" style={{ width: `${r.best.expected_hold_rate}%` }} />
                    </div>
                  </div>
                  <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{r.best.note}</p>
                  {r.best.live_adjustment ? (
                    <p className="mt-1.5 rounded border border-emerald-500/30 bg-emerald-500/5 px-2 py-1 text-[11px] text-emerald-300">
                      ✓ {r.best.live_adjustment}
                    </p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-1">
                    {r.alternatives.map((alt) => (
                      <span key={alt.duration_key} className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        alt: {alt.seconds_label} ({alt.expected_hold_rate}%)
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {plan.overall_best?.reason ? (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs leading-relaxed text-emerald-100/90">
                <span className="font-semibold">Recommendation: </span>{plan.overall_best.reason}
              </div>
            ) : null}

            <Tabs defaultValue="curves">
              <TabsList>
                <TabsTrigger value="curves">Attention curves</TabsTrigger>
                <TabsTrigger value="live">Live niche evidence</TabsTrigger>
              </TabsList>

              <TabsContent value="curves">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-sm font-medium">
                      <Timer className="h-4 w-4 text-sky-400" />
                      Predicted audience retention — % still watching at each second
                      <DataBadge label="MODEL PREDICTION" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" />
                        <XAxis
                          dataKey="t"
                          type="number"
                          domain={[0, "dataMax"]}
                          tick={{ fill: "#7c8db0", fontSize: 10 }}
                          tickLine={false}
                          axisLine={{ stroke: "#1c2a44" }}
                          tickFormatter={(t) => `${t}s`}
                          label={{ value: "seconds watched", position: "insideBottomRight", offset: -2, fill: "#7c8db0", fontSize: 10 }}
                        />
                        <YAxis domain={[0, 100]} tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} unit="%" width={48} />
                        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${v}%`, "still watching"]} labelFormatter={(t) => `t = ${t}s`} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        {plan.retention_curves.map((c, i) => {
                          const data = [...c.points];
                          if (data.length && data[data.length - 1].t < c.seconds) {
                            // extend to the full duration so curves end at their real length
                            data.push({ t: c.seconds, held: data[data.length - 1].held });
                          }
                          return (
                            <Line
                              key={c.duration_key}
                              data={data}
                              dataKey="held"
                              type="monotone"
                              name={c.label}
                              stroke={CURVE_COLORS[i % CURVE_COLORS.length]}
                              strokeWidth={2}
                              dot={false}
                            />
                          );
                        })}
                      </LineChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="live">
                {plan.live_research.label === "LIVE DATA" ? (
                  <div className="grid gap-4 lg:grid-cols-2">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">
                          Engagement by real video length
                          <DataBadge label="LIVE DATA" className="ml-2" />
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <ComposedChart data={plan.live_research.buckets.filter((b) => b.count > 0)}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" />
                            <XAxis dataKey="bucket" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#1c2a44" }} />
                            <YAxis yAxisId="l" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} width={40} allowDecimals={false} />
                            <YAxis yAxisId="r" orientation="right" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} width={48} unit="%" />
                            <Tooltip contentStyle={TOOLTIP_STYLE} />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Bar yAxisId="l" dataKey="count" name="videos found" fill="#38bdf8" radius={[4, 4, 0, 0]} barSize={26} />
                            <Line
                              yAxisId="r"
                              type="monotone"
                              dataKey={(row: { engagement_index: number | null }) =>
                                row.engagement_index == null ? null : Math.round((row.engagement_index - 1) * 1000) / 10}
                              name="engagement vs niche avg (%)"
                              stroke="#34d399"
                              strokeWidth={2}
                              dot={{ r: 4 }}
                            />
                          </ComposedChart>
                        </ResponsiveContainer>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">
                          Duration vs engagement — real public videos
                          <DataBadge label="LIVE DATA" className="ml-2" />
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <ScatterChart margin={{ top: 8, right: 16 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" />
                            <XAxis
                              type="number"
                              dataKey="seconds"
                              name="duration"
                              tick={{ fill: "#7c8db0", fontSize: 10 }}
                              tickLine={false}
                              axisLine={{ stroke: "#1c2a44" }}
                              tickFormatter={(s) => `${s}s`}
                            />
                            <YAxis
                              type="number"
                              dataKey="engagement_rate"
                              name="engagement"
                              tick={{ fill: "#7c8db0", fontSize: 10 }}
                              tickLine={false}
                              axisLine={false}
                              width={48}
                              unit="%"
                            />
                            <ZAxis type="number" dataKey="views" range={[30, 220]} name="views" />
                            <Tooltip
                              contentStyle={TOOLTIP_STYLE}
                              formatter={(v: number, n) => [n === "engagement" ? `${v}%` : fmtNum(v), String(n)]}
                              labelFormatter={() => ""}
                            />
                            <Scatter data={plan.live_research.scatter} fill="#38bdf8" fillOpacity={0.55} />
                          </ScatterChart>
                        </ResponsiveContainer>
                        <p className="mt-2 text-[11px] text-muted-foreground">
                          {plan.live_research.note} Bubble size = public views ({plan.live_research.videos_used} videos).
                        </p>
                      </CardContent>
                    </Card>
                  </div>
                ) : (
                  <EmptyState
                    title="No live duration evidence yet"
                    hint={plan.live_research.note}
                  />
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="pb-1">
          <SectionTitle
            title="Why this allocation"
            desc="Every allocation cites its evidence: funnel rates, history sample size, fit multipliers and the exploration bonus."
            label="MODEL PREDICTION"
          />
        </CardHeader>
        <CardContent className="space-y-3">
          {rec.allocations.map((a) => (
            <div key={a.format_key} className="rounded-lg border bg-secondary/30 p-3">
              <p className="text-sm font-semibold">
                {a.label} — {(a.share * 100).toFixed(0)}% ({fmtMoney(a.amount, rec.currency)})
              </p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{a.reason}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-1">
          <SectionTitle title="Methodology" desc={rec.methodology} />
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          <p>Predicted totals: {fmtNum(rec.predicted_totals.impressions)} impressions ·{" "}
            {fmtNum(rec.predicted_totals.clicks)} clicks · {fmtNum(rec.predicted_totals.conversions, 0)} conversions ·{" "}
            {fmtMoney(rec.predicted_totals.revenue, rec.currency)} revenue · ROAS {rec.predicted_totals.roas ?? "—"}</p>
          <p className="mt-2">
            Algorithm: {rec.algorithm} · Generated {new Date(rec.created_at).toLocaleString()}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
