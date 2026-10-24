"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import type { Report } from "@/lib/types";
import { AlertTriangle, Bot, Loader2, Send, User } from "lucide-react";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  insufficient?: boolean;
}

const SUGGESTED = [
  "Is this product worth buying?",
  "What are its biggest disadvantages?",
  "Which platform has the most positive reviews?",
  "What do customers complain about most?",
  "Are customers complaining about fake or defective units?",
  "Summarize the Roman Urdu reviews",
  "What should I check before purchasing?",
];

export function AssistantTab({ jobId, report }: { jobId: string; report: Report }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const chat = useMutation({
    mutationFn: async (history: ChatMsg[]) => {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jobId,
          question: history[history.length - 1]?.content ?? "",
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.error ?? `Chat failed (${res.status})`);
      }
      return (await res.json()) as { answer: string; insufficient?: boolean };
    },
    onSuccess: (data) => {
      setMessages((m) => [...m, { role: "assistant", content: data.answer, insufficient: data.insufficient }]);
    },
    onError: (e: Error) => {
      toast({ title: "Assistant unavailable", description: e.message, variant: "destructive" });
      setMessages((m) => [...m, {
        role: "assistant",
        content: "Sorry, the assistant could not answer just now. Please try again.",
      }]);
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, chat.isPending]);

  const send = (text: string) => {
    const q = text.trim();
    if (!q || chat.isPending) return;
    const next: ChatMsg[] = [...messages, { role: "user", content: q }];
    setMessages(next);
    setInput("");
    chat.mutate(next);
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
      <Card className="flex min-h-[520px] flex-col">
        <CardContent className="flex flex-1 flex-col gap-3 p-4">
          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto rounded-lg bg-muted/20 p-3 max-h-[60vh]">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 py-10 text-center">
                <span className="flex size-11 items-center justify-center rounded-full bg-primary/10">
                  <Bot className="size-6 text-primary" />
                </span>
                <p className="text-sm font-medium">Ask about the collected reviews</p>
                <p className="max-w-sm text-xs text-muted-foreground">
                  Answers are grounded strictly in the {report.totals.analyzed} analyzed
                  comments for “{report.job.product_name}”. If the data is insufficient
                  to answer reliably, the assistant says so instead of inventing opinions.
                </p>
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : ""}`}>
                  {m.role === "assistant" ? (
                    <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
                      <Bot className="size-4 text-primary" />
                    </span>
                  ) : null}
                  <div
                    className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                      m.role === "user"
                        ? "rounded-br-sm bg-primary text-primary-foreground"
                        : m.insufficient
                          ? "rounded-bl-sm border border-amber-500/40 bg-amber-500/10"
                          : "rounded-bl-sm border bg-background"
                    }`}
                  >
                    {m.insufficient ? <AlertTriangle className="mb-1 size-3.5 text-amber-600" /> : null}
                    {m.content}
                  </div>
                  {m.role === "user" ? (
                    <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-muted">
                      <User className="size-4" />
                    </span>
                  ) : null}
                </div>
              ))
            )}
            {chat.isPending ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> Analyzing review data…
              </div>
            ) : null}
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); send(input); }}
            className="flex gap-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. What problems do customers report most often?"
              disabled={chat.isPending}
              aria-label="Ask the research assistant"
            />
            <Button type="submit" size="icon" disabled={chat.isPending || !input.trim()} aria-label="Send">
              <Send className="size-4" />
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Suggested questions
        </p>
        {SUGGESTED.map((s) => (
          <button
            key={s}
            onClick={() => send(s)}
            disabled={chat.isPending}
            className="w-full rounded-lg border bg-background px-3 py-2 text-left text-xs leading-snug transition-colors hover:border-primary/40 hover:bg-primary/5 disabled:opacity-50"
          >
            {s}
          </button>
        ))}
        <p className="rounded-lg bg-muted/40 px-3 py-2 text-[10px] leading-relaxed text-muted-foreground">
          The assistant only uses the collected and analyzed data shown in this report and
          cites platforms where possible. It cannot access any other data and will not
          invent statistics.
        </p>
      </div>
    </div>
  );
}
