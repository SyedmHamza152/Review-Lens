"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { CheckCircle2, Database, KeyRound, Link2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { CardsSkeleton, DataBadge, ErrorNote, SectionTitle } from "@/components/adpilot/bits";
import { pyFetch, pyUrl } from "@/lib/pyapi";
import type { Health, OAuthStatus, SettingsInfo } from "@/lib/types";

export function SettingsView() {
  const qc = useQueryClient();
  const { toast } = useToast();

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => pyFetch<SettingsInfo>("/api/v1/settings"),
  });
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => pyFetch<Health>("/api/v1/health"),
    refetchInterval: 20_000,
  });
  const { data: oauth } = useQuery({
    queryKey: ["oauth-status"],
    queryFn: () => pyFetch<OAuthStatus>("/api/v1/oauth/google/status"),
  });

  const [currency, setCurrency] = React.useState<string | null>(null);
  const [market, setMarket] = React.useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      pyFetch("/api/v1/settings", {
        method: "PUT",
        body: JSON.stringify({ currency: currency ?? settings?.currency, market: market ?? settings?.market }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      toast({ title: "Settings saved" });
    },
  });

  const seedDemo = useMutation({
    mutationFn: () => pyFetch("/api/v1/demo/seed", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analytics"] });
      toast({ title: "Demo data re-seeded", description: "12 labeled synthetic campaigns" });
    },
  });

  const connectGoogle = useMutation({
    mutationFn: async () => {
      const r = await pyFetch<{ authorization_url: string }>("/api/v1/oauth/google/start");
      window.open(r.authorization_url, "_blank", "noopener");
      return r;
    },
    onSuccess: () => {
      toast({
        title: "Google authorization opened",
        description: "Complete consent in the new tab. Register the redirect URI first (shown below).",
      });
    },
    onError: (e) => toast({ title: "Cannot start OAuth", description: String(e).slice(0, 160) }),
  });

  const testConnection = useMutation({
    mutationFn: () => pyFetch<{ ok: boolean; status: string; detail?: string }>("/api/v1/oauth/google/test-connection", { method: "POST" }),
    onSuccess: (d) => {
      toast({
        title: d.ok ? "Google Ads connection works" : `Connection failed: ${d.status}`,
        description: d.ok ? "Live reporting is available." : d.detail?.slice(0, 140),
      });
    },
  });

  if (isLoading) return <div className="p-4 lg:p-6"><CardsSkeleton rows={2} /></div>;

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Connection status, market preferences and demo data.</p>
      </div>

      {/* API status */}
      <Card>
        <CardHeader className="pb-2">
          <SectionTitle title="API connection status" desc="Honest, live-checked status — no simulated success states." />
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <StatusRow
            ok={!!health?.youtube.configured}
            title="YouTube Data API v3"
            detail={health?.youtube.configured ? `Configured · ${health.youtube.quota_used_process} quota units used this process` : "Set YOUTUBE_API_KEY in backend/.env"}
          />
          <StatusRow
            ok={!!health?.google_ads.configured}
            title="Google Ads API"
            detail={health?.google_ads.configured
              ? "All env vars present — run a test connection"
              : `Missing: ${health?.google_ads.missing.join("; ") || "—"}`}
          />
          <StatusRow
            ok={!!health?.google_oauth.configured}
            title="Google OAuth client"
            detail={health?.google_oauth.configured ? "Client id/secret configured" : "Set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET"}
          />
          <StatusRow
            ok={health?.llm.engine === "ollama"}
            title="LLM engine (optional)"
            detail={health?.llm.engine === "ollama" ? `Ollama: ${health.llm.model}` : "Ollama not detected — deterministic rule engine active (by design)"}
          />
          <StatusRow ok={health?.database === "ok"} title="Database" detail={health?.database === "ok" ? "Connected" : "Error"} />
          <StatusRow ok title="Task queue" detail={`${health?.task_queue ?? "inline"} (Celery+Redis optional via docker-compose)`} />
        </CardContent>
      </Card>

      {/* Google connection */}
      <Card>
        <CardHeader className="pb-2">
          <SectionTitle
            title="Google account connection"
            desc="OAuth 2.0 (offline access) links your Google account for Google Ads reporting. The refresh token is stored encrypted and never leaves the backend."
          />
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            {oauth?.connected ? (
              <span className="inline-flex items-center gap-1.5 text-sm text-emerald-300">
                <CheckCircle2 className="h-4 w-4" /> Connected{oauth.google_email ? ` as ${oauth.google_email}` : ""}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <XCircle className="h-4 w-4 text-amber-400" /> Not connected
              </span>
            )}
            <Button size="sm" variant="outline" type="button" onClick={() => connectGoogle.mutate()} disabled={connectGoogle.isPending}>
              <Link2 className={"mr-2 h-3.5 w-3.5" + (connectGoogle.isPending ? " animate-pulse" : "")} /> Connect Google account
            </Button>
            <Button size="sm" variant="outline" onClick={() => testConnection.mutate()} disabled={testConnection.isPending}>
              <KeyRound className="mr-2 h-3.5 w-3.5" /> Test Google Ads connection
            </Button>
          </div>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            Redirect URI to register in Google Cloud Console: <code>{settings?.oauth.redirect_uri}</code>.
            Google Ads additionally requires an approved developer token (Basic access) — see README
            §Google Ads setup. {oauth?.ads.note}
          </p>
          {oauth?.scopes?.length ? (
            <div className="flex flex-wrap gap-1.5">
              {oauth.scopes.map((s) => (
                <code key={s} className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">{s}</code>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* preferences */}
      <Card>
        <CardHeader className="pb-2">
          <SectionTitle title="Preferences" desc="Currency and market defaults for new analyses." />
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Currency</p>
            <Select value={currency ?? settings?.currency ?? "PKR"} onValueChange={setCurrency}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(settings?.supported_currencies ?? []).map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Market</p>
            <Select value={market ?? settings?.market ?? "PK"} onValueChange={setMarket}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(settings?.supported_markets ?? []).map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>Save</Button>
        </CardContent>
      </Card>

      {/* demo data */}
      <Card>
        <CardHeader className="pb-2">
          <SectionTitle
            title="Demo data"
            desc="Synthetic campaign history keeps every feature functional without API credentials. It is always labeled SYNTHETIC DEMO DATA and never merged with live data."
          />
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button size="sm" variant="outline" onClick={() => seedDemo.mutate()} disabled={seedDemo.isPending}>
            <Database className="mr-2 h-3.5 w-3.5" /> Re-seed demo campaigns
          </Button>
          <DataBadge label="SYNTHETIC DEMO DATA" />
        </CardContent>
      </Card>
    </div>
  );
}

function StatusRow({ ok, title, detail }: { ok: boolean; title: string; detail: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg border bg-secondary/30 p-3">
      {ok ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
      ) : (
        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
      )}
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{detail}</p>
      </div>
    </div>
  );
}
