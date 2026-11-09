"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import {
  CardsSkeleton, DataBadge, EmptyState, ErrorNote, SectionTitle,
  fmtMoney, fmtNum, fmtPct,
} from "@/components/adpilot/bits";
import { pyFetch } from "@/lib/pyapi";
import type { Recommendation } from "@/lib/types";

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
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rec.allocations.map((a) => (
                  <TableRow key={a.format_key}>
                    <TableCell className="pl-6 font-medium">{a.label}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-secondary">
                          <div className="h-full rounded-full bg-primary" style={{ width: `${a.share * 100}%` }} />
                        </div>
                        {(a.share * 100).toFixed(0)}%
                      </div>
                    </TableCell>
                    <TableCell>{fmtMoney(a.amount, rec.currency)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {fmtNum(a.predicted.impressions)} impr · {fmtNum(a.predicted.clicks)} clicks ·{" "}
                      {fmtNum(a.predicted.conversions, 0)} conv · ROAS {a.predicted.roas ?? "—"}
                    </TableCell>
                    <TableCell>{fmtPct(a.confidence, 0)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

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
