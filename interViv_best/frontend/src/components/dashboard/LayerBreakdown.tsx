import React from "react";
import { Shield, Layers, Cpu } from "lucide-react";

function LayerIcon(label: string) {
  if (label.toLowerCase().includes("1")) return <Layers className="h-4 w-4" />;
  if (label.toLowerCase().includes("2")) return <Shield className="h-4 w-4" />;
  return <Cpu className="h-4 w-4" />;
}

function ProgressBar(props: { value: number }) {
  const v = Math.max(0, Math.min(100, props.value));
  return (
    <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--color-surface)]">
      <div
        className="h-full rounded-full bg-gradient-to-r from-cyan-400/70 via-sky-400/70 to-blue-500/70 shadow-[0_0_22px_rgba(34,211,238,0.25)]"
        style={{ width: `${v}%` }}
      />
    </div>
  );
}

export function LayerBreakdown(props: {
  layers: Array<{ label: string; subtitle: string; score: number }>;
}) {
  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div
            className="text-2xl sm:text-3xl font-normal italic tracking-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Score Breakdown
          </div>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
            Three-layer deterministic scoring: content, answer quality, and classifier signal.
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4">
        {props.layers.map((l) => (
          <div key={l.label} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 backdrop-blur-xl">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--color-surface)] text-[var(--color-ink)]">
                  {LayerIcon(l.label)}
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.18em] text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
                    {l.label}
                  </div>
                  <div className="text-base text-[var(--color-ink)]" style={{ fontFamily: "var(--font-body)" }}>
                    {l.subtitle}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-semibold text-[var(--color-ink)]" style={{ fontFamily: "var(--font-body)" }}>
                  {Math.round(l.score)}%
                </div>
                <div className="text-xs text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
                  layer score
                </div>
              </div>
            </div>
            <ProgressBar value={l.score} />
          </div>
        ))}
      </div>
    </section>
  );
}
