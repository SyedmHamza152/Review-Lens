"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import * as React from "react";
import { Bot, Cpu, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { CardsSkeleton, DataBadge, ErrorNote, SectionTitle, fmtNum } from "@/components/adpilot/bits";
import { pyFetch } from "@/lib/pyapi";
import type { MlModels } from "@/lib/types";

const OBJECTIVES = ["Brand Awareness", "Video Views", "Website Traffic", "Leads", "Sales / Conversions"];
const FORMATS = [
  { key: "in_stream", label: "In-Stream" },
  { key: "shorts", label: "Shorts" },
  { key: "in_feed", label: "In-Feed" },
];
const CATEGORIES = ["general", "sports_equipment", "electronics", "fashion_apparel", "education_courses"];

export function MlLabView() {
  const { toast } = useToast();
  const [format, setFormat] = React.useState("in_stream");
  const [objective, setObjective] = React.useState("Sales / Conversions");
  const [category, setCategory] = React.useState("general");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["ml-models"],
    queryFn: () => pyFetch<MlModels>("/api/v1/ml/models"),
    refetchInterval: 5000,
  });

  const predict = useQuery({
    queryKey: ["ml-predict", format, objective, category],
    queryFn: () =>
      pyFetch<{ predictions: Record<string, { value: number; model: string }> }>("/api/v1/ml/predict", {
        method: "POST",
        body: JSON.stringify({ format_key: format, objective, category_key: category }),
      }),
    retry: false,
  });

  const train = useMutation({
    mutationFn: () => pyFetch<{ status: string }>("/api/v1/ml/train", { method: "POST" }),
    onSuccess: () => {
      toast({ title: "Retraining queued", description: "Poll the model table — it updates when finished." });
      setTimeout(() => refetch(), 4000);
    },
  });

  if (isLoading) return <div className="p-4 lg:p-6"><CardsSkeleton rows={3} /></div>;
  if (isError) return <div className="p-6"><ErrorNote message={String(error)} /></div>;
  if (!data) return null;

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">ML Model Lab</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Candidate models compared per target with MAE / RMSE / R² on a chronological 80/20 split
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DataBadge label={`TRAINED ON ${data.trained_on.toUpperCase()}`} />
          <Button size="sm" variant="outline" disabled={train.isPending} onClick={() => train.mutate()}>
            <Play className={"mr-2 h-3.5 w-3.5" + (train.isPending ? " animate-pulse" : "")} />
            Retrain (100k)
          </Button>
        </div>
      </div>

      {!data.available ? (
        <ErrorNote message="No trained models yet — click Retrain and AdPilot prepares the training dataset and runs all candidate models automatically." />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-card p-3 text-xs text-muted-foreground">
            <Bot className="h-3.5 w-3.5 text-primary" />
            {data.rows_train?.toLocaleString()} train / {data.rows_test?.toLocaleString()} test rows ·
            features: ad_format, objective, category, budget_share, audience age index, mobile share, month, weekday ·
            targets: ctr, cpc, cvr, cpa, roas, conversions, revenue, video_views
          </div>

          <Card>
            <CardHeader className="pb-1">
              <SectionTitle
                title="Model performance by prediction target"
                desc="Best candidate selected by R²; all candidates' metrics are stored for comparison."
                label="MODEL PREDICTION"
              />
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <div className="adpilot-scroll max-h-96 overflow-y-auto">
                <Table>
                  <TableHeader className="sticky top-0 bg-card">
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="pl-6">Target</TableHead>
                      <TableHead>Best model</TableHead>
                      <TableHead>MAE</TableHead>
                      <TableHead>RMSE</TableHead>
                      <TableHead>R²</TableHead>
                      <TableHead className="pr-6">All candidates (R²)</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.targets.map((t) => {
                      const best = t.metrics[t.best_model];
                      const others = Object.entries(t.metrics)
                        .filter(([k]) => k !== t.best_model)
                        .map(([k, v]) => `${k} ${v.r2 != null ? v.r2.toFixed(2) : "err"}`)
                        .join(" · ");
                      return (
                        <TableRow key={t.target}>
                          <TableCell className="pl-6 font-medium">{t.target}</TableCell>
                          <TableCell>
                            <span className="inline-flex items-center gap-1.5 text-primary">
                              <Cpu className="h-3.5 w-3.5" /> {t.best_model}
                            </span>
                          </TableCell>
                          <TableCell>{best?.mae?.toFixed(4) ?? "—"}</TableCell>
                          <TableCell>{best?.rmse?.toFixed(4) ?? "—"}</TableCell>
                          <TableCell className={getR2Color(best?.r2)}>{best?.r2?.toFixed(3) ?? "—"}</TableCell>
                          <TableCell className="pr-6 text-[11px] text-muted-foreground">{others}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <SectionTitle
                title="Live prediction"
                desc="One inference row per format/objective/category combination, using the best model per target."
              />
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground">Format</p>
                  <Select value={format} onValueChange={setFormat}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {FORMATS.map((f) => <SelectItem key={f.key} value={f.key}>{f.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground">Objective</p>
                  <Select value={objective} onValueChange={setObjective}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {OBJECTIVES.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground">Category</p>
                  <Select value={category} onValueChange={setCategory}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {predict.isError ? (
                <ErrorNote message={String(predict.error)} />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {Object.entries(predict.data?.predictions ?? {}).map(([target, p]) => (
                    <div key={target} className="rounded-lg border bg-secondary/30 p-3">
                      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{target}</p>
                      <p className="mt-1 font-semibold text-primary">
                        {target === "revenue" || target === "cpc" || target === "cpa" || target === "video_views" || target === "conversions"
                          ? fmtNum(p.value, 2)
                          : p.value.toFixed(4)}
                      </p>
                      <p className="mt-0.5 text-[10px] text-muted-foreground">via {p.model}</p>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-[11px] text-muted-foreground">{data.note}</p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function getR2Color(r2: number | undefined) {
  if (r2 == null) return "";
  if (r2 >= 0.7) return "text-emerald-300 font-medium";
  if (r2 >= 0.4) return "text-amber-300";
  return "text-rose-300";
}
