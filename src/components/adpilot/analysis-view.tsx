"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import * as React from "react";
import { Loader2, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ErrorNote } from "@/components/adpilot/bits";
import { pyFetch } from "@/lib/pyapi";
import type { SettingsInfo } from "@/lib/types";
import { useToast } from "@/hooks/use-toast";

const EXAMPLES = [
  { name: "Premium Cricket Bat", budget: 50000, description: "Professional English willow cricket bat for hard-ball players." },
  { name: "Wireless Earbuds Pro", budget: 120000, description: "Bluetooth 5.3 earbuds with ANC and 40-hour battery life." },
  { name: "Online IELTS Preparation Course", budget: 80000, description: "Live classes with certified trainers and mock exams." },
];

export function AnalysisView({ onStarted }: { onStarted: (jobId: string) => void }) {
  const [name, setName] = React.useState("");
  const [budget, setBudget] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [currency, setCurrency] = React.useState("PKR");
  const [market, setMarket] = React.useState("PK");
  const { toast } = useToast();

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => pyFetch<SettingsInfo>("/api/v1/settings"),
  });

  React.useEffect(() => {
    if (settings) {
      setCurrency(settings.currency);
      setMarket(settings.market);
    }
  }, [settings?.currency, settings?.market]);

  const create = useMutation({
    mutationFn: async () => {
      const product = await pyFetch<{ id: number }>("/api/v1/products", {
        method: "POST",
        body: JSON.stringify({ name, total_budget: Number(budget), description, currency, market }),
      });
      return pyFetch<{ job_id: string }>("/api/v1/analyses", {
        method: "POST",
        body: JSON.stringify({ product_id: product.id }),
      });
    },
    onSuccess: (data) => {
      toast({ title: "Analysis started", description: "The 7-step pipeline is running." });
      onStarted(data.job_id);
    },
  });

  const valid = name.trim().length >= 2 && Number(budget) > 0;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Analyze a product</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Only three inputs are required. AdPilot infers everything else — and lets you correct its
          assumptions later.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Product &amp; budget</CardTitle>
          <CardDescription>
            Example: Premium Cricket Bat · PKR 50,000 · optional description
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="name">Product name *</Label>
            <Input
              id="name" placeholder="e.g. Premium Cricket Bat" value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="budget">Total advertising budget *</Label>
              <Input
                id="budget" type="number" min={1} placeholder="e.g. 50000" value={budget}
                onChange={(e) => setBudget(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Currency</Label>
              <Select value={currency} onValueChange={setCurrency}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(settings?.supported_currencies ?? ["PKR"]).map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label>Market</Label>
            <Select value={market} onValueChange={setMarket}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {(settings?.supported_markets ?? ["PK"]).map((m) => (
                  <SelectItem key={m} value={m}>{m}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="desc">Description (optional)</Label>
            <Textarea
              id="desc" rows={3} value={description}
              placeholder="Anything that helps: features, price point, who it is for…"
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {create.isError ? <ErrorNote message={String(create.error)} /> : null}

          <div className="flex flex-wrap gap-2 border-t pt-4">
            <span className="w-full text-xs text-muted-foreground">Try an example:</span>
            {EXAMPLES.map((ex) => (
              <Button
                key={ex.name} type="button" size="sm" variant="secondary"
                onClick={() => { setName(ex.name); setBudget(String(ex.budget)); setDescription(ex.description); }}
              >
                {ex.name}
              </Button>
            ))}
          </div>

          <Button
            className="w-full" size="lg" disabled={!valid || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
            Run AI analysis &amp; optimization
          </Button>
          <p className="text-center text-[11px] text-muted-foreground">
            Pipeline: understand product → infer audience → research YouTube → fetch ad history →
            analyze performance → optimize budget → generate recommendation
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
