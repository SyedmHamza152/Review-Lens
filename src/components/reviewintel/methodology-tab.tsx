"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Report } from "@/lib/types";
import { BookOpenCheck, Database, Scale, ShieldCheck } from "lucide-react";

export function MethodologyTab({ report }: { report: Report }) {
  const m = report.methodology;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Scale className="size-4 text-primary" /> Scoring methodology
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed">
          <p><b>Pipeline:</b> {m.nlp_pipeline}</p>
          <p>{m.scoring}</p>
          <p><b>Mixed comments:</b> {m.mixed_rule}</p>
          <p><b>Verdict thresholds</b> operate on the confidence-weighted shares of positive/negative/mixed comments and require at least {m.min_sample_for_verdict} analyzed comments - otherwise the verdict is <i>Insufficient Data</i>.</p>
          <p><b>Low-sample flag:</b> platforms with fewer than {m.low_sample_platform_threshold} analyzed comments are marked “low sample” and excluded from ranking.</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="size-4 text-primary" /> Honest data coverage
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed">
          <p>
            Each platform adapter reports one of: <b>live success</b>, <b>no results</b>,{" "}
            <b>needs credentials</b> (exact env vars listed), <b>access blocked</b>, or{" "}
            <b>unsupported</b> (platform offers no authorized API and forbids scraping).
          </p>
          <p>
            When live access is unavailable and the sample toggle is on, results are
            filled from the clearly-labelled <b>SAMPLE corpus</b> - synthetic comments
            written to exercise the multilingual pipeline. They are badged everywhere and
            stored with <code className="rounded bg-muted px-1 text-xs">data_source=sample</code>.
          </p>
          <div className="space-y-1.5">
            {report.platform_statuses.map((s) => (
              <div key={s.platform} className="flex items-center gap-2 text-xs">
                <span className="w-24 font-medium">{s.platform_name}</span>
                <Badge variant="outline" className="text-[9px]">{s.status}</Badge>
                <span className="tabular-nums text-muted-foreground">{s.items_collected} items</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <BookOpenCheck className="size-4 text-primary" /> Disclaimers
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {m.disclaimers.map((d, i) => <li key={i}>{d}</li>)}
          </ul>
          <div className="mt-3 flex items-start gap-2 rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
            <Database className="mt-0.5 size-3.5 shrink-0" />
            <p>
              Comments are stored with strict separation between the original text, the
              normalized analysis copy and the English gloss. Sentiment/language
              confidence and uncertainty flags are preserved per comment. The system
              follows platform ToS - it never bypasses logins, CAPTCHAs or rate limits,
              and never fabricates data.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
