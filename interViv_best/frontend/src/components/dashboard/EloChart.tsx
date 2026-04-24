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
import { TrendingUp } from "lucide-react";

type Point = { t: string; value: number };

function mergeSeries(
  a: Point[],
  b: Point[],
): Array<{ t: string; difficulty?: number; rating?: number }> {
  const byT = new Map<string, { t: string; difficulty?: number; rating?: number }>();
  for (const p of a) byT.set(p.t, { t: p.t, difficulty: p.value });
  for (const p of b) {
    const cur = byT.get(p.t) ?? { t: p.t };
    cur.rating = p.value;
    byT.set(p.t, cur);
  }
  return Array.from(byT.values());
}

function EloTooltip(props: any) {
  if (!props.active || !props.payload?.length) return null;
  const payload = props.payload as Array<{ name: string; value: number }>;
  const round = props.label as string;
  const difficulty = payload.find((p) => p.name === "difficulty")?.value;
  const rating = payload.find((p) => p.name === "rating")?.value;
  return (
    <div className="rounded-2xl border border-white/12 bg-black/70 px-3 py-2 text-xs text-white/90 backdrop-blur-2xl shadow-[0_18px_70px_rgba(0,0,0,0.65)]">
      <div className="text-[11px] uppercase tracking-[0.18em] text-white/50" style={{ fontFamily: "var(--font-body)" }}>
        {round}
      </div>
      <div className="mt-1 grid gap-1 text-[12px]" style={{ fontFamily: "var(--font-body)" }}>
        {typeof rating === "number" && (
          <div className="flex items-center justify-between gap-6">
            <span className="text-white/60">Elo</span>
            <span className="font-semibold text-cyan-100">{Math.round(rating)}</span>
          </div>
        )}
        {typeof difficulty === "number" && (
          <div className="flex items-center justify-between gap-6">
            <span className="text-white/60">Difficulty</span>
            <span className="font-semibold text-white/85">{Math.round(difficulty)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function EloChart(props: {
  finalRating: number;
  difficulty: Point[];
  rating: Point[];
}) {
  const data = mergeSeries(props.difficulty, props.rating);

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur-2xl shadow-[0_28px_90px_rgba(0,0,0,0.55)] sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/5 text-white/85">
            <TrendingUp className="h-4 w-4" />
          </div>
          <div>
            <div
              className="text-2xl sm:text-3xl font-normal italic tracking-tight"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Progress + Elo
            </div>
            <p className="mt-1 text-sm text-white/65" style={{ fontFamily: "var(--font-body)" }}>
              Difficulty progression with your final rating.
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/25 px-4 py-3 backdrop-blur-xl">
          <div className="text-[11px] uppercase tracking-[0.18em] text-white/45" style={{ fontFamily: "var(--font-body)" }}>
            Final Elo
          </div>
          <div className="mt-0.5 text-xl font-semibold text-cyan-100" style={{ fontFamily: "var(--font-body)" }}>
            {props.finalRating}
          </div>
        </div>
      </div>

      <div className="mt-5 h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
            <XAxis
              dataKey="t"
              tick={{ fill: "rgba(255,255,255,0.55)", fontSize: 12, fontFamily: "var(--font-body)" }}
              axisLine={{ stroke: "rgba(255,255,255,0.10)" }}
              tickLine={{ stroke: "rgba(255,255,255,0.10)" }}
            />
            <YAxis
              tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11, fontFamily: "var(--font-body)" }}
              axisLine={{ stroke: "rgba(255,255,255,0.10)" }}
              tickLine={{ stroke: "rgba(255,255,255,0.10)" }}
              width={34}
            />
            <Tooltip content={<EloTooltip />} />
            <Line
              type="monotone"
              dataKey="rating"
              name="rating"
              stroke="rgba(34,211,238,0.9)"
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 5, fill: "rgba(34,211,238,1)", stroke: "rgba(0,0,0,0)" }}
            />
            <Line
              type="monotone"
              dataKey="difficulty"
              name="difficulty"
              stroke="rgba(59,130,246,0.55)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 flex items-center gap-3 text-xs text-white/55" style={{ fontFamily: "var(--font-body)" }}>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-cyan-300/80 shadow-[0_0_18px_rgba(34,211,238,0.35)]" />
          Elo rating
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-blue-400/60" />
          Difficulty
        </div>
      </div>
    </section>
  );
}

