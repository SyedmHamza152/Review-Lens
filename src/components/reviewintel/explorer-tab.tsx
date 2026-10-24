"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { pyFetch } from "@/lib/pyapi";
import type { BelowMinimumPlatform, PaginatedReviews, ReviewRow, SentimentLabel } from "@/lib/types";
import { ChevronUp, ExternalLink, Filter, Info, Languages, Search, Sparkles } from "lucide-react";

const SENTIMENT_BADGE: Record<string, string> = {
  positive: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700",
  negative: "border-red-500/40 bg-red-500/10 text-red-700",
  neutral: "border-slate-400/40 bg-slate-400/10 text-slate-600",
  mixed: "border-amber-500/40 bg-amber-500/10 text-amber-700",
};

export function ExplorerTab({ jobId, belowMinimum = [] }: { jobId: string; belowMinimum?: BelowMinimumPlatform[] }) {
  const [platform, setPlatform] = useState("all");
  const [sentiment, setSentiment] = useState("all");
  const [language, setLanguage] = useState("all");
  const [scope, setScope] = useState("all");
  const [minRating, setMinRating] = useState("any");
  const [sort, setSort] = useState("date");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<number | null>(null);

  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (platform !== "all") p.set("platform", platform);
    if (sentiment !== "all") p.set("sentiment", sentiment);
    if (language !== "all") p.set("language", language);
    if (scope !== "all") p.set("scope", scope);
    if (minRating !== "any") p.set("min_rating", minRating);
    if (q.trim()) p.set("q", q.trim());
    p.set("sort", sort);
    p.set("page", String(page));
    p.set("page_size", "20");
    return p.toString();
  }, [platform, sentiment, language, scope, minRating, sort, q, page]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["reviews", jobId, params],
    queryFn: () => pyFetch<PaginatedReviews>(`/api/jobs/${jobId}/reviews?${params}`),
    placeholderData: (prev) => prev,
  });

  const reset = () => {
    setPlatform("all"); setSentiment("all"); setLanguage("all");
    setScope("all"); setMinRating("any"); setSort("date"); setQ(""); setPage(1);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-4">
      {belowMinimum.length > 0 ? (
        <div className="space-y-2">
          {belowMinimum.map((b) => (
            <div key={b.platform}
              className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
              <Info className="mt-0.5 size-4 shrink-0 text-amber-600" />
              <p>
                <b>{b.platform_name}:</b> {b.message}
              </p>
            </div>
          ))}
        </div>
      ) : null}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Filter className="size-4 text-primary" />
            <div className="relative min-w-52 flex-1">
              <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => { setQ(e.target.value); setPage(1); }}
                placeholder="Search comments…"
                className="h-9 pl-8"
                aria-label="Search comments"
              />
            </div>
            <SelectBox value={platform} onChange={(v) => { setPlatform(v); setPage(1); }} label="Platform"
              options={PLATFORMS} />
            <SelectBox value={sentiment} onChange={(v) => { setSentiment(v); setPage(1); }} label="Sentiment"
              options={SENTIMENTS} />
            <SelectBox value={language} onChange={(v) => { setLanguage(v); setPage(1); }} label="Language"
              options={LANGUAGES} />
            <SelectBox value={scope} onChange={(v) => { setScope(v); setPage(1); }} label="Complaint scope"
              options={SCOPES} />
            <SelectBox value={minRating} onChange={(v) => { setMinRating(v); setPage(1); }} label="Min rating"
              options={RATINGS} />
            <SelectBox value={sort} onChange={(v) => setSort(v)} label="Sort"
              options={[
                { value: "date", label: "Newest" },
                { value: "sentiment", label: "Sentiment score" },
                { value: "rating", label: "Rating" },
                { value: "relevance", label: "Relevance" },
              ]} />
            <Button variant="ghost" size="sm" onClick={reset}>Reset</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="px-0 pb-2">
          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10" />)}
            </div>
          ) : !data || data.total === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No comments match the selected filters.
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="pl-5">Comment</TableHead>
                      <TableHead className="w-24">Platform</TableHead>
                      <TableHead className="w-24">Sentiment</TableHead>
                      <TableHead className="w-28">Language</TableHead>
                      <TableHead className="w-16 text-right">Rating</TableHead>
                      <TableHead className="w-24 pr-5 text-right">Date</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((r) => (
                      <ReviewRowItem
                        key={r.id}
                        r={r}
                        expanded={expanded === r.id}
                        onToggle={() => setExpanded(expanded === r.id ? null : r.id)}
                      />
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="flex items-center justify-between px-5 pt-2 text-xs text-muted-foreground">
                <span>
                  {data.total} comments{isFetching ? " · refreshing…" : ""}
                </span>
                <span className="flex items-center gap-2">
                  <Button variant="outline" size="sm" className="h-7"
                    disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    Prev
                  </Button>
                  <span className="tabular-nums">page {page} / {totalPages}</span>
                  <Button variant="outline" size="sm" className="h-7"
                    disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                    Next
                  </Button>
                </span>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ReviewRowItem({ r, expanded, onToggle }: { r: ReviewRow; expanded: boolean; onToggle: () => void }) {
  return (
    <>
      <TableRow className="cursor-pointer align-top" onClick={onToggle}>
        <TableCell className="max-w-md pl-5">
          <p className="line-clamp-2 text-sm leading-snug" dir="auto">{r.text_original}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {r.aspects.slice(0, 3).map((a) => (
              <span key={a.aspect}
                className={`rounded px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide ${
                  a.label === "positive" ? "bg-emerald-500/10 text-emerald-700"
                  : a.label === "negative" ? "bg-red-500/10 text-red-700"
                  : "bg-slate-500/10 text-slate-600"
                }`}>
                {a.aspect.replace("_", " ")}
              </span>
            ))}
            {r.complaint_scope !== "none" ? (
              <span className="rounded bg-slate-500/10 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-slate-600">
                {r.complaint_scope} complaint
              </span>
            ) : null}
            {r.sarcasm_suspect ? (
              <span className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-purple-700">
                sarcasm?
              </span>
            ) : null}
          </div>
        </TableCell>
        <TableCell>
          <span className="text-xs font-medium">{r.platform_name}</span>
          {r.data_source === "sample" ? (
            <Sparkles className="ml-1 inline size-3 text-amber-500" aria-label="sample data" />
          ) : null}
        </TableCell>
        <TableCell>
          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${SENTIMENT_BADGE[r.sentiment]}`}>
            {r.sentiment}
          </span>
          <span className="block text-[10px] tabular-nums text-muted-foreground">
            {r.sentiment_score >= 0 ? "+" : ""}{r.sentiment_score.toFixed(2)} · {(r.sentiment_confidence * 100).toFixed(0)}%
          </span>
        </TableCell>
        <TableCell>
          <span className="flex items-center gap-1 text-xs capitalize">
            <Languages className="size-3 text-muted-foreground" />
            {r.language.replace("_", " ")}
          </span>
          {r.language_uncertain ? (
            <span className="text-[10px] text-amber-600">uncertain</span>
          ) : null}
        </TableCell>
        <TableCell className="text-right text-sm tabular-nums">
          {r.rating ?? "—"}
        </TableCell>
        <TableCell className="pr-5 text-right text-xs tabular-nums text-muted-foreground">
          {r.review_date ? new Date(r.review_date).toLocaleDateString() : "—"}
        </TableCell>
      </TableRow>
      {expanded ? (
        <TableRow className="bg-muted/30 hover:bg-muted/30">
          <TableCell colSpan={6} className="px-5 py-4">
            <div className="space-y-2 text-sm">
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Original</p>
                <p className="leading-relaxed" dir="auto">{r.text_original}</p>
              </div>
              {r.translation ? (
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    English gloss (approximate)
                  </p>
                  <p className="leading-relaxed text-muted-foreground">{r.translation}</p>
                </div>
              ) : null}
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span>relevance {(r.relevance * 100).toFixed(0)}%</span>
                <span>variant: {r.variant ?? "—"}</span>
                <span>source: {r.data_source === "sample" ? "SAMPLE (synthetic)" : "live API"}</span>
                {r.source_url ? (
                  <a href={r.source_url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline">
                    open source <ExternalLink className="size-3" />
                  </a>
                ) : (
                  <span>source link n/a (sample data)</span>
                )}
                <button onClick={onToggle} className="ml-auto inline-flex items-center gap-1 text-primary hover:underline">
                  hide <ChevronUp className="size-3" />
                </button>
              </div>
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  );
}

function SelectBox({ value, onChange, label, options }: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  options: { value: string; label: string }[];
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-9 w-[7.5rem] shrink-0 text-xs" aria-label={label}>
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value} className="text-xs">
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

const PLATFORMS = [
  { value: "all", label: "All" },
  ...["daraz", "amazon", "alibaba", "aliexpress", "temu", "shein",
    "reddit", "youtube", "x", "facebook", "instagram", "tiktok"].map((p) => ({
    value: p, label: p === "x" ? "X" : p[0].toUpperCase() + p.slice(1),
  })),
];
const SENTIMENTS: { value: string; label: string }[] = [
  { value: "all", label: "All" },
  ...(["positive", "negative", "neutral", "mixed"] as SentimentLabel[]).map((s) => ({
    value: s, label: s[0].toUpperCase() + s.slice(1),
  })),
];
const LANGUAGES = [
  { value: "all", label: "All" },
  { value: "english", label: "English" },
  { value: "roman_urdu", label: "Roman Urdu" },
  { value: "urdu", label: "Urdu script" },
  { value: "mixed", label: "Mixed" },
];
const SCOPES = [
  { value: "all", label: "All" },
  { value: "product", label: "Product complaints" },
  { value: "seller", label: "Seller complaints" },
  { value: "marketplace", label: "Marketplace complaints" },
  { value: "both", label: "Product + seller" },
  { value: "none", label: "No complaints" },
];
const RATINGS = [
  { value: "any", label: "Any" },
  { value: "1", label: "≥ 1" },
  { value: "2", label: "≥ 2" },
  { value: "3", label: "≥ 3" },
  { value: "4", label: "≥ 4" },
  { value: "5", label: "5" },
];
