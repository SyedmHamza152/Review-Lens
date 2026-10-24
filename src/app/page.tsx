"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { RiFooter, RiHeader } from "@/components/reviewintel/chrome";
import { DashboardView } from "@/components/reviewintel/dashboard";
import { HomeView } from "@/components/reviewintel/home-view";
import { ProgressView } from "@/components/reviewintel/progress-view";
import { ensureBackend } from "@/lib/pyapi";

type View = { name: "home" } | { name: "progress"; jobId: string } | { name: "dashboard"; jobId: string };

function parseHash(): View {
  if (typeof window === "undefined") return { name: "home" };
  const m = window.location.hash.match(/^#\/(job|progress)\/([0-9a-f-]{36})$/i);
  if (m) {
    return m[1] === "progress"
      ? { name: "progress", jobId: m[2] }
      : { name: "dashboard", jobId: m[2] };
  }
  return { name: "home" };
}

export default function Page() {
  const [view, setView] = useState<View>(() => parseHash());

  useEffect(() => {
    const onHash = () => setView(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = useCallback((next: View) => {
    const hash =
      next.name === "home" ? "" : `#/${next.name === "progress" ? "progress" : "job"}/${next.jobId}`;
    if (window.location.hash !== hash) {
      history.replaceState(null, "", hash ? `/${hash}` : window.location.pathname);
    }
    setView(next);
  }, []);

  // Ensure the Python backend is up before enabling search (idempotent).
  const { data: health } = useQuery({
    queryKey: ["ensure-backend"],
    queryFn: ensureBackend,
    staleTime: 30_000,
  });

  const backendOk = !!health?.healthy;

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <RiHeader
        backendOk={backendOk}
        productName={view.name !== "home" ? view.jobId : undefined}
        onHome={() => go({ name: "home" })}
      />

      <main className="flex-1">
        {view.name === "home" ? (
          <HomeView
            backendOk={backendOk}
            onSearch={(jobId) => go({ name: "progress", jobId })}
          />
        ) : view.name === "progress" ? (
          <ProgressView
            jobId={view.jobId}
            onOpenReport={() => go({ name: "dashboard", jobId: view.jobId })}
          />
        ) : (
          <DashboardView jobId={view.jobId} />
        )}
      </main>

      <RiFooter />
    </div>
  );
}
