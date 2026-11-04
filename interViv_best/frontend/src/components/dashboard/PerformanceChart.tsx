import React from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { GaugeCircle } from "lucide-react";

type Point = { t: string; value: number };

function mergeSeries(
  difficulty: Point[],
  score: Point[],
): Array<{ t: string; difficulty?: number; score?: number }> {
  const byRound = new Map<string, { t: string; difficulty?: number; score?: number }>();
  for (const d of difficulty) byRound.set(d.t, { t: d.t, difficulty: d.value });
  for (const s of score) {
    const current = byRound.get(s.t) ?? { t: s.t };
    current.score = s.value;
    byRound.set(s.t, current);
  }
  return Array.from(byRound.values());
}

function ChartTooltip(props: any) {
  if (!props.active || !props.payload?.length) return null;
  const payload = props.payload as Array<{ name: string; value: number }>;
  const round = props.label as string;
  const score = payload.find((p) => p.name === "score")?.value;
  const difficulty = payload.find((p) => p.name === "difficulty")?.value;

  return (
    <div className="glass-panel rounded-2xl px-3 py-2 text-xs text-[var(--color-ink)]">
      <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
        {round}
      </div>
      <div className="mt-1 grid gap-1 text-[12px]" style={{ fontFamily: "var(--font-body)" }}>
        <div className="flex items-center justify-between gap-6">
          <span className="text-[var(--color-ink-muted)]">Score</span>
          <span className="font-semibold text-[var(--color-accent)]">{typeof score === "number" ? `${Math.round(score)}%` : "--"}</span>
        </div>
        <div className="flex items-center justify-between gap-6">
          <span className="text-[var(--color-ink-muted)]">Difficulty</span>
          <span className="font-semibold text-indigo-700">{typeof difficulty === "number" ? Math.round(difficulty) : "--"}</span>
        </div>
      </div>
    </div>
  );
}

export function PerformanceChart(props: {
  finalRating: number;
  difficulty: Point[];
  score: Point[];
}) {
  const data = mergeSeries(props.difficulty, props.score);

  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--color-surface)] text-[var(--color-ink)]">
            <GaugeCircle className="h-4 w-4" />
          </div>
          <div>
            <div className="text-2xl font-normal italic tracking-tight sm:text-3xl" style={{ fontFamily: "var(--font-display)" }}>
              Performance Trend
            </div>
            <p className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
              Round-wise score progression against adaptive difficulty.
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 backdrop-blur-xl">
          <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
            Final Elo
          </div>
          <div className="mt-0.5 text-xl font-semibold text-[var(--color-accent)]" style={{ fontFamily: "var(--font-body)" }}>
            {props.finalRating}
          </div>
        </div>
      </div>

      <div className="mt-5 h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 10, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="#cbd5e1" vertical={false} />
            <XAxis
              dataKey="t"
              tick={{ fill: "#475569", fontSize: 12, fontFamily: "var(--font-body)" }}
              axisLine={{ stroke: "#cbd5e1" }}
              tickLine={{ stroke: "#cbd5e1" }}
            />
            <YAxis
              tick={{ fill: "#64748b", fontSize: 11, fontFamily: "var(--font-body)" }}
              axisLine={{ stroke: "#cbd5e1" }}
              tickLine={{ stroke: "#cbd5e1" }}
              width={36}
            />
            <Tooltip content={<ChartTooltip />} />
            <Line
              type="monotone"
              dataKey="score"
              name="score"
              stroke="rgba(34,211,238,0.95)"
              strokeWidth={2.6}
              dot={false}
              activeDot={{ r: 5, fill: "rgba(34,211,238,1)", stroke: "transparent" }}
            />
            <Line
              type="monotone"
              dataKey="difficulty"
              name="difficulty"
              stroke="rgba(129,140,248,0.8)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

