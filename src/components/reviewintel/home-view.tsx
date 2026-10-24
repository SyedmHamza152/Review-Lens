"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ensureBackend, pyFetch } from "@/lib/pyapi";
import {
  BarChart3, Globe, Loader2, Radio, Search, ShieldCheck, Youtube,
} from "lucide-react";

export function HomeView({
  onSearch,
  backendOk,
}: {
  onSearch: (jobId: string, productName: string) => void;
  backendOk: boolean;
}) {
  const [productName, setProductName] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState("");

  const { data: backend } = useQuery({
    queryKey: ["py-health"],
    queryFn: ensureBackend,
    enabled: !backendOk,
  });

  const { data: platforms } = useQuery({
    queryKey: ["platforms"],
    queryFn: () => pyFetch<{ platforms: { key: string; name: string }[] }>("/api/platforms"),
    enabled: backendOk || !!backend?.healthy,
  });

  const search = useMutation({
    mutationFn: () =>
      pyFetch<{ job_id: string }>("/api/search", {
        method: "POST",
        body: JSON.stringify({
          product_name: productName,
          description: description || null,
          platforms: null, // YouTube is the only registered platform
          include_sample: false, // live platform data only
        }),
      }),
    onSuccess: (data) => onSearch(data.job_id, productName),
    onError: (e: Error) => setFormError(e.message),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (productName.trim().length < 2) {
      setFormError("Please enter a product name (at least 2 characters).");
      return;
    }
    search.mutate();
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6">
      {/* Hero */}
      <section className="pt-10 text-center sm:pt-14">
        <Badge variant="secondary" className="mb-4 gap-1.5">
          <Radio className="size-3 text-emerald-600" />
          YouTube-only intelligence · real comments · EN + اردو + Roman Urdu
        </Badge>
        <h1 className="mx-auto max-w-3xl text-3xl font-bold tracking-tight sm:text-5xl">
          How do customers <span className="text-primary">really</span> feel about a product?
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-balance text-sm text-muted-foreground sm:text-base">
          Search any product and ReviewLens collects real comments from YouTube product
          review videos, then analyzes sentiment in English, Urdu and Roman Urdu —
          including mixed-language comments — with aspect-level insights, source-video
          links and an honest, evidence-based verdict.
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

              {/* Source platform (YouTube only by product decision) */}
              <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 p-4">
                <Label className="text-sm font-medium">Comments source:</Label>
                {platforms?.platforms.map((p) => (
                  <Badge key={p.key} variant="outline"
                    className="border-emerald-500/40 text-emerald-700">
                    <Youtube className="mr-1 size-3" /> {p.name} · live
                  </Badge>
                ))}
                <span className="text-xs text-muted-foreground">
                  Every comment links to the video it came from.
                </span>
              </div>

              {/* Live data notice (replaces the old sample-data toggle) */}
              <div className="flex items-start justify-between gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
                <div className="space-y-0.5">
                  <Label className="flex items-center gap-2 text-sm font-medium">
                    <Radio className="size-4 text-emerald-600" />
                    Live YouTube data only
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    Every comment shown is collected <b>live</b> from real YouTube review
                    videos via the public YouTube web API (official Data API v3 when a key
                    is configured). Nothing is ever simulated; if YouTube cannot be
                    reached, the report says so honestly.
                  </p>
                </div>
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
        <Feature icon={<Youtube className="size-5" />} title="1 · Collect"
          text="Real comments are collected live from YouTube product review videos via the public YouTube web API (official Data API v3 when a key is configured). Every comment keeps a link to its source video. Nothing is ever simulated." />
        <Feature icon={<Globe className="size-5" />} title="2 · Understand"
          text="Language detection for English, Urdu script, Roman Urdu and mixed comments, with spelling-variant normalization (bohat/bahut/bohot…) and confidence scores." />
        <Feature icon={<BarChart3 className="size-5" />} title="3 · Analyze"
          text="Context-aware sentiment (positive / negative / neutral / mixed), aspect-based insights (quality, price, durability, authenticity…), spam filtering and deduplication." />
        <Feature icon={<ShieldCheck className="size-5" />} title="4 · Report honestly"
          text="Every analyzed comment counts toward the verdict, whatever the sample size - with low-sample warnings, source-video links and a transparent scoring methodology. No invented data, ever." />
      </section>
    </div>
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
