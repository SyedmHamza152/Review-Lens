"use client";

import * as React from "react";
import {
  ArrowRight, Bot, CheckCircle2, Database, LineChart, Play, Radio,
  ShieldCheck, Sparkles, Target, Youtube,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const FEATURES = [
  {
    icon: Sparkles,
    title: "Product intelligence",
    desc: "Enter just a product name and budget — the engine infers category, audience hypotheses, geo opportunities and the right marketing objective, explaining every inference.",
  },
  {
    icon: Youtube,
    title: "Live YouTube research",
    desc: "YouTube Data API v3 pulls real public videos, channels and engagement for competitor content analysis — clearly separated from paid advertising metrics.",
  },
  {
    icon: Target,
    title: "Constrained optimization",
    desc: "SLSQP optimization with UCB-style exploration distributes your exact budget across In-Stream, Shorts and In-Feed — with a written reason for every allocation.",
  },
  {
    icon: Bot,
    title: "ML predictions",
    desc: "Linear Regression, Random Forest, Gradient Boosting and XGBoost models predict CTR, CPC, CVR, CPA, ROAS and revenue — evaluated with MAE / RMSE / R².",
  },
  {
    icon: Database,
    title: "Big Data lab",
    desc: "Generate synthetic datasets from 10k to 10M rows and benchmark Pandas vs a genuine Python MapReduce pipeline vs PySpark — with measured, cross-checked results.",
  },
  {
    icon: ShieldCheck,
    title: "Data honesty by design",
    desc: "Every number in the product is labeled LIVE DATA, ESTIMATED DATA or MODEL PREDICTION. Nothing is ever fabricated or silently mixed.",
  },
];

const FORMATS = [
  { name: "YouTube In-Stream Ads", desc: "Skippable video before/during content — storytelling and demos." },
  { name: "YouTube Shorts Ads", desc: "Vertical short-form placement — cheap incremental reach." },
  { name: "YouTube In-Feed Video Ads", desc: "Thumbnail cards beside organic content — deliberate clicks." },
];

export function LandingView({
  backendOk,
  hasAnalysis,
  onStart,
  onOpenDashboard,
}: {
  backendOk: boolean;
  hasAnalysis: boolean;
  onStart: () => void;
  onOpenDashboard: () => void;
}) {
  return (
    <div className="min-h-screen">
      {/* hero */}
      <section className="relative overflow-hidden">
        <div className="adpilot-hero-grid absolute inset-0" />
        <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-16 text-center lg:pt-24">
          <Badge variant="outline" className="mb-4 border-primary/40 bg-primary/10 text-primary">
            <Radio className="mr-1.5 h-3 w-3" /> Google &amp; YouTube advertising only
          </Badge>
          <h1 className="mx-auto max-w-3xl text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
            Spend your YouTube ad budget on{" "}
            <span className="text-primary">what actually works</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-muted-foreground sm:text-lg">
            AdPilot AI analyzes your product, researches the live YouTube market, predicts
            performance with machine learning, and optimizes your exact budget across
            In-Stream, Shorts and In-Feed formats — with a transparent reason for every rupee.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" className="h-12 px-7 text-base" onClick={onStart}>
              <Play className="mr-2 h-4 w-4" /> Start Analysis
            </Button>
            {hasAnalysis ? (
              <Button size="lg" variant="outline" className="h-12 px-7 text-base" onClick={onOpenDashboard}>
                Open Dashboard <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : null}
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> No lengthy questionnaires
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> Fully functional without API credentials
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> Every metric source-labeled
            </span>
          </div>
        </div>
      </section>

      {/* formats strip */}
      <section className="border-y bg-card/40">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-8 sm:grid-cols-3">
          {FORMATS.map((f) => (
            <div key={f.name} className="flex gap-3">
              <LineChart className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <div>
                <p className="text-sm font-semibold">{f.name}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* features */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="text-center text-2xl font-bold tracking-tight sm:text-3xl">
          A complete Big Data + ML advertising engine
        </h2>
        <p className="mx-auto mt-2 max-w-2xl text-center text-sm text-muted-foreground">
          FastAPI + PostgreSQL/SQLite backend · Next.js 16 frontend · scikit-learn &amp; XGBoost ·
          Pandas, MapReduce and PySpark pipelines · ReportLab/OpenPyXL reporting.
        </p>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="group rounded-xl border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-lg"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/12 text-primary transition-transform group-hover:scale-105">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-3 font-semibold">{f.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t bg-card/40">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-6 py-14 text-center">
          <h2 className="text-2xl font-bold tracking-tight">Ready to pilot your budget?</h2>
          <p className="max-w-xl text-sm text-muted-foreground">
            One product name, one budget number — that is all AdPilot needs. Everything else is
            inferred, researched, predicted and explained.
          </p>
          <Button size="lg" onClick={onStart} disabled={!backendOk}>
            {backendOk ? "Start Analysis" : "Starting backend…"}
          </Button>
          <p className="text-[11px] text-muted-foreground">
            Default market: Pakistan (PKR) · configurable in Settings
          </p>
        </div>
      </section>

      <footer className="border-t py-6 text-center text-xs text-muted-foreground">
        AdPilot AI · Project 2 — AI-Based Google &amp; YouTube Advertising Budget Optimizer ·
        Follows Review Lens engineering conventions
      </footer>
    </div>
  );
}
