import React from "react";
import { CheckCircle2, XCircle } from "lucide-react";

type Item = { title: string; detail: string };

function Column(props: {
  tone: "good" | "bad";
  title: string;
  subtitle: string;
  items: Item[];
}) {
  const icon =
    props.tone === "good" ? (
      <CheckCircle2 className="h-4 w-4 text-emerald-700" />
    ) : (
      <XCircle className="h-4 w-4 text-rose-700" />
    );

  const glow =
    props.tone === "good"
      ? "from-emerald-400/15 via-transparent to-transparent"
      : "from-rose-400/15 via-transparent to-transparent";

  return (
    <div className="relative overflow-hidden rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 backdrop-blur-2xl">
      <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${glow}`} />
      <div className="relative flex items-start gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--color-surface)]">{icon}</div>
        <div className="min-w-0">
          <div
            className="text-xl sm:text-2xl font-normal italic tracking-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {props.title}
          </div>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
            {props.subtitle}
          </p>
        </div>
      </div>

      <div className="relative mt-5 grid gap-3">
        {props.items.map((it) => (
          <div key={it.title} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <div className="text-sm font-semibold text-[var(--color-ink)]" style={{ fontFamily: "var(--font-body)" }}>
              {it.title}
            </div>
            <div className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
              {it.detail}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function StrengthsWeaknesses(props: { strengths: Item[]; weaknesses: Item[] }) {
  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div
            className="text-2xl sm:text-3xl font-normal italic tracking-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Strengths & Weaknesses
          </div>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
            High-signal highlights—what to keep, and what to tighten next session.
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <Column
          tone="good"
          title="Strengths"
          subtitle="Repeat these patterns—they’re working."
          items={props.strengths}
        />
        <Column
          tone="bad"
          title="Weaknesses"
          subtitle="Small fixes that unlock big score gains."
          items={props.weaknesses}
        />
      </div>
    </section>
  );
}

