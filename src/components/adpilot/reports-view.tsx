"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { FileSpreadsheet, FileText, Files, Sheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { CardsSkeleton, DataBadge, ErrorNote, SectionTitle } from "@/components/adpilot/bits";
import { pyFetch, reportDownloadUrl } from "@/lib/pyapi";
import type { ReportRow } from "@/lib/types";

const FORMAT_META: Record<string, { icon: React.ReactNode; name: string }> = {
  pdf: { icon: <FileText className="h-4 w-4 text-rose-300" />, name: "PDF report" },
  xlsx: { icon: <FileSpreadsheet className="h-4 w-4 text-emerald-300" />, name: "Excel workbook" },
  csv: { icon: <Sheet className="h-4 w-4 text-sky-300" />, name: "CSV extract" },
};

export function ReportsView({ analysisId }: { analysisId: number | null }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [busy, setBusy] = React.useState<string | null>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["reports"],
    queryFn: () => pyFetch<{ reports: ReportRow[] }>("/api/v1/reports"),
  });

  const activeId = analysisId;

  const generate = useMutation({
    mutationFn: (format: string) =>
      pyFetch<{ id: number; size_bytes: number }>("/api/v1/reports", {
        method: "POST",
        body: JSON.stringify({ analysis_id: activeId, format }),
      }),
    onSuccess: (_d, format) => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      setBusy(null);
      toast({ title: `${FORMAT_META[format]?.name ?? format} generated` });
    },
    onError: () => setBusy(null),
  });

  if (isLoading) return <div className="p-4 lg:p-6"><CardsSkeleton rows={2} /></div>;
  if (isError) return <div className="p-6"><ErrorNote message={String(error)} /></div>;

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Reports</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Export the full analysis: product info, objective, audience, competitor research,
          allocation, predictions, methodology, confidence and limitations.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <SectionTitle
            title="Generate a new report"
            desc={activeId ? `Target analysis: #${activeId}` : "No active analysis — the latest one will be used."}
            label="MODEL PREDICTION"
          />
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          {(["pdf", "xlsx", "csv"] as const).map((f) => (
            <Button
              key={f}
              variant="outline"
              disabled={!activeId || generate.isPending}
              onClick={() => { setBusy(f); generate.mutate(f); }}
            >
              {FORMAT_META[f].icon}
              <span className="ml-2">{FORMAT_META[f].name}</span>
            </Button>
          ))}
          {!activeId ? (
            <p className="w-full text-xs text-muted-foreground">
              Run an analysis first — reports need product, allocation and prediction data.
            </p>
          ) : null}
          {generate.isError ? <div className="w-full"><ErrorNote message={String(generate.error)} /></div> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Files className="h-4 w-4" /> Generated reports
          </CardTitle>
        </CardHeader>
        <CardContent className="px-0 pb-0">
          {!(data?.reports ?? []).length ? (
            <p className="p-6 text-sm text-muted-foreground">No reports yet — generate one above.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-6">Format</TableHead>
                  <TableHead>Analysis</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="pr-6">Download</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data!.reports.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="pl-6">
                      <span className="inline-flex items-center gap-2">
                        {FORMAT_META[r.format]?.icon}
                        {FORMAT_META[r.format]?.name ?? r.format}
                      </span>
                    </TableCell>
                    <TableCell>#{r.analysis_id}</TableCell>
                    <TableCell>{(r.size_bytes / 1024).toFixed(0)} KB</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="pr-6">
                      <a
                        className="text-primary hover:underline"
                        href={reportDownloadUrl(r.id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        download
                      </a>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <DataBadge label="LIVE DATA" />
        <DataBadge label="ESTIMATED DATA" />
        <DataBadge label="MODEL PREDICTION" />
        <span className="text-xs text-muted-foreground">
          — every report section carries its own source label, so a reader can never mistake one class of number for another.
        </span>
      </div>
    </div>
  );
}
