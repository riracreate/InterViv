import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  fetchMe,
  fetchNotebook,
  fetchRetrySets,
  createRetrySet,
  deleteRetrySet,
  startRetrySet,
  fetchBookmarks,
  removeBookmark,
  fetchHint,
  fetchExplanation,
  fetchNextSteps,
  fetchDueReviews,
  fetchReviewSchedules,
  startDueReviews,
  saveInterviewState,
} from '../lib/api';
import AppNav from '../components/AppNav';
import AccountGate from '../components/AccountGate';
import { useAccountRetry } from '../lib/useAccountRetry';

/** Curated question hint: concept, schema, constructs or approach (no answers). */
export function HintView({ hint }) {
  if (!hint) return null;
  const tables = hint.tables || [];
  const lines = [
    ...(hint.checklist || []),
    ...(hint.constructs || []).map((c) => c.hint),
    ...(hint.approach || []).map((a) => (typeof a === 'string' ? a : `${a.topic}: ${a.hint}`)),
  ];
  return (
    <div className="mt-2 rounded border border-[var(--color-border)] bg-white p-2 text-xs" data-testid="learn-hint">
      <p>{hint.guidance}</p>
      {tables.length > 0 && (
        <p className="mt-1 text-[var(--color-ink-muted)]">
          Tables: {tables.map((t) => `${t.name}(${(t.columns || []).join(', ')})`).join(' · ')}
          {hint.relationships?.length ? ` — joins: ${hint.relationships.join(', ')}` : ''}
        </p>
      )}
      {lines.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-4">
          {lines.slice(0, 5).map((line) => <li key={line}>{line}</li>)}
        </ul>
      )}
    </div>
  );
}

/** Phase D+I learning hub: notebook, retry sets, spaced reviews, bookmarks. */
export default function Learn() {
  const navigate = useNavigate();
  const { accountError, accountAttempt, retryAccount, onAccountError } = useAccountRetry();
  const [authReady, setAuthReady] = useState(false);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });
  const [notebook, setNotebook] = useState(null);
  const [retrySets, setRetrySets] = useState([]);
  const [bookmarks, setBookmarks] = useState([]);
  const [nextSteps, setNextSteps] = useState(null);
  const [dueReviews, setDueReviews] = useState(null);
  const [allSchedules, setAllSchedules] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [retryName, setRetryName] = useState('');
  const [retryMax, setRetryMax] = useState(5);
  const [assistView, setAssistView] = useState({}); // entryKey -> {hint|explanation|error}

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        setAuthReady(true);
        const u = me.user || me;
        setNavUser({
          userId: u.id || u.user_id || null,
          roleId: u.target_role_id || null,
        });
      })
      .catch((err) => {
        if (!cancelled) onAccountError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [accountAttempt, navigate]);

  const reload = () => {
    fetchNotebook().then(setNotebook).catch((e) => setError(e.message));
    fetchRetrySets().then((d) => setRetrySets(d.retry_sets || [])).catch(() => {});
    fetchBookmarks().then((d) => setBookmarks(d.bookmarks || [])).catch(() => {});
    fetchNextSteps().then(setNextSteps).catch(() => {});
    fetchDueReviews().then(setDueReviews).catch(() => {});
    fetchReviewSchedules().then(setAllSchedules).catch(() => {});
  };

  const navigateIntoSession = (resp) => {
    const state = {
      candidateId: resp.candidate_id,
      skill: (resp.skills && resp.skills[0]) || 'DBMS',
      allSkills: resp.skills || [],
      sessionId: resp.session_id,
      question: resp.question,
      difficulty: resp.difficulty,
      round_type: resp.round_type || 'mcq',
      block_category: resp.block_category || null,
      question_context: resp.question_context || {},
      config_json: resp.config_json || {},
      expires_at: resp.expires_at || null,
      round: resp.round || 1,
      elo: resp.elo || 1200,
      totalRounds: resp.total_rounds || 1,
      roundsPerSkill: resp.rounds_per_skill || 1,
      purpose: resp.purpose || null,
    };
    saveInterviewState(state);
    navigate(resp.navigate || `/interview/${resp.session_id}`, { state });
  };

  useEffect(() => {
    if (!authReady) return undefined;
    reload();
    return undefined;
  }, [authReady]);

  const handleCreateRetry = async () => {
    setBusy(true);
    setError('');
    try {
      await createRetrySet({ name: retryName || undefined, max_items: Number(retryMax) || 5 });
      setRetryName('');
      reload();
    } catch (err) {
      setError(err.message || 'Could not create retry set.');
    } finally {
      setBusy(false);
    }
  };

  const handleStartRetry = async (setId) => {
    setBusy(true);
    setError('');
    try {
      const resp = await startRetrySet(setId);
      navigateIntoSession(resp);
    } catch (err) {
      setError(err.message || 'Could not start retry set.');
    } finally {
      setBusy(false);
    }
  };

  const handleStartDueReviews = async () => {
    setBusy(true);
    setError('');
    try {
      const resp = await startDueReviews({ max_items: 5 });
      navigateIntoSession(resp);
    } catch (err) {
      setError(err.message || 'Could not start review session.');
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteRetry = async (setId) => {
    setBusy(true);
    try {
      await deleteRetrySet(setId);
      reload();
    } catch (err) {
      setError(err.message || 'Could not delete retry set.');
    } finally {
      setBusy(false);
    }
  };

  const handleRemoveBookmark = async (itemType, itemId) => {
    try {
      await removeBookmark(itemType, itemId);
      reload();
    } catch (err) {
      setError(err.message || 'Could not remove bookmark.');
    }
  };

  const entryKey = (entry, idx) => `${entry.session_id}:${entry.round}:${entry.kind}:${entry.item_id || idx}`;

  const handleHint = async (entry, idx) => {
    const key = entryKey(entry, idx);
    try {
      const data = await fetchHint(entry.item_type, entry.item_id);
      setAssistView((prev) => ({ ...prev, [key]: { hint: data } }));
    } catch (err) {
      setAssistView((prev) => ({ ...prev, [key]: { error: err.message } }));
    }
  };

  const handleExplanation = async (entry, idx) => {
    const key = entryKey(entry, idx);
    try {
      const data = await fetchExplanation(entry.item_type, entry.item_id);
      setAssistView((prev) => ({ ...prev, [key]: { explanation: data } }));
    } catch (err) {
      setAssistView((prev) => ({ ...prev, [key]: { error: err.message } }));
    }
  };

  const handleSuggestionAction = async (suggestion) => {
    const action = suggestion.action || {};
    if (action.type === 'retry_set') {
      setBusy(true);
      setError('');
      try {
        const created = await createRetrySet({ skills: action.skills || [] });
        await handleStartRetry(created.retry_set.id);
      } catch (err) {
        setError(err.message || 'Could not start suggested retry.');
      } finally {
        setBusy(false);
      }
      return;
    }
    navigate('/practice?mode=full', {
      state: {
        prefilledSkills: action.skills || [],
        prefillSource: 'next steps',
      },
    });
  };

  if (!authReady) {
    return (
      <main className="min-h-screen bg-[var(--color-surface)] grid place-items-center">
        <AccountGate error={accountError} onRetry={retryAccount} />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]">
      <div className="app-container">
        <AppNav userId={navUser.userId} roleId={navUser.roleId} />
        <h1 className="mt-6 text-[length:var(--text-3xl)] font-semibold" style={{ fontFamily: 'var(--font-display)' }}>
          Learn
        </h1>
        <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
          Next steps, mistakes, spaced reviews, retry sets, and bookmarks —
          everything here is built from your recorded attempts. Assisted and
          unassisted work is labeled throughout. Reviews are practice, not
          measured mastery.
        </p>

        {error && (
          <div role="alert" className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        <section className="mt-6 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5" data-testid="due-reviews">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-xl font-semibold">Due for review</h2>
            {dueReviews && dueReviews.due_count > 0 && (
              <p className="text-sm text-[var(--color-ink-muted)]" data-testid="due-count">
                {dueReviews.due_count} due
                {dueReviews.unavailable_due_count > 0
                  ? ` (${dueReviews.available_due_count} reviewable, ${dueReviews.unavailable_due_count} coding unavailable)`
                  : ''}
              </p>
            )}
          </div>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
            Interval ladder: {(dueReviews?.interval_ladder || [1, 3, 7, 16, 35]).join(', ')} days.
            Correct lengthens; incorrect resets to 1 day. Scheduling never changes readiness or mastery.
          </p>
          {!dueReviews || dueReviews.items.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-ink-muted)]" data-testid="due-empty">
              {dueReviews?.empty_reason === 'nothing_due'
                ? 'Nothing is due right now — scheduled items will appear when their interval arrives.'
                : 'No review schedule yet. Misses from completed attempts appear here after they are recorded.'}
            </p>
          ) : (
            <>
              <ul className="mt-3 space-y-3">
                {dueReviews.items.map((item) => (
                  <li
                    key={item.id}
                    className="rounded-[var(--radius-card)] border border-[var(--color-border)] p-4"
                    data-testid={`due-item-${item.item_id}`}
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <p className="text-sm font-semibold">
                        {item.title || item.item_id}
                        {item.skill ? ` · ${item.skill}` : ''}
                      </p>
                      <p className="text-xs text-[var(--color-ink-muted)]">
                        {item.status === 'due_but_unavailable'
                          ? 'Due but unavailable'
                          : `Interval ${item.interval_days} day${item.interval_days === 1 ? '' : 's'}`}
                      </p>
                    </div>
                    <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
                      {item.miss_reason || 'Recorded miss'}
                      {item.originating_assisted ? ' · originating attempt assisted' : ' · originating attempt unassisted'}
                      {item.last_outcome
                        ? ` · last review ${item.last_outcome}${item.last_review_assisted ? ' (assisted)' : ''}`
                        : ''}
                    </p>
                    {item.status === 'due_but_unavailable' && (
                      <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
                        Coding execution is unavailable — this item stays on the due list
                        but cannot be reviewed to an outcome. Not a score and not a zero.
                      </p>
                    )}
                    {item.due_at && (
                      <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                        Due {new Date(item.due_at).toLocaleString()}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
              {dueReviews.note && (
                <p className="mt-3 text-sm text-[var(--color-ink-muted)]">{dueReviews.note}</p>
              )}
              {dueReviews.available_due_count > 0 && (
                <button
                  type="button"
                  className="hub-button mt-4"
                  disabled={busy}
                  onClick={handleStartDueReviews}
                  data-testid="start-due-reviews"
                >
                  {busy ? 'Working…' : 'Start review session'}
                </button>
              )}
            </>
          )}
          {allSchedules?.items?.some((i) => !i.is_due) && (
            <div className="mt-5 border-t border-[var(--color-border)] pt-4" data-testid="scheduled-reviews">
              <h3 className="text-sm font-semibold">Scheduled (not due yet)</h3>
              <ul className="mt-2 space-y-2">
                {allSchedules.items.filter((i) => !i.is_due).map((item) => (
                  <li key={item.id} className="text-sm text-[var(--color-ink-muted)]" data-testid={`scheduled-${item.item_id}`}>
                    <span className="font-medium text-[var(--color-ink)]">{item.title || item.item_id}</span>
                    {item.skill ? ` · ${item.skill}` : ''}
                    {' · '}
                    interval {item.interval_days} day{item.interval_days === 1 ? '' : 's'}
                    {item.last_outcome ? ` · last ${item.last_outcome}` : ''}
                    {item.due_at ? ` · next due ${new Date(item.due_at).toLocaleString()}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <section className="mt-6 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-xl font-semibold">Next steps</h2>
          {!nextSteps || nextSteps.suggestions.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              {nextSteps?.empty_reason === 'no_scored_attempts'
                ? 'No scored attempts yet — complete a practice round to get suggestions.'
                : 'No actionable gaps right now.'}
            </p>
          ) : (
            <ul className="mt-3 space-y-3">
              {nextSteps.suggestions.map((s) => (
                <li key={s.id} className="rounded-[var(--radius-card)] border border-[var(--color-border)] p-4">
                  <p className="text-sm font-semibold">{s.title}</p>
                  <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{s.detail}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => handleSuggestionAction(s)}
                      className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-40"
                    >
                      {s.action?.type === 'retry_set' ? 'Create & start retry' : 'Practice this skill'}
                    </button>
                    {(s.resources || []).slice(0, 2).map((r, i) => (
                      <a
                        key={i}
                        href={r.url}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-xs font-semibold"
                      >
                        {r.title || r.source || 'Resource'}
                      </a>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-xl font-semibold">Mistakes notebook</h2>
          {notebook?.counts && (
            <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
              {notebook.counts.total} misses from {notebook.counts.scored_rounds_scanned} scored rounds
              ({notebook.counts.unassisted} unassisted, {notebook.counts.assisted} assisted).
            </p>
          )}
          {!notebook || notebook.entries.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              {notebook?.empty_reason === 'no_scored_attempts'
                ? 'No scored attempts yet — your misses will appear here.'
                : 'No misses recorded. Explanations stay locked until you attempt an item.'}
            </p>
          ) : (
            <ul className="mt-3 max-h-[32rem] space-y-3 overflow-auto">
              {notebook.entries.map((entry, idx) => {
                const key = entryKey(entry, idx);
                const viewed = assistView[key] || {};
                return (
                  <li key={key} className="rounded-[var(--radius-card)] border border-[var(--color-border)] p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="min-w-0 flex-1 truncate text-sm font-semibold">{entry.title}</p>
                      {entry.assisted ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                          assisted{(entry.assistance_kinds || []).length ? ` · ${entry.assistance_kinds.join(', ')}` : ''}
                        </span>
                      ) : (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">
                          unassisted
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                      {entry.skill}{entry.sub_domain ? ` · ${entry.sub_domain}` : ''}
                      {entry.difficulty ? ` · ${entry.difficulty}` : ''}
                      {entry.round_type === 'mcq' && entry.raw_marks != null ? ` · ${entry.raw_marks} marks` : ''}
                      {entry.final_score != null ? ` · scored ${entry.final_score}` : ''}
                      {entry.cases_total ? ` · ${entry.cases_passed}/${entry.cases_total} cases` : ''}
                    </p>
                    {entry.kind === 'mcq_miss' && (
                      <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                        Your picks: {(entry.selected_option_ids || []).join(', ') || 'none (unanswered)'}
                      </p>
                    )}
                    {entry.kind === 'interview_miss' && (entry.missing_concepts || []).length > 0 && (
                      <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                        Missed concepts: {entry.missing_concepts.join(', ')}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <Link
                        to={`/dashboard/${entry.session_id}`}
                        className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 font-semibold"
                      >
                        View session report
                      </Link>
                      {entry.item_id && (
                        <>
                          <button
                            type="button"
                            onClick={() => handleHint(entry, idx)}
                            className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 font-semibold"
                          >
                            Hint
                          </button>
                          {entry.item_type === 'mcq' && (
                            <button
                              type="button"
                              onClick={() => handleExplanation(entry, idx)}
                              className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 font-semibold"
                            >
                              Explanation
                            </button>
                          )}
                        </>
                      )}
                    </div>
                    {viewed.error && (
                      <p className="mt-2 text-xs text-[var(--color-danger)]">{viewed.error}</p>
                    )}
                    {viewed.hint && <HintView hint={viewed.hint.hint} />}
                    {viewed.explanation?.available && (
                      <div className="mt-2 rounded border border-[var(--color-border)] bg-white p-2 text-xs" data-testid="learn-explanation">
                        <p>{viewed.explanation.explanation}</p>
                        {viewed.explanation.editorial?.solution_query && (
                          <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-2 text-[11px] text-slate-100">{viewed.explanation.editorial.solution_query}</pre>
                        )}
                        {viewed.explanation.editorial?.solution_code && (
                          <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-2 text-[11px] text-slate-100">{viewed.explanation.editorial.solution_code}</pre>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {notebook?.coverage?.excluded_coding_rounds > 0 && (
            <p className="mt-3 text-xs text-[var(--color-ink-muted)]">
              {notebook.coverage.excluded_coding_reason} (
              {notebook.coverage.excluded_coding_rounds} coding round
              {notebook.coverage.excluded_coding_rounds === 1 ? '' : 's'} excluded.)
            </p>
          )}
        </section>

        <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-xl font-semibold">Retry sets</h2>
          <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
            Generated from your genuinely missed topics only.
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-3 text-sm">
            <label>
              Name{' '}
              <input
                className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
                value={retryName}
                onChange={(e) => setRetryName(e.target.value)}
                placeholder="Optional"
              />
            </label>
            <label>
              Items{' '}
              <input
                type="number"
                min={1}
                max={10}
                className="ml-1 w-20 rounded border border-[var(--color-border)] px-2 py-1"
                value={retryMax}
                onChange={(e) => setRetryMax(Number(e.target.value))}
              />
            </label>
            <button
              type="button"
              disabled={busy}
              onClick={handleCreateRetry}
              className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-40"
            >
              {busy ? 'Working…' : 'Generate retry set'}
            </button>
          </div>
          {retrySets.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-ink-muted)]">
              No retry sets yet.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {retrySets.map((set) => (
                <li
                  key={set.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{set.name}</p>
                    <p className="text-xs text-[var(--color-ink-muted)]">
                      {set.items.length} items · {set.source}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => handleStartRetry(set.id)}
                      className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
                    >
                      Start
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => handleDeleteRetry(set.id)}
                      className="rounded-[var(--radius-pill)] border border-[var(--color-danger)]/40 px-3 py-1.5 text-xs font-semibold text-[var(--color-danger)] disabled:opacity-40"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-xl font-semibold">Bookmarks</h2>
          {bookmarks.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              No bookmarks yet. Bookmark problems from{' '}
              <Link to="/problems" className="underline">Problems</Link>.
            </p>
          ) : (
            <ul className="mt-3 max-h-72 space-y-2 overflow-auto">
              {bookmarks.map((b) => (
                <li
                  key={`${b.item_type}:${b.item_id}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{b.title}</p>
                    <p className="text-xs text-[var(--color-ink-muted)]">
                      {b.item_type} · {b.skill || '—'}{b.difficulty ? ` · ${b.difficulty}` : ''}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveBookmark(b.item_type, b.item_id)}
                    className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
