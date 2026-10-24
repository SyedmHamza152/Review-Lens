"use client";

import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { AspectStat, DistributionItem, LanguageRow, TrendPoint } from "@/lib/types";

export const SENTIMENT_COLORS: Record<string, string> = {
  positive: "#10b981",
  negative: "#ef4444",
  neutral: "#94a3b8",
  mixed: "#f59e0b",
};

const LANG_COLORS: Record<string, string> = {
  english: "#0d9488",
  roman_urdu: "#14b8a6",
  urdu: "#059669",
  mixed: "#84cc16",
};

const tooltipStyle = {
  borderRadius: 8,
  border: "1px solid hsl(var(--border))",
  fontSize: 12,
  background: "hsl(var(--popover))",
  color: "hsl(var(--popover-foreground))",
};

export function SentimentDonut({ data }: { data: DistributionItem[] }) {
  const total = data.reduce((a, b) => a + b.count, 0);
  return (
    <div className="relative h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="count" nameKey="label" innerRadius={62} outerRadius={90}
            paddingAngle={2} strokeWidth={0}>
            {data.map((d) => (
              <Cell key={d.label} fill={SENTIMENT_COLORS[d.label]} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold tabular-nums">{total}</span>
        <span className="text-xs text-muted-foreground">comments</span>
      </div>
    </div>
  );
}

export function PlatformStackedBar({
  rows,
  height = 340,
}: {
  rows: { platform_name: string; positive_pct: number; negative_pct: number; neutral_pct: number; mixed_pct: number }[];
  height?: number;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }} barCategoryGap={10}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
          <YAxis type="category" dataKey="platform_name" width={92} tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="positive_pct" name="Positive" stackId="s" fill={SENTIMENT_COLORS.positive} radius={[0, 0, 0, 0]} />
          <Bar dataKey="negative_pct" name="Negative" stackId="s" fill={SENTIMENT_COLORS.negative} />
          <Bar dataKey="mixed_pct" name="Mixed" stackId="s" fill={SENTIMENT_COLORS.mixed} />
          <Bar dataKey="neutral_pct" name="Neutral" stackId="s" fill={SENTIMENT_COLORS.neutral} radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function VolumeBar({ rows }: { rows: { name: string; count: number }[] }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ left: -18, right: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-35} textAnchor="end" height={58} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="count" name="Comments analyzed" fill="#0d9488" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TrendLine({ data }: { data: TrendPoint[] }) {
  if (data.length < 2) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
        Not enough dated reviews yet to draw a trend.
      </div>
    );
  }
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ left: -14, right: 10, top: 6 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="period" tick={{ fontSize: 10 }} />
          <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} ticks={[-1, -0.5, 0, 0.5, 1]} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line type="monotone" dataKey="score" name="Avg sentiment (-1..1)" stroke="#0d9488"
            strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AspectChart({ aspects }: { aspects: AspectStat[] }) {
  const data = aspects
    .filter((a) => a.positive + a.negative > 0)
    .slice(0, 8)
    .map((a) => ({
      name: a.label.length > 22 ? a.label.slice(0, 21) + "…" : a.label,
      Positive: a.positive,
      Negative: -a.negative,
      scope: a.scope,
    }));
  if (!data.length) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
        No aspect mentions detected yet.
      </div>
    );
  }
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 20 }} stackOffset="sign">
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
          <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
          <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="Negative" fill={SENTIMENT_COLORS.negative} stackId="a" radius={[3, 0, 0, 3]} />
          <Bar dataKey="Positive" fill={SENTIMENT_COLORS.positive} stackId="a" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function LanguagePie({ data }: { data: LanguageRow[] }) {
  const mapped = data.map((d) => ({
    name: d.language === "mixed" ? "mixed (EN+RU/UR)" : d.language,
    value: d.count,
    pct: d.pct,
    fill: LANG_COLORS[d.language] ?? "#94a3b8",
  }));
  const legend = mapped.length ? mapped : [];
  return (
    <div className="flex h-64 flex-col sm:flex-row sm:items-center">
      <ResponsiveContainer width="55%" height="100%">
        <PieChart>
          <Pie data={mapped} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70}
            paddingAngle={2} strokeWidth={0}>
            {mapped.map((d) => (
              <Cell key={d.name} fill={d.fill} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
      <ul className="flex-1 space-y-1.5 pr-2">
        {legend.map((d) => (
          <li key={d.name} className="flex items-center gap-2 text-xs">
            <span aria-hidden className="size-2.5 rounded-full" style={{ background: d.fill }} />
            <span className="capitalize">{d.name.replace("_", " ")}</span>
            <span className="ml-auto tabular-nums text-muted-foreground">{d.pct}%</span>
          </li>
        ))}
        {!legend.length ? <li className="text-xs text-muted-foreground">No data.</li> : null}
      </ul>
    </div>
  );
}

export function SentimentByLanguageBar({ data }: { data: LanguageRow[] }) {
  const rows = data.map((d) => ({
    language: d.language.replace("roman_urdu", "roman urdu").replace("urdu", "urdu script")
      .replace("urdu script script", "urdu script"),
    Positive: d.positive,
    Negative: d.negative,
    Mixed: d.mixed,
    Neutral: d.neutral,
  }));
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ left: -20, right: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
          <XAxis dataKey="language" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="Positive" stackId="a" fill={SENTIMENT_COLORS.positive} />
          <Bar dataKey="Negative" stackId="a" fill={SENTIMENT_COLORS.negative} />
          <Bar dataKey="Mixed" stackId="a" fill={SENTIMENT_COLORS.mixed} />
          <Bar dataKey="Neutral" stackId="a" fill={SENTIMENT_COLORS.neutral} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
