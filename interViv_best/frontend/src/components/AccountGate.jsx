import React from 'react';
import { Link } from 'react-router-dom';

/** Shown until the signed-in account loads; failures stay on this page. */
export default function AccountGate({ error, onRetry }) {
  if (!error) {
    return <p className="text-sm text-[var(--color-ink-muted)]" role="status">Checking sign-in…</p>;
  }
  return (
    <div role="alert" className="max-w-md px-4 text-center" data-testid="account-load-error">
      <p className="text-sm text-[var(--color-ink)]">{error}</p>
      <div className="mt-4 flex justify-center gap-3">
        <button type="button" className="app-button app-button-primary" onClick={onRetry}>Try again</button>
        <Link to="/home" className="app-button">Home</Link>
      </div>
    </div>
  );
}
