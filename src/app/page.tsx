"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { AnalysisView } from "@/components/adpilot/analysis-view";
import { AudienceView } from "@/components/adpilot/audience-view";
import { BigDataView } from "@/components/adpilot/bigdata-view";
import { CampaignsView } from "@/components/adpilot/campaigns-view";
import { CompetitorsView } from "@/components/adpilot/competitors-view";
import { DashboardView } from "@/components/adpilot/dashboard-view";
import { LandingView } from "@/components/adpilot/landing-view";
import { AllocationView } from "@/components/adpilot/allocation-view";
import { MlLabView } from "@/components/adpilot/mllab-view";
import { ProgressView } from "@/components/adpilot/progress-view";
import { ReportsView } from "@/components/adpilot/reports-view";
import { SettingsView } from "@/components/adpilot/settings-view";
import { MobileNav, Sidebar, Topbar, type ViewKey } from "@/components/adpilot/shell";
import { ensureBackend, pyFetch } from "@/lib/pyapi";
import type { Analysis } from "@/lib/types";

type LatestAnalysis = Partial<Analysis> & { empty?: boolean; id?: number };

type View =
  | { name: "landing" }
  | { name: "analyze" }
  | { name: "progress"; jobId: string }
  | { name: "app"; key: ViewKey };

function parseHash(): View {
  if (typeof window === "undefined") return { name: "landing" };
  const h = window.location.hash.replace(/^#\/?/, "");
  const progress = h.match(/^progress\/([a-f0-9]{32})$/i);
  if (progress) return { name: "progress", jobId: progress[1] };
  const known = [
    "dashboard", "allocation", "campaigns", "audience", "competitors",
    "bigdata", "ml", "reports", "settings", "analyze",
  ];
  if (known.includes(h)) return h === "analyze" ? { name: "analyze" } : { name: "app", key: h as ViewKey };
  return { name: "landing" };
}

const APP_VIEWS: ViewKey[] = [
  "dashboard", "allocation", "campaigns", "audience", "competitors",
  "bigdata", "ml", "reports", "settings",
];

export default function Page() {
  const [view, setView] = useState<View>(() => parseHash());
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    const onHash = () => setView(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = useCallback((next: View) => {
    const hash =
      next.name === "landing" ? "" :
      next.name === "analyze" ? "#/analyze" :
      next.name === "progress" ? `#/progress/${next.jobId}` :
      `#/${next.key}`;
    if (window.location.hash !== hash) {
      history.replaceState(null, "", `${window.location.pathname}${hash}`);
    }
    setView(next);
  }, []);

  // Ensure the Python backend is up (idempotent) before enabling the app.
  const { data: health } = useQuery({
    queryKey: ["ensure-backend"],
    queryFn: ensureBackend,
    refetchInterval: (q) => (q.state.data?.healthy ? false : 3000),
    staleTime: 10_000,
  });
  const backendOk = !!health?.healthy;

  // Active analysis (latest by default)
  const { data: latest } = useQuery({
    queryKey: ["latest-analysis"],
    queryFn: () => pyFetch<LatestAnalysis>("/api/v1/analyses/latest"),
    enabled: backendOk,
    retry: false,
    staleTime: 30_000,
  });
  const active = analysisId && latest?.id === analysisId ? latest : (latest && !latest.empty ? latest : null);
  const activeId = analysisId ?? (latest && !latest.empty ? latest.id : null);

  const onAnalysisDone = useCallback(
    (newId: number) => {
      setAnalysisId(newId);
      go({ name: "app", key: "dashboard" });
      toast({ title: "Analysis complete", description: "Budget recommendation is ready." });
      // refresh latest-analysis
      window.dispatchEvent(new CustomEvent("adpilot:analysis-done"));
    },
    [go, toast],
  );

  useEffect(() => {
    const handler = () => {
      // force react-query refetch of latest analysis
      fetch("/api/py-health").catch(() => undefined);
    };
    window.addEventListener("adpilot:analysis-done", handler);
    return () => window.removeEventListener("adpilot:analysis-done", handler);
  }, []);

  const showChrome = view.name === "app" || view.name === "progress" || view.name === "analyze";
  const currentKey: ViewKey = view.name === "app" ? view.key : "dashboard";

  return (
    <div className="flex min-h-screen">
      {showChrome ? (
        <Sidebar current={currentKey} onNewAnalysis={() => go({ name: "analyze" })} />
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col">
        {showChrome ? (
          <Topbar
            backendOk={backendOk}
            productName={active?.product?.name}
            budgetLabel={
              active?.product
                ? `${active.product.currency} ${active.product.total_budget.toLocaleString()}`
                : undefined
            }
            onHome={() => go({ name: "landing" })}
            mobileNav={<MobileNav current={currentKey} onNewAnalysis={() => go({ name: "analyze" })} />}
          />
        ) : null}
        <main className="flex-1">
          {view.name === "landing" ? (
            <LandingView
              backendOk={backendOk}
              hasAnalysis={!!latest}
              onStart={() => go({ name: "analyze" })}
              onOpenDashboard={() => go({ name: "app", key: "dashboard" })}
            />
          ) : view.name === "analyze" ? (
            <AnalysisView onStarted={(jobId) => go({ name: "progress", jobId })} />
          ) : view.name === "progress" ? (
            <ProgressView jobId={view.jobId} onDone={onAnalysisDone} />
          ) : (
            <AppViews
              viewKey={view.key}
              analysisId={activeId ?? null}
              backendOk={backendOk}
              onAnalysisChanged={(id) => setAnalysisId(id)}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function AppViews({
  viewKey,
  analysisId,
  backendOk,
  onAnalysisChanged,
}: {
  viewKey: ViewKey;
  analysisId: number | null;
  backendOk: boolean;
  onAnalysisChanged: (id: number) => void;
}) {
  switch (viewKey) {
    case "allocation":
      return <AllocationView analysisId={analysisId} />;
    case "campaigns":
      return <CampaignsView />;
    case "audience":
      return <AudienceView analysisId={analysisId} />;
    case "competitors":
      return <CompetitorsView analysisId={analysisId} />;
    case "bigdata":
      return <BigDataView />;
    case "ml":
      return <MlLabView />;
    case "reports":
      return <ReportsView analysisId={analysisId} />;
    case "settings":
      return <SettingsView />;
    default:
      return <DashboardView analysisId={analysisId} backendOk={backendOk} />;
  }
}
