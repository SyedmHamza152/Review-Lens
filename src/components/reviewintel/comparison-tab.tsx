"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Report } from "@/lib/types";
import { PlatformStackedBar } from "./charts";
import { Crown, Info } from "lucide-react";

export function ComparisonTab({ report }: { report: Report }) {
  const rows = report.comparison;
  const [showDetails, setShowDetails] = useState<string | null>(null);
  const best = rows.find((r) => r.rank_by_positive === 1);
  const mostNegative = [...rows].sort((a, b) => (b.negative_pct ?? 0) - (a.negative_pct ?? 0))[0];

  return (
    <div className="space-y-5">
      {/* Q&A callouts */}
      <div className="grid gap-3 md:grid-cols-2">
        <Card className="border-primary/25 bg-primary/5">
          <CardContent className="flex gap-3 p-4">
            <Crown className="mt-0.5 size-5 shrink-0 text-primary" />
            <div className="text-sm">
              <p className="font-medium">Most positive feedback in this sample</p>
              <p className="mt-1 text-muted-foreground">
                {best
                  ? `${best.platform_name} - ${best.positive_pct}% positive across ${best.total} analyzed comments.`
                  : "No comments were analyzed yet."}
                {" "}A higher positive share reflects this collected sample (audience and
                video selection differ), not overall product quality.
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-red-500/20 bg-red-500/5">
          <CardContent className="flex gap-3 p-4">
            <Info className="mt-0.5 size-5 shrink-0 text-red-500" />
            <div className="text-sm">
              <p className="font-medium">Most complaints in this sample</p>
              <p className="mt-1 text-muted-foreground">
                {mostNegative && (mostNegative.negative_pct ?? 0) > 0
                  ? `${mostNegative.platform_name} - ${mostNegative.negative_pct}% negative across ${mostNegative.total} comments (top complaint: ${mostNegative.top_complaint_aspect ?? "n/a"}).`
                  : "No negative feedback stands out in this sample."}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Source-by-source comparison</CardTitle>
          <p className="text-xs font-normal text-muted-foreground">
            Percentages are of the analyzed YouTube comments. Sources marked{" "}
            <b>low sample</b> (&lt;{report.methodology.low_sample_platform_threshold}{" "}
            comments) are not meaningful for ranking.
          </p>
        </CardHeader>
        <CardContent className="px-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-6">#</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead className="text-right">N</TableHead>
                  <TableHead className="text-right">Positive</TableHead>
                  <TableHead className="text-right">Negative</TableHead>
                  <TableHead className="text-right">Neutral</TableHead>
                  <TableHead className="text-right">Mixed</TableHead>
                  <TableHead className="text-right">Avg rating</TableHead>
                  <TableHead className="pr-6 text-right">Data</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow
                    key={r.platform}
                    className="cursor-pointer"
                    onClick={() => setShowDetails(showDetails === r.platform ? null : r.platform)}
                  >
                    <TableCell className="pl-6 tabular-nums text-muted-foreground">
                      {r.rank_by_positive ?? "-"}
                    </TableCell>
                    <TableCell className="font-medium">
                      <span className="flex items-center gap-2">
                        {r.platform_name}
                        {r.low_sample ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Badge variant="outline" className="h-4.5 border-amber-500/40 px-1 text-[9px] text-amber-700">
                                low sample
                              </Badge>
                            </TooltipTrigger>
                            <TooltipContent className="text-xs">
                              Only {r.total} comments - too few for a meaningful comparison.
                            </TooltipContent>
                          </Tooltip>
                        ) : null}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{r.total}</TableCell>
                    <TableCell className="text-right tabular-nums font-medium text-emerald-600">
                      {r.positive_pct !== null ? `${r.positive_pct}%` : "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-red-500">
                      {r.negative_pct !== null ? `${r.negative_pct}%` : "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">
                      {r.neutral_pct !== null ? `${r.neutral_pct}%` : "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-amber-600">
                      {r.mixed_pct !== null ? `${r.mixed_pct}%` : "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.avg_rating ?? "—"}
                    </TableCell>
                    <TableCell className="pr-6 text-right">
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${r.is_sample ? "border-amber-500/40 text-amber-700" : "border-emerald-500/40 text-emerald-700"}`}
                      >
                        {r.is_sample ? "SAMPLE" : "live"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="py-8 text-center text-sm text-muted-foreground">
                      No usable comment sample was collected for comparison.
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
          {showDetails ? (
            <DetailsRow report={report} platformKey={showDetails} />
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Visual comparison</CardTitle>
          <p className="text-xs font-normal text-muted-foreground">
            Sentiment shares of the analyzed sample.
          </p>
        </CardHeader>
        <CardContent>
          {rows.length ? (
            <PlatformStackedBar
              rows={rows.map((r) => ({
                platform_name: `${r.platform_name} (n=${r.total})`,
                positive_pct: r.positive_pct ?? 0,
                negative_pct: r.negative_pct ?? 0,
                neutral_pct: r.neutral_pct ?? 0,
                mixed_pct: r.mixed_pct ?? 0,
              }))}
              height={Math.max(220, rows.length * 44 + 60)}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              Nothing to chart - no comments were analyzed. See the exact counts above.
            </p>
          )}
        </CardContent>
      </Card>

      <p className="px-1 text-xs leading-relaxed text-muted-foreground">
        Comment sentiment on YouTube reflects the audiences of the selected review
        videos - not a verified measure of product quality. Review videos may focus on
        particular models or price brackets, which shapes the discussion.
      </p>
    </div>
  );
}

function DetailsRow({ report, platformKey }: { report: Report; platformKey: string }) {
  const row = report.comparison.find((r) => r.platform === platformKey);
  const status = report.platform_statuses.find((s) => s.platform === platformKey);
  if (!row) return null;
  return (
    <div className="mx-6 my-3 rounded-lg border bg-muted/30 p-4 text-sm">
      <p className="font-medium">{row.platform_name} - details</p>
      <ul className="mt-2 space-y-1 text-muted-foreground">
        <li>Top positive aspect: {row.top_positive_aspect ?? "n/a"}</li>
        <li>Top complaint: {row.top_complaint_aspect ?? "n/a"}</li>
        {row.top_drivers.length ? <li>Frequent signal words: {row.top_drivers.join(", ")}</li> : null}
      </ul>
      <ul className="mt-2 space-y-1 text-muted-foreground">
        <li>Collection status: {row.status} - {status?.message ?? row.message}</li>
        <li>
          Collected at:{" "}
          {row.collected_at ? new Date(row.collected_at).toLocaleString() : "n/a"}
        </li>
      </ul>
    </div>
  );
}
