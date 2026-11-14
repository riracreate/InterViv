import React from 'react';

/**
 * What an interview will actually ask, from the server's own plan: questions
 * per confirmed skill, skills the budget cannot reach, and skills without
 * scored content. Shown before a start button.
 *
 * `scope` comes from `summarizePlannedScope` (lib/practiceBuilder); nothing is
 * rendered without one. `notCoveredHint` replaces the advice after the list
 * of skills that get no question, for launches with a fixed question budget.
 */
export default function PlannedScope({ scope, notCoveredHint = 'Add questions or remove skills.' }) {
  if (!scope) return null;
  const plural = (n) => `${n} question${n === 1 ? '' : 's'}`;
  return (
    <div
      data-testid="planned-scope"
      role="status"
      className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3"
    >
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-ink-muted)]">
        Planned scope · {plural(scope.questions)}
      </p>
      <ul className="mt-2 space-y-1 text-sm text-[var(--color-ink)]">
        {scope.skills.map((item, index) => (
          <li key={`${item.skill}-${index}`} className={item.available ? '' : 'text-[var(--color-danger)]'}>
            <span className="font-medium">{item.skill}</span> — {plural(item.questions)}{' '}
            <span className={item.available ? 'text-[var(--color-ink-muted)]' : ''}>({item.note})</span>
          </li>
        ))}
      </ul>
      {scope.notCovered.length > 0 && (
        <p className="mt-2 text-sm text-[var(--color-danger)]" data-testid="planned-scope-not-covered">
          Not covered within {plural(scope.questions)}: {scope.notCovered.join(', ')}. {notCoveredHint}
        </p>
      )}
      {scope.unavailable.length > 0 && (
        <p className="mt-2 text-sm text-[var(--color-danger)]" data-testid="planned-scope-unavailable">
          Not enough scored questions for {scope.unavailable.join(', ')}. Remove {scope.unavailable.length === 1 ? 'it' : 'them'} to start.
        </p>
      )}
    </div>
  );
}
