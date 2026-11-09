"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { Database, FileDown, Gauge, Play, Timer } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import {
  CardsSkeleton, ChartTooltip, DataBadge, ErrorNote, SectionTitle, fmtNum,
} from "@/components/adpilot/bits";
import { pyUrl, pyFetch } from "@/lib/pyapi";
import type { BenchmarkRow, BigDataJob } from "@/lib/types";

const SIZES = ["10000", "100000", "1000000", "10000000"];
const ENGINE_LABEL: Record<string, string> = {
  pandas: "Pandas", mapreduce: "Python MapReduce", spark: "PySpark (local)",
};

export function BigDataView() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [rows, setRows] = React.useState("100000");
  const [engines, setEngines] = React.useState<string[]>(["pandas", "mapreduce", "spark"]);
  const [jobId, setJobId] = React.useState<string | null>(null);

  const { data: benchmarks, isLoading } = useQuery({
    queryKey: ["benchmarks"],
    queryFn: () => pyFetch<{ benchmarks: BenchmarkRow[] }>("/api/v1/bigdata/benchmarks"),
    refetchInterval: jobId ? 2000 : false,
  });

  const { data: job } = useQuery({
    queryKey: ["bd-job", jobId],
    queryFn: () => pyFetch<BigDataJob>(`/api/v1/bigdata/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s && (s === "done" || s === "done_with_errors" || s === "error") ? false : 1500;
    },
  });

  React.useEffect(() => {
    if (job && ["done", "done_with_errors", "error"].includes(job.status)) {
      qc.invalidateQueries({ queryKey: ["benchmarks"] });
    }
  }, [job?.status, qc]);

  const run = useMutation({
    mutationFn: () =>
      pyFetch<{ job_id: string }>("/api/v1/bigdata/benchmark", {
        method: "POST",
        body: JSON.stringify({ rows: Number(rows), engines }),
      }),
    onSuccess: (d) => {
      setJobId(d.job_id);
      toast({ title: "Benchmark started", description: `${fmtNum(Number(rows))} rows · ${engines.length} engines` });
    },
  });

  const latestChart = (benchmarks?.benchmarks ?? []).find(
    (b) => b.status === "ok" || b.status === "error",
  );

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Big Data Lab</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Generate synthetic YouTube campaign datasets and benchmark three processing engines on
          identical inputs. All results are measured during the run — never estimated.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <SectionTitle
            title="Run a benchmark"
            desc="The generator streams rows to CSV (10k–10M), then each engine ingests, cleans, transforms and aggregates the same file. Totals are cross-checked for equivalence."
            label="ESTIMATED DATA"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground">Dataset size (rows)</p>
              <Select value={rows} onValueChange={setRows}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SIZES.map((s) => <SelectItem key={s} value={s}>{fmtNum(Number(s))}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground">Engines</p>
              <div className="flex flex-wrap gap-4 pt-2">
                {["pandas", "mapreduce", "spark"].map((e) => (
                  <label key={e} className="flex cursor-pointer items-center gap-2 text-sm">
                    <Checkbox
                      checked={engines.includes(e)}
                      onCheckedChange={(v) =>
                        setEngines((prev) => (v ? [...prev, e] : prev.filter((x) => x !== e)))
                      }
                    />
                    {ENGINE_LABEL[e]}
                  </label>
                ))}
              </div>
            </div>
          </div>

          {run.isError ? <ErrorNote message={String(run.error)} /> : null}

          <div className="flex items-center gap-3">
            <Button disabled={run.isPending || engines.length === 0} onClick={() => run.mutate()}>
              <Play className="mr-2 h-4 w-4" /> Generate &amp; benchmark
            </Button>
            {job ? (
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="truncate">{job.current_step}</span>
                  <span>{Math.round(job.progress)}%</span>
                </div>
                <Progress value={job.progress} className="mt-1" />
              </div>
            ) : null}
          </div>
          {job?.status === "error" ? <ErrorNote message={job.error} /> : null}
          {job && ["done", "done_with_errors"].includes(job.status) ? (
            <p className="text-xs text-emerald-300">
              Benchmark finished — results appended to the table below.
              {job.status === "done_with_errors" ? " Some engines reported errors (see table)." : ""}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-1">
          <SectionTitle
            title="Measured benchmark results"
            desc="pandas / mapreduce / spark pipeline seconds, peak process-tree memory, and cross-engine equivalence checks."
          />
        </CardHeader>
        <CardContent className="px-0 pb-0">
          {isLoading ? (
            <div className="p-6"><CardsSkeleton rows={2} /></div>
          ) : !(benchmarks?.benchmarks ?? []).length ? (
            <p className="p-6 text-sm text-muted-foreground">
              No benchmarks yet — run one above.
            </p>
          ) : (
            <div className="adpilot-scroll max-h-96 overflow-y-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-card">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="pl-6">Engine</TableHead>
                    <TableHead>Rows</TableHead>
                    <TableHead>CSV size</TableHead>
                    <TableHead>Generate</TableHead>
                    <TableHead><Timer className="inline h-3.5 w-3.5" /> Pipeline</TableHead>
                    <TableHead><Gauge className="inline h-3.5 w-3.5" /> Peak RSS</TableHead>
                    <TableHead>Equivalence</TableHead>
                    <TableHead className="pr-6">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {benchmarks!.benchmarks.map((b) => (
                    <TableRow key={b.id}>
                      <TableCell className="pl-6 font-medium">{ENGINE_LABEL[b.engine] ?? b.engine}</TableCell>
                      <TableCell>{fmtNum(b.rows)}</TableCell>
                      <TableCell>{b.dataset_size_mb.toFixed(1)} MB</TableCell>
                      <TableCell>{b.generate_seconds.toFixed(1)}s</TableCell>
                      <TableCell>{b.pipeline_seconds ? `${b.pipeline_seconds.toFixed(2)}s` : "—"}</TableCell>
                      <TableCell>{b.peak_memory_mb ? `${fmtNum(b.peak_memory_mb)} MB` : "—"}</TableCell>
                      <TableCell>
                        {b.status === "ok" ? (b.equivalence_ok ? "✓ match" : "✗ mismatch") : "—"}
                      </TableCell>
                      <TableCell className="pr-6">
                        {b.status === "ok" ? (
                          <span className="text-emerald-400">ok</span>
                        ) : (
                          <span className="text-rose-400" title={b.error}>
                            {b.error ? `error — ${b.error.slice(0, 42)}` : "error"}
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <SectionTitle title="Latest benchmark chart" desc="Rendered server-side with matplotlib from the measured run." />
          </CardHeader>
          <CardContent>
            <BenchmarkChart benchmarks={benchmarks?.benchmarks ?? []} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <SectionTitle
              title="Engine notes"
              desc="What each engine actually is in this deployment."
            />
          </CardHeader>
          <CardContent className="space-y-3 text-xs leading-relaxed text-muted-foreground">
            <p><span className="font-semibold text-foreground">Pandas</span> — columnar in-memory processing with explicit category dtypes; the equivalence baseline.</p>
            <p><span className="font-semibold text-foreground">Python MapReduce</span> — a genuine mapper/shuffle/reducer pipeline built on multiprocessing pools with byte-aligned input chunks and per-chunk combiners. It is a single-machine implementation, <em>not</em> a distributed Hadoop cluster (no HDFS/YARN) — by design and stated as such.</p>
            <p><span className="font-semibold text-foreground">PySpark</span> — Spark 4 local[*] with the same cleaning + aggregation contract as Pandas. Requires Java 17+.</p>
            <div className="flex items-center gap-2 pt-1">
              <Database className="h-3.5 w-3.5" />
              <span>Datasets are stored under <code>backend/data/datasets/</code>; reports under <code>backend/data/benchmarks/</code>.</span>
            </div>
            <a
              className="inline-flex items-center gap-1.5 text-primary hover:underline"
              href={pyUrl("/api/v1/bigdata/benchmark/report")}
              target="_blank"
              rel="noreferrer"
            >
              <FileDown className="h-3.5 w-3.5" /> Open latest markdown benchmark report
            </a>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function BenchmarkChart({ benchmarks }: { benchmarks: BenchmarkRow[] }) {
  const bySize = new Map<number, BenchmarkRow[]>();
  for (const b of benchmarks) {
    if (b.status !== "ok" || !b.pipeline_seconds) continue;
    const list = bySize.get(b.rows) ?? [];
    list.push(b);
    bySize.set(b.rows, list);
  }
  const sizes = [...bySize.keys()].sort((a, b) => a - b).slice(-4);
  const data = sizes.map((rows) => {
    const entry: Record<string, number | string> = { size: fmtNum(rows) };
    for (const b of bySize.get(rows) ?? []) {
      entry[ENGINE_LABEL[b.engine] ?? b.engine] = b.pipeline_seconds;
    }
    return entry;
  });

  if (!data.length) {
    return <EmptyChart />;
  }

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} onClick={() => undefined}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1c2a44" />
          <XAxis dataKey="size" tick={{ fill: "#7c8db0", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#1c2a44" }} />
          <YAxis tick={{ fill: "#7c8db0", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}s`} width={44} />
          <ChartTooltip />
          {["Pandas", "Python MapReduce", "PySpark (local)"].map((k, i) => (
            <Bar key={k} dataKey={k} fill={["#34d399", "#f59e0b", "#38bdf8"][i]} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 flex justify-center">
        <DataBadge label="LIVE DATA" />
      </div>
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
      Run a benchmark to render the comparison chart.
    </div>
  );
}
