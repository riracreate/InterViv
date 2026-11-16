import React from 'react';

export default function StagedLauncherCard({ busy = false, onStart }) {
  return <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5" aria-labelledby="quick-interview-title">
    <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">Guided interview · about 15 minutes</p>
    <h2 id="quick-interview-title" className="mt-2 text-xl font-semibold">Quick interview</h2>
    <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-ink-muted)]">Start with a warm-up, then two core questions on your selected skills. Behavioural questions are included when available. Feedback arrives after the interview; there is no practical round.</p>
    <button type="button" className="app-button app-button-primary mt-4" disabled={busy} onClick={onStart}>
      {busy ? 'Starting…' : 'Start Quick interview'}
    </button>
  </section>;
}
