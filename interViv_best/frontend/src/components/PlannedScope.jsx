import React from 'react';

/**
 * What an interview will actually ask, from the server's own plan: questions
 * per confirmed skill, then one notice for each kind of gap, because each
 * needs different advice.
 *
 *   not covered   warning  the question budget does not reach the skill
 *   no content    error    nothing offline is about the skill
 *   insufficient  error    some offline questions, fewer than planned
 *
 * `scope` comes from `summarizePlannedScope` (lib/practiceBuilder); nothing is
 * rendered without one. For a launch whose question count the candidate
 * cannot change (Jobs, Coach) pass `countFixed` and a `notCoveredHint`.
 * Notices use the shared `app-notice` classes so they look the same on
 * every page.
 */
export default function PlannedScope({
  scope,
  notCoveredHint = 'Add questions or remove skills.',
  countFixed = false,
}) {
  if (!scope) return null;
  const plural = (n) => `${n} question${n === 1 ? '' : 's'}`;
  const them = (list) => (list.length === 1 ? 'it' : 'them');
  const noContent = scope.noContent || [];
  const insufficient = scope.insufficient || [];
  const describeShort = (item) => (
    `${item.skill} has ${item.available} of ${item.planned} planned`
    + (item.sharedWith.length ? ` (shared with ${item.sharedWith.join(' and ')})` : '')
  );
  return (
    <div
      data-testid="planned-scope"
      role="status"
      className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3"
    >
      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-ink-muted)]">
        Planned scope · {plural(scope.questions)}
      </div>
      <ul className="mt-2 space-y-1 text-sm text-[var(--color-ink)]">
        {scope.skills.map((item, index) => (
          <li key={`${item.skill}-${index}`} className={item.available ? '' : 'app-text-error'}>
            <span className="font-medium">{item.skill}</span> — {plural(item.questions)}{' '}
            <span className={item.available ? 'text-[var(--color-ink-muted)]' : ''}>({item.note})</span>
          </li>
        ))}
      </ul>
      {scope.notCovered.length > 0 && (
        <div className="app-notice app-notice-warn" data-testid="planned-scope-not-covered">
          <strong>Not covered:</strong> {scope.notCovered.join(', ')}. Only {plural(scope.questions)}{' '}
          {scope.questions === 1 ? 'is' : 'are'} planned, so {scope.notCovered.length === 1 ? 'this skill gets' : 'these skills get'} none.{' '}
          {notCoveredHint}
        </div>
      )}
      {noContent.length > 0 && (
        <div className="app-notice app-notice-error" data-testid="planned-scope-no-content">
          <strong>No offline questions:</strong> {noContent.join(', ')}. Remove {them(noContent)}, or use live
          question generation where it is configured.
        </div>
      )}
      {insufficient.length > 0 && (
        <div className="app-notice app-notice-error" data-testid="planned-scope-insufficient">
          <strong>Not enough offline questions:</strong> {insufficient.map(describeShort).join('; ')}.{' '}
          {countFixed ? `Remove ${them(insufficient)}.` : `Lower the question count or remove ${them(insufficient)}.`}
        </div>
      )}
    </div>
  );
}
