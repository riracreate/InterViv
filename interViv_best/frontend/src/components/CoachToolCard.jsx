import React from 'react';
import { toolCardView } from '../lib/coachChat.js';

export default function CoachToolCard({ proposal, busy = false, onConfirm, onCancel }) {
  const view = toolCardView(proposal);
  if (!view) return null;
  return (
    <section
      className="mt-3 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-4"
      data-testid="coach-tool-card"
    >
      <h3 className="text-sm font-semibold">{view.title}</h3>
      <ul className="mt-2 space-y-1 text-sm text-[var(--color-ink-muted)]">
        {view.lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {view.note && (
        <p className="mt-2 text-xs text-[var(--color-ink-muted)]" data-testid="coach-explain-note">
          {view.note}
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={busy}
          className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          data-testid="coach-tool-confirm"
          onClick={() => onConfirm?.(proposal)}
        >
          {view.confirmLabel}
        </button>
        <button
          type="button"
          disabled={busy}
          className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-sm font-semibold"
          data-testid="coach-tool-cancel"
          onClick={() => onCancel?.()}
        >
          Cancel
        </button>
      </div>
    </section>
  );
}
