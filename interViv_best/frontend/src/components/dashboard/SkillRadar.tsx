import React from "react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Eye } from "lucide-react";

type RadarDatum = { skill: string; value: number };

function RadarTooltip(props: any) {
  if (!props.active || !props.payload?.length) return null;
  const row = props.payload[0]?.payload as RadarDatum | undefined;
  if (!row) return null;
  return (
    <div className="rounded-2xl border border-white/12 bg-black/70 px-3 py-2 text-xs text-white/90 backdrop-blur-2xl shadow-[0_18px_70px_rgba(0,0,0,0.65)]">
      <div className="text-[11px] uppercase tracking-[0.18em] text-white/50" style={{ fontFamily: "var(--font-body)" }}>
        {row.skill}
      </div>
      <div className="mt-0.5 text-sm font-semibold text-cyan-100" style={{ fontFamily: "var(--font-body)" }}>
        {Math.round(row.value)}%
      </div>
    </div>
  );
}

export function SkillRadar(props: { data: RadarDatum[] }) {
  return (
    <section className="glass-panel relative overflow-hidden rounded-3xl p-5 sm:p-6">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-cyan-500/10 blur-[90px]" />
        <div className="absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-blue-500/10 blur-[90px]" />
      </div>

      <div className="relative flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/5 text-white/85">
              <Eye className="h-4 w-4" />
            </div>
            <div>
              <div
                className="text-2xl sm:text-3xl font-normal italic tracking-tight"
                style={{ fontFamily: "var(--font-display)" }}
              >
                Skill Radar
              </div>
              <p className="mt-1 text-sm text-white/65" style={{ fontFamily: "var(--font-body)" }}>
                Your strongest visual signal—multi-skill performance across the session.
              </p>
            </div>
          </div>
        </div>

        <div className="hidden sm:block text-right">
          <div className="text-xs uppercase tracking-[0.18em] text-white/45" style={{ fontFamily: "var(--font-body)" }}>
            Scale
          </div>
          <div className="text-sm text-white/75" style={{ fontFamily: "var(--font-body)" }}>
            0 → 100
          </div>
        </div>
      </div>

      <div className="relative mt-6 h-[320px] sm:h-[360px] lg:h-[420px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={props.data} outerRadius="72%">
            <PolarGrid stroke="rgba(255,255,255,0.10)" />
            <PolarAngleAxis
              dataKey="skill"
              tick={{ fill: "rgba(255,255,255,0.72)", fontSize: 12, fontFamily: "var(--font-body)" }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 10, fontFamily: "var(--font-body)" }}
              stroke="rgba(255,255,255,0.10)"
            />
            <Tooltip content={<RadarTooltip />} />
            <Radar
              dataKey="value"
              stroke="rgba(34,211,238,0.9)"
              fill="rgba(34,211,238,0.18)"
              strokeWidth={2}
              dot={{ r: 3, fill: "rgba(34,211,238,0.95)", stroke: "rgba(0,0,0,0)", strokeWidth: 0 }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

