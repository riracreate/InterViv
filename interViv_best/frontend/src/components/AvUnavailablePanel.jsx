import React from 'react';
import { avStateLabel } from '../lib/avStates';

/**
 * Distinct, reachable AV unavailable panels. Never shows a speech score.
 */
export default function AvUnavailablePanel({ state, detail = '', onRetry = null }) {
  if (!state) return null;
  return (
    <div
      data-testid={`av-state-${state}`}
      data-av-state={state}
      className="rounded-xl border border-amber-500/40 bg-amber-50 px-4 py-3 text-sm text-amber-950"
      style={{ fontFamily: "var(--font-body)" }}
    >
      <div className="font-medium">{avStateLabel(state)}</div>
      {detail ? <p className="mt-1 text-amber-900/80">{detail}</p> : null}
      <p className="mt-2 text-xs text-amber-900/70">
        No speech score is recorded for this state. Unavailable audio does not
        contribute zero to readiness.
      </p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg bg-amber-900 px-3 py-1.5 text-xs font-medium text-white"
        >
          Retry capture
        </button>
      ) : null}
    </div>
  );
}
