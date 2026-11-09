"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  CardsSkeleton, ChartTooltip, DataBadge, EmptyState, ErrorNote, SectionTitle, fmtMoney, fmtPct,
} from "@/components/adpilot/bits";
import { pyFetch } from "@/lib/pyapi";
import type { Analysis } from "@/lib/types";

const AGE_COLORS = ["#34d399", "#38bdf8", "#f59e0b", "#a78bfa", "#fb7185"];

export function AudienceView({ analysisId }: { analysisId: number | null }) {
  const { data: latest, isLoading } = useQuery({
    queryKey: ["audience-analysis", analysisId],
    queryFn: async () => {
      if (analysisId) return pyFetch<Analysis>(`/api/v1/analyses/${analysisId}`);
      const l = await pyFetch<Analysis & { empty?: boolean }>("/api/v1/analyses/latest");
      if (l.empty) throw new Error("No analysis yet");
      return l;
    },
    retry: false,
  });

  if (isLoading) return <div className="p-4 lg:p-6"><CardsSkeleton rows={3} /></div>;
  if (!latest)
    return (
      <div className="space-y-4 p-4 lg:p-6">
        <h1 className="text-xl font-bold tracking-tight">Audience Intelligence</h1>
        <EmptyState title="No analysis yet" hint="Run a product analysis to generate audience hypotheses." />
      </div>
    );

  const aud = latest.audience;
  const ageData = Object.entries(aud.age_weights ?? {}).map(([band, w]) => ({ band, weight: +(w * 100).toFixed(1) }));
  const genderData = Object.entries(aud.gender_skew ?? {}).map(([g, w]) => ({ g, weight: +(w * 100).toFixed(1) }));

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Audience Intelligence</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Inferred targeting hypotheses for <span className="text-foreground">{latest.product.name}</span> ·
            engine: {latest.inference_method}
          </p>
        </div>
        <DataBadge label="INFERENCE" />
      </div>

      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/90">
        ⚠ {aud.disclaimer}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Age-band hypotheses</CardTitle>
          </CardHeader>
          <CardContent className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ageData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" />
                <XAxis dataKey="band" tick={{ fill: "#7c8db0", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#1c2a44" }} />
                <YAxis tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} unit="%" width={40} />
                <ChartTooltip formatter={(v: number) => [`${v}%`, "weight"]} />
                <Bar dataKey="weight" radius={[4, 4, 0, 0]}>
                  {ageData.map((_, i) => <Cell key={i} fill={AGE_COLORS[i % AGE_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <SectionTitle title="Geographic priorities" desc={aud.geo?.note} />
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {(aud.geo?.priority_cities ?? []).map((c, i) => (
                <span key={c} className={"rounded-full border px-3 py-1.5 text-sm " + (i < 3 ? "border-primary/40 bg-primary/10 text-primary" : "text-muted-foreground")}>
                  {c}
                </span>
              ))}
            </div>
            <div className="mt-4 border-t pt-3">
              <p className="text-xs font-medium text-muted-foreground">Gender skew hypothesis</p>
              <div className="mt-2 flex h-3 overflow-hidden rounded-full">
                {genderData.map((g, i) => (
                  <div key={g.g} style={{ width: `${g.weight}%`, background: AGE_COLORS[i] }} title={`${g.g}: ${g.weight}%`} />
                ))}
              </div>
              <div className="mt-1.5 flex gap-4 text-xs text-muted-foreground">
                {genderData.map((g, i) => (
                  <span key={g.g}>{g.g}: {g.weight}%</span>
                ))}
              </div>
            </div>
            <div className="mt-4 border-t pt-3 text-xs text-muted-foreground">
              Est. average order value: <span className="text-foreground">{fmtMoney(aud.aov_estimate)}</span> ·
              purchase intent: <span className="text-foreground">{aud.intent}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Audience segments</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          {(aud.segments ?? []).map((s) => (
            <div key={s.key} className="rounded-lg border bg-secondary/30 p-4">
              <p className="text-sm font-semibold">{s.label}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">Ages {s.age_bands.join(", ")}</p>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{s.note}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(s.interests ?? []).map((i) => (
                  <span key={i} className="rounded-full border px-2 py-0.5 text-[10px] text-muted-foreground">{i}</span>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Interest &amp; content targeting signals</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {(aud.interests ?? []).map((i) => (
            <span key={i} className="rounded-full bg-secondary px-3 py-1.5 text-xs">{i}</span>
          ))}
        </CardContent>
      </Card>

      <p className="text-[11px] text-muted-foreground">
        Analysis confidence: {fmtPct(latest.confidence, 0)} · Segment data is stored per analysis for
        auditability ({latest.id}).
      </p>
    </div>
  );
}
