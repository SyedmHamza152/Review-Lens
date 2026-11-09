"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  CardsSkeleton, DataBadge, EmptyState, ErrorNote, SectionTitle,
  fmtMoney, fmtNum, fmtPctRaw,
} from "@/components/adpilot/bits";
import { pyFetch } from "@/lib/pyapi";
import type { Analytics } from "@/lib/types";

const TOOLTIP_STYLE = { background: "#0c1526", border: "1px solid #1c2a44", borderRadius: 8, fontSize: 12 };

export function CampaignsView() {
  const [days, setDays] = React.useState(90);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["analytics", days],
    queryFn: () => pyFetch<Analytics>(`/api/v1/campaigns/analytics?days=${days}`),
  });

  if (isLoading) return <div className="space-y-4 p-4 lg:p-6"><CardsSkeleton rows={2} /><CardsSkeleton rows={2} /></div>;
  if (isError) return <div className="p-6"><ErrorNote message={String(error)} /></div>;
  if (!data) return null;

  const hasData = data.data_source_label !== "NO DATA";
  const series = data.series.map((p) => ({
    date: p.date.slice(5),
    impressions: p.impressions,
    clicks: p.clicks,
    cost: Math.round(p.cost * 100) / 100,
    conversions: p.conversions,
    roas: p.roas,
  }));
  const fmtRows = data.by_format.map((f) => ({
    format_key: String(f.format_key),
    impressions: Number(f.impressions),
    clicks: Number(f.clicks),
    cost: Number(f.cost),
    roas: f.roas == null ? null : Number(f.roas),
    ctr: f.ctr == null ? null : Number(f.ctr),
    cpa: f.cpa == null ? null : Number(f.cpa),
  }));

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Campaign Analytics</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Historical YouTube campaign performance from the connected account
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DataBadge label={data.data_source_label} />
          {([30, 90, 180] as const).map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={
                "rounded-md border px-2.5 py-1 text-xs transition-colors " +
                (days === d ? "border-primary/50 bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")
              }
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {!hasData ? (
        <EmptyState
          title="No campaign history"
          hint="Connect a Google Ads account in Settings (or keep the labeled synthetic demo data) to populate this page."
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MiniStat title="Impressions" value={fmtNum(data.totals.impressions)} />
            <MiniStat title="Clicks" value={fmtNum(data.totals.clicks)} sub={`CTR ${fmtPctRaw(data.totals.ctr as number | null)}`} />
            <MiniStat title="Cost" value={fmtMoney(data.totals.cost as number)} sub={`CPC ${fmtMoney(data.totals.cpc as number, undefined, 2)}`} />
            <MiniStat title="ROAS" value={data.totals.roas != null ? `${Number(data.totals.roas).toFixed(2)}×` : "—"} sub={`Conversions ${fmtNum(data.totals.conversions, 0)}`} />
          </div>

          <Tabs defaultValue="trend">
            <TabsList>
              <TabsTrigger value="trend">Trend</TabsTrigger>
              <TabsTrigger value="formats">By format</TabsTrigger>
              <TabsTrigger value="table">Campaigns</TabsTrigger>
            </TabsList>

            <TabsContent value="trend">
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Daily impressions &amp; clicks</CardTitle></CardHeader>
                <CardContent className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={series}>
                      <defs>
                        <linearGradient id="imprFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
                          <stop offset="100%" stopColor="#38bdf8" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" />
                      <XAxis dataKey="date" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#1c2a44" }} minTickGap={28} />
                      <YAxis yAxisId="l" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => fmtNum(v)} width={56} />
                      <YAxis yAxisId="r" orientation="right" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => fmtNum(v)} width={48} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number, n) => [fmtNum(v, 1), String(n)]} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Area yAxisId="l" type="monotone" dataKey="impressions" name="Impressions" stroke="#38bdf8" strokeWidth={1.6} fill="url(#imprFill)" />
                      <Line yAxisId="r" type="monotone" dataKey="clicks" name="Clicks" stroke="#34d399" strokeWidth={1.8} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="formats">
              <Card>
                <CardHeader className="pb-2">
                  <SectionTitle title="Performance by format" label={data.data_source_label} />
                </CardHeader>
                <CardContent className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={fmtRows}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" />
                      <XAxis dataKey="format_key" tick={{ fill: "#7c8db0", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#1c2a44" }} />
                      <YAxis yAxisId="l" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => fmtNum(v)} width={56} />
                      <YAxis yAxisId="r" orientation="right" tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} width={44} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar yAxisId="l" dataKey="impressions" name="Impressions" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                      <Bar yAxisId="r" dataKey="roas" name="ROAS (×)" fill="#34d399" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="table">
              <Card>
                <CardContent className="px-0 pb-0">
                  <div className="adpilot-scroll max-h-96 overflow-y-auto">
                    <Table>
                      <TableHeader className="sticky top-0 bg-card">
                        <TableRow className="hover:bg-transparent">
                          <TableHead className="pl-6">Campaign</TableHead>
                          <TableHead>Format</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Impr.</TableHead>
                          <TableHead>Clicks</TableHead>
                          <TableHead>CTR</TableHead>
                          <TableHead>Cost</TableHead>
                          <TableHead>ROAS</TableHead>
                          <TableHead className="pr-6">Source</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.campaigns.map((c) => (
                          <TableRow key={c.campaign_id}>
                            <TableCell className="max-w-56 truncate pl-6 font-medium" title={c.name}>{c.name}</TableCell>
                            <TableCell className="text-xs">{c.format_key}</TableCell>
                            <TableCell className="text-xs">{c.status}</TableCell>
                            <TableCell>{fmtNum(c.metrics.impressions as number)}</TableCell>
                            <TableCell>{fmtNum(c.metrics.clicks as number)}</TableCell>
                            <TableCell>{fmtPctRaw(c.metrics.ctr as number | null)}</TableCell>
                            <TableCell>{fmtMoney(c.metrics.cost as number)}</TableCell>
                            <TableCell>{c.metrics.roas != null ? `${Number(c.metrics.roas).toFixed(2)}×` : "—"}</TableCell>
                            <TableCell className="pr-6"><DataBadge label={c.data_source_label} /></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}

function MiniStat({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
      {sub ? <p className="text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}
