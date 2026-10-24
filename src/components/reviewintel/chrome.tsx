"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Database, Sparkles } from "lucide-react";

export function RiHeader({
  backendOk,
  productName,
  onHome,
}: {
  backendOk: boolean;
  productName?: string;
  onHome: () => void;
}) {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
        {productName ? (
          <Button variant="ghost" size="sm" onClick={onHome} aria-label="Back to search">
            <ArrowLeft className="size-4" />
            <span className="hidden sm:inline">New search</span>
          </Button>
        ) : null}
        <button onClick={onHome} className="flex items-center gap-2" aria-label="Home">
          <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </span>
          <span className="font-semibold tracking-tight">
            Review<span className="text-primary">Lens</span>
          </span>
        </button>
        <Badge variant="outline" className="hidden text-[10px] font-normal md:inline-flex">
          AI Product Review Intelligence
        </Badge>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
          <Database className="size-3.5" />
          <span
            aria-hidden
            className={`size-2 rounded-full ${backendOk ? "bg-emerald-500" : "bg-amber-500"}`}
          />
          <span className="hidden sm:inline">
            {backendOk ? "Python API connected" : "Connecting to Python API..."}
          </span>
        </span>
      </div>
    </header>
  );
}

export function RiFooter() {
  return (
    <footer className="mt-auto border-t bg-muted/30">
      <div className="mx-auto max-w-7xl px-4 py-4 text-xs leading-relaxed text-muted-foreground sm:px-6">
        <p className="font-medium text-foreground/70">
          ReviewLens - cross-platform product review intelligence
        </p>
        <p>
          Sentiment percentages describe the collected sample only and are not customer
          ratings or verified quality measures. Platform comparisons must consider sample
          size and audience composition. Comments are collected via authorized APIs;
          clearly-labelled SAMPLE data is used when no live access is available and is
          never presented as real reviews.
        </p>
      </div>
    </footer>
  );
}
