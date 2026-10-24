"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ensureBackend, pyFetch } from "@/lib/pyapi";
import type { PlatformInfo } from "@/lib/types";
import {
  AlertTriangle, BarChart3, CheckCircle2, Globe, Loader2, Search,
  ShieldCheck, Store, Users, XCircle,
} from "lucide-react";

const PLATFORM_ICON: Record<string, React.ReactNode> = {
  marketplace: <Store className="size-4 text-primary" />,
  social: <Users className="size-4 text-primary" />,
};

export function HomeView({
  onSearch,
  backendOk,
}: {
  onSearch: (jobId: string, productName: string) => void;
  backendOk: boolean;
}) {
  const [productName, setProductName] = useState("");
  const [description, setDescription] = useState("");
  // null => all platforms selected (derived, no effect needed)
  const [selected, setSelected] = useState<Set<string> | null>(null);
  const [includeSample, setIncludeSample] = useState(true);
  const [formError, setFormError] = useState("");

  const { data: backend } = useQuery({
    queryKey: ["py-health"],
    queryFn: ensureBackend,
    enabled: !backendOk,
  });

  const { data: platforms, isLoading } = useQuery({
    queryKey: ["platforms"],
    queryFn: () => pyFetch<{ platforms: PlatformInfo[] }>("/api/platforms"),
    enabled: backendOk || !!backend?.healthy,
  });

  const allKeys = platforms?.platforms.map((p) => p.key) ?? [];
  const activeSelection: Set<string> = selected ?? new Set(allKeys);

  const search = useMutation({
    mutationFn: () =>
      pyFetch<{ job_id: string }>("/api/search", {
        method: "POST",
        body: JSON.stringify({
          product_name: productName,
          description: description || null,
          platforms: activeSelection.size && activeSelection.size !== allKeys.length
            ? Array.from(activeSelection)
            : null,
          include_sample: includeSample,
        }),
      }),
    onSuccess: (data) => onSearch(data.job_id, productName),
    onError: (e: Error) => setFormError(e.message),
  });

  const toggle = (key: string) => {
    const base = new Set(activeSelection);
    if (base.has(key)) base.delete(key);
    else base.add(key);
    setSelected(base);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (productName.trim().length < 2) {
      setFormError("Please enter a product name (at least 2 characters).");
      return;
    }
    search.mutate();
  };

  const marketplaces = platforms?.platforms.filter((p) => p.type === "marketplace") ?? [];
  const socials = platforms?.platforms.filter((p) => p.type === "social") ?? [];

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6">
      {/* Hero */}
      <section className="pt-10 text-center sm:pt-14">
        <Badge variant="secondary" className="mb-4 gap-1.5">
          <Globe className="size-3" /> 6 marketplaces · 6 social platforms · EN + اردو + Roman Urdu
        </Badge>
        <h1 className="mx-auto max-w-3xl text-3xl font-bold tracking-tight sm:text-5xl">
          How do customers <span className="text-primary">really</span> feel about a product?
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-balance text-sm text-muted-foreground sm:text-base">
          Search any product and ReviewLens collects available reviews and public
          discussions across e-commerce marketplaces and social media, then analyzes
          sentiment in English, Urdu and Roman Urdu — including mixed-language comments —
          with aspect-level insights and an honest, evidence-based verdict.
        </p>
      </section>

      {/* Search card */}
      <section className="mt-8">
        <Card className="border-primary/20 shadow-lg shadow-primary/5">
          <CardContent className="p-5 sm:p-7">
            <form onSubmit={submit} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-[1.2fr_1fr]">
                <div className="space-y-2">
                  <Label htmlFor="product-name">Product name *</Label>
                  <Input
                    id="product-name"
                    placeholder="e.g. Samsung Galaxy S25 Ultra"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    className="h-11"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="product-desc">
                    Description / details{" "}
                    <span className="font-normal text-muted-foreground">(optional)</span>
                  </Label>
                  <Input
                    id="product-desc"
                    placeholder="e.g. 512GB, Titanium Gray, PTA Approved"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="h-11"
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Details like brand, model, variant and specifications help the matcher
                distinguish between models, generations and variants.
              </p>

              {/* Platform picker */}
              <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Label className="text-sm font-medium">Platforms to search</Label>
                  <div className="flex gap-2">
                    <Button type="button" variant="outline" size="sm"
                      onClick={() => setSelected(new Set(allKeys))}>
                      Select all
                    </Button>
                    <Button type="button" variant="outline" size="sm"
                      onClick={() => setSelected(new Set())}>
                      Clear
                    </Button>
                  </div>
                </div>
                {isLoading ? (
                  <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
                    {Array.from({ length: 12 }).map((_, i) => (
                      <Skeleton key={i} className="h-9" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="grid gap-1.5 sm:grid-cols-3 lg:grid-cols-4">
                      {marketplaces.map((p) => (
                        <PlatformChip key={p.key} p={p} selected={activeSelection.has(p.key)} onToggle={() => toggle(p.key)} />
                      ))}
                    </div>
                    <div className="grid gap-1.5 sm:grid-cols-3 lg:grid-cols-4">
                      {socials.map((p) => (
                        <PlatformChip key={p.key} p={p} selected={activeSelection.has(p.key)} onToggle={() => toggle(p.key)} />
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Sample data toggle */}
              <div className="flex items-start justify-between gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
                <div className="space-y-0.5">
                  <Label htmlFor="sample-toggle" className="flex items-center gap-2 text-sm font-medium">
                    <AlertTriangle className="size-4 text-amber-600" />
                    Include clearly-labelled sample dataset
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    Marketplaces/social APIs require platform approval. When live access is
                    unavailable, a synthetic <b>sample corpus</b> (English / Urdu / Roman
                    Urdu) is used so the full pipeline can be demonstrated. Sample items are
                    always badged <b>SAMPLE</b> and never shown as real reviews.
                  </p>
                </div>
                <Switch id="sample-toggle" checked={includeSample} onCheckedChange={setIncludeSample} />
              </div>

              {formError ? (
                <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </p>
              ) : null}

              <Button type="submit" size="lg" className="w-full text-base sm:w-auto" disabled={search.isPending}>
                {search.isPending ? (
                  <Loader2 className="size-5 animate-spin" />
                ) : (
                  <Search className="size-5" />
                )}
                Analyze product sentiment
              </Button>
            </form>
          </CardContent>
        </Card>
      </section>

      {/* How it works */}
      <section className="mt-12 grid gap-4 pb-12 sm:grid-cols-2 lg:grid-cols-4">
        <Feature icon={<Search className="size-5" />} title="1 · Collect"
          text="Authorized platform APIs collect reviews, ratings and public comments. Each adapter is independent — one failure never blocks the rest, and integration status is always shown honestly." />
        <Feature icon={<Globe className="size-5" />} title="2 · Understand"
          text="Language detection for English, Urdu script, Roman Urdu and mixed comments, with spelling-variant normalization (bohat/bahut/bohot…) and confidence scores." />
        <Feature icon={<BarChart3 className="size-5" />} title="3 · Analyze"
          text="Context-aware sentiment (positive / negative / neutral / mixed), aspect-based insights (battery, delivery, price, authenticity…), spam filtering and deduplication." />
        <Feature icon={<ShieldCheck className="size-5" />} title="4 · Compare honestly"
          text="Cross-platform comparison with sample sizes, low-sample warnings and a transparent scoring methodology. No invented data, ever." />
      </section>
    </div>
  );
}

function PlatformChip({ p, selected, onToggle }: {
  p: PlatformInfo;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <label
          className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
            selected ? "border-primary/50 bg-primary/5 font-medium" : "bg-background"
          }`}
        >
          <Checkbox checked={selected} onCheckedChange={onToggle} aria-label={`Toggle ${p.name}`} />
          {PLATFORM_ICON[p.type]}
          <span className="truncate">{p.name}</span>
          {p.has_credentials ? (
            <CheckCircle2 className="ml-auto size-3.5 shrink-0 text-emerald-600" />
          ) : (
            <XCircle className="ml-auto size-3.5 shrink-0 text-muted-foreground/60" />
          )}
        </label>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-64 text-xs">
        <p className="font-medium">{p.name}</p>
        <p className="mt-1 text-muted-foreground">{p.access_mode}</p>
        <p className="mt-1">{p.notes}</p>
      </TooltipContent>
    </Tooltip>
  );
}

function Feature({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <Card className="border-muted">
      <CardContent className="p-4">
        <div className="mb-2 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
          {icon}
        </div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{text}</p>
      </CardContent>
    </Card>
  );
}
