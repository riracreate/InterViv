import React from "react";
import { motion } from "motion/react";
import { Clock, Calendar, BriefcaseBusiness, Target } from "lucide-react";

function StatPill(props: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 backdrop-blur-xl">
      <div className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--color-surface)] text-[var(--color-ink)]">
        {props.icon}
      </div>
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
          {props.label}
        </div>
        <div className="truncate text-sm text-[var(--color-ink)]" style={{ fontFamily: "var(--font-body)" }}>
          {props.value}
        </div>
      </div>
    </div>
  );
}

function ScoreRing(props: {
  score: number | null;
  accentRingClass: string;
  accentTextClass: string;
}) {
  const radius = 46;
  const circumference = 2 * Math.PI * radius;
  const progress = props.score == null ? 0 : Math.max(0, Math.min(100, props.score));
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className="relative grid h-[140px] w-[140px] place-items-center">
      <div className={`absolute inset-0 rounded-full bg-gradient-to-b ${props.accentRingClass} blur-2xl opacity-60`} />
      <div className="absolute inset-[10px] rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] backdrop-blur-2xl shadow-[0_30px_90px_rgba(0,0,0,0.60)]" />

      <svg className="relative h-[120px] w-[120px] -rotate-90" viewBox="0 0 120 120">
        <circle
          cx="60"
          cy="60"
          r={radius}
          stroke="#cbd5e1"
          strokeWidth="10"
          fill="transparent"
        />
        <motion.circle
          cx="60"
          cy="60"
          r={radius}
          stroke="rgba(34,211,238,0.90)"
          strokeWidth="10"
          strokeLinecap="round"
          fill="transparent"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.15, ease: [0.2, 0.8, 0.2, 1] }}
          style={{
            filter: "drop-shadow(0 0 18px rgba(34,211,238,0.35))",
          }}
        />
      </svg>

      <div className="absolute inset-0 grid place-items-center">
        <div className="text-center">
          <div className={`text-4xl font-semibold ${props.accentTextClass}`} style={{ fontFamily: "var(--font-body)" }}>
            {props.score == null ? "—" : progress}
          </div>
          <div className="mt-0.5 text-[11px] uppercase tracking-[0.22em] text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
            Overall
          </div>
        </div>
      </div>
    </div>
  );
}

export function ScoreHero(props: {
  overallScore: number | null;
  gradeLabel: string;
  deltaLabel: string;
  sessionTitle: string;
  role: string;
  dateLabel: string;
  durationLabel: string;
  skillFocus: string;
  accentRingClass: string;
  accentTextClass: string;
}) {
  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-7">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div
              className="text-3xl sm:text-4xl font-normal italic tracking-tight text-[var(--color-ink)]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Results Dashboard
            </div>
          </div>

          <p className="mt-2 max-w-2xl text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
            A premium snapshot of your performance—clarity, quality, and progression across an adaptive interview.
          </p>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatPill icon={<BriefcaseBusiness className="h-4 w-4" />} label="Session" value={`${props.sessionTitle} · ${props.role}`} />
            <StatPill icon={<Calendar className="h-4 w-4" />} label="Date" value={props.dateLabel} />
            <StatPill icon={<Clock className="h-4 w-4" />} label="Duration" value={props.durationLabel} />
            <StatPill icon={<Target className="h-4 w-4" />} label="Focus" value={props.skillFocus} />
          </div>
        </div>

        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center lg:flex-col lg:items-end">
          <ScoreRing score={props.overallScore} accentRingClass={props.accentRingClass} accentTextClass={props.accentTextClass} />

          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 backdrop-blur-xl">
            <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
              Verdict
            </div>
            <div className="mt-0.5 text-sm text-[var(--color-ink)]" style={{ fontFamily: "var(--font-body)" }}>
              <span className="font-semibold text-[var(--color-ink)]">{props.gradeLabel}</span>{" "}
              <span className="text-[var(--color-ink-muted)]">·</span>{" "}
              <span className="text-[var(--color-ink-muted)]">{props.deltaLabel}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
