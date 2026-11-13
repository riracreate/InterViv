import React from "react";

type FollowUpItem = {
  round: number;
  parentRound: number | null;
  question: string;
  answer: string;
  label: string;
  feedback: string;
};

/**
 * Follow-up questions the server placed outside the assessed report
 * (system-initiated or unscored). Never scored here, never charted.
 */
export function FollowUpSection({ items }: { items: FollowUpItem[] }) {
  if (!items.length) return null;
  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-6" aria-labelledby="report-follow-ups-heading"
      data-testid="report-follow-ups">
      <h2 id="report-follow-ups-heading" className="text-xl font-normal tracking-tight"
        style={{ fontFamily: "var(--font-display)" }}>
        Follow-up questions
      </h2>
      <p className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
        Not scored and not part of your assessment, charts or averages.
      </p>
      <ul className="mt-4 space-y-4">
        {items.map((item) => (
          <li key={item.round} className="rounded-2xl border border-[var(--color-border)] p-4">
            <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--color-ink-muted)]">
              <span className="rounded-full bg-black/[0.04] px-2.5 py-1 font-medium">{item.label}</span>
              {item.parentRound != null && <span>After question {item.parentRound}</span>}
            </div>
            <p className="mt-2 text-sm font-medium text-[var(--color-ink)]">{item.question}</p>
            {item.answer && <p className="mt-2 text-sm text-[var(--color-ink-muted)] whitespace-pre-wrap">{item.answer}</p>}
            {item.feedback && <p className="mt-2 text-xs text-[var(--color-ink-muted)]">{item.feedback}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
