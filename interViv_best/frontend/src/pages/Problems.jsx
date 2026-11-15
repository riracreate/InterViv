import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bookmark, Code2, Search } from 'lucide-react';
import { fetchMe, fetchProblems, startSession, saveInterviewState, fetchItemStatus, fetchBookmarks, saveBookmark, removeBookmark, fetchCodingExecutionStatus } from '../lib/api';
import { mapStandaloneToStartPayload } from '../lib/practiceBuilder';
import AppNav from '../components/AppNav';
import AccountGate from '../components/AccountGate';
import { useAccountRetry } from '../lib/useAccountRetry';

/** Phase C Problems experience: browse the coding bank and start a coding round. */
export default function Problems() {
  const navigate = useNavigate();
  const { accountError, accountAttempt, retryAccount, onAccountError } = useAccountRetry();
  const [authReady, setAuthReady] = useState(false);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });
  const [problems, setProblems] = useState([]);
  const [count, setCount] = useState(0);
  const [difficulty, setDifficulty] = useState('');
  const [topic, setTopic] = useState('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [states, setStates] = useState({});
  const [bookmarked, setBookmarked] = useState(new Set());
  const [execution, setExecution] = useState(null);

  const statusLabel = (state) => {
    if (state === 'solved') return 'solved';
    if (state === 'attempted') return 'attempted';
    if (state === 'attempted_unscored') return 'attempted · unscored';
    return 'untried';
  };

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

  useEffect(() => {
    if (!authReady) return undefined;
    let cancelled = false;
    fetchCodingExecutionStatus()
      .then((data) => { if (!cancelled) setExecution(data); })
      .catch(() => { if (!cancelled) setExecution({ available: false, unknown: true }); });
    return () => { cancelled = true; };
  }, [authReady]);

  useEffect(() => {
    if (!authReady) return undefined;
    let cancelled = false;
    fetchProblems({ difficulty, topic: topic.trim() })
      .then((data) => {
        if (cancelled) return;
        setProblems(data.problems || []);
        setCount(data.count ?? (data.problems || []).length);
        setError('');
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load problems.');
      });
    fetchItemStatus('coding')
      .then((data) => {
        if (!cancelled) setStates(data.states || {});
      })
      .catch(() => {});
    fetchBookmarks()
      .then((data) => {
        if (cancelled) return;
        setBookmarked(new Set(
          (data.bookmarks || [])
            .filter((b) => b.item_type === 'coding')
            .map((b) => b.item_id)
        ));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [authReady, difficulty, topic]);

  const toggleBookmark = async (problemId) => {
    try {
      if (bookmarked.has(problemId)) {
        await removeBookmark('coding', problemId);
        setBookmarked((prev) => {
          const next = new Set(prev);
          next.delete(problemId);
          return next;
        });
      } else {
        await saveBookmark('coding', problemId);
        setBookmarked((prev) => new Set(prev).add(problemId));
      }
    } catch (err) {
      setError(err.message || 'Could not update bookmark.');
    }
  };

  const visibleProblems = problems.filter((p) => {
    const query = search.trim().toLowerCase();
    if (query && !`${p.title || ''} ${(p.topics || []).join(' ')}`.toLowerCase().includes(query)) return false;
    if (statusFilter === 'bookmarked') return bookmarked.has(p.id);
    if (!statusFilter) return true;
    return (states[p.id]?.state || 'untried') === statusFilter;
  });

  const formatValue = (value) => {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  };

  const practiceProblem = async (problemId) => {
    const mapped = mapStandaloneToStartPayload('coding', {
      problemId,
      durationMinutes: 30,
    });
    if (mapped.error) {
      setError(mapped.error);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const resp = await startSession(mapped.payload);
      const state = {
        candidateId: resp.candidate_id,
        skill: (resp.skills && resp.skills[0]) || 'DSA',
        allSkills: resp.skills || [],
        sessionId: resp.session_id,
        question: resp.question,
        difficulty: resp.difficulty,
        round_type: resp.round_type || 'coding',
        block_category: resp.block_category || null,
        question_context: resp.question_context || {},
        config_json: resp.config_json || {},
        expires_at: resp.expires_at || null,
        round: resp.round || 1,
        elo: resp.elo || 1200,
        totalRounds: resp.total_rounds || 1,
        roundsPerSkill: resp.rounds_per_skill || 1,
      };
      saveInterviewState(state);
      navigate(`/interview/${resp.session_id}`, { state });
    } catch (err) {
      setError(err.message || 'Could not start session.');
    } finally {
      setBusy(false);
    }
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
        <header className="app-page-hero iv-coding-header">
          <p className="iv-page-kicker">Practice / Coding Arena</p>
          <h1>Make every problem<br className="iv-desktop-break" /> a little easier.</h1>
          <p>Find a problem, write your solution, and learn from each attempt. Choose from the languages available in your coding workspace.</p>
        </header>
        {execution && <ExecutorStatus execution={execution} />}

        {error && (
          <div role="alert" className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        <div className="iv-problem-toolbar mt-4 flex flex-wrap gap-3 text-sm">
          <label className="iv-problem-search"><Search size={17} aria-hidden="true" /><span className="sr-only">Search problems</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search problems or topics" />
          </label>
          <label>
            Difficulty{' '}
            <select
              className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
            >
              <option value="">all</option>
              <option value="easy">easy</option>
              <option value="medium">medium</option>
              <option value="hard">hard</option>
            </select>
          </label>
          <label>
            Topic{' '}
            <input
              className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="arrays, strings, dp…"
            />
          </label>
          <label>
            Status{' '}
            <select
              className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">all</option>
              <option value="untried">untried</option>
              <option value="attempted">attempted</option>
              <option value="attempted_unscored">attempted · unscored</option>
              <option value="solved">solved</option>
              <option value="bookmarked">bookmarked</option>
            </select>
          </label>
          <span className="ml-auto self-center text-xs text-[var(--color-ink-muted)]">
            {visibleProblems.length} of {count} problem{count === 1 ? '' : 's'}
          </span>
        </div>

        <div className="iv-problem-grid mt-4 grid gap-4 lg:grid-cols-[5fr_7fr]">
          <ul className="iv-problem-list max-h-[32rem] space-y-2 overflow-auto" aria-label="Coding problems">
            {visibleProblems.map((p) => (
              <li
                key={p.id}
                className={`iv-problem-row flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border px-3 py-2 ${
                  selected?.id === p.id ? 'border-[var(--color-accent)]' : 'border-[var(--color-border)]'
                }`}
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => setSelected(p)}
                >
                  <p className="truncate text-sm font-medium text-[var(--color-ink)]">{p.title}</p>
                  <p className="text-xs text-[var(--color-ink-muted)]">
                    {p.difficulty || '—'} · {(p.topics || []).join(', ') || '—'} ·{' '}
                    {statusLabel(states[p.id]?.state || 'untried')}
                    {bookmarked.has(p.id) ? ' · ★' : ''}
                  </p>
                </button>
                <button
                  type="button"
                  className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold"
                  onClick={() => toggleBookmark(p.id)}
                  aria-label={bookmarked.has(p.id) ? 'Remove bookmark' : 'Bookmark'}
                  aria-pressed={bookmarked.has(p.id)}
                >
                  <Bookmark size={16} fill={bookmarked.has(p.id) ? 'currentColor' : 'none'} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  disabled={busy}
                  className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
                  onClick={() => practiceProblem(p.id)}
                >
                  {busy ? 'Starting…' : 'Practice'}
                </button>
              </li>
            ))}
            {visibleProblems.length === 0 && (
              <li className="text-sm text-[var(--color-ink-muted)]">No problems match these filters.</li>
            )}
          </ul>

          <div className="iv-problem-preview rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            {selected ? (
              <>
                <h2 className="text-xl font-semibold">{selected.title}</h2>
                <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                  {selected.difficulty} · {(selected.topics || []).join(', ')} · implement {selected.function}(...)
                </p>
                <p className="mt-3 whitespace-pre-line text-sm leading-relaxed">{selected.statement}</p>
                {(selected.constraints || []).length > 0 && (
                  <>
                    <h3 className="mt-4 text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">
                      Constraints
                    </h3>
                    <ul className="mt-1 list-disc pl-5 font-mono text-xs text-[var(--color-ink-muted)]">
                      {(selected.constraints || []).map((c, idx) => (
                        <li key={idx}>{c}</li>
                      ))}
                    </ul>
                  </>
                )}
                <h3 className="mt-4 text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">
                  Visible examples
                </h3>
                <div className="mt-2 space-y-2">
                  {(selected.visible_tests || []).map((tc, idx) => (
                    <div key={idx} className="rounded border border-[var(--color-border)] bg-white p-2 font-mono text-xs">
                      <div>Input: {formatValue(tc.input)}</div>
                      <div>Expected: {formatValue(tc.expected)}</div>
                    </div>
                  ))}
                </div>
                <h3 className="mt-4 text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">
                  Starter code
                </h3>
                <pre className="mt-2 overflow-x-auto rounded bg-gray-900 p-3 font-mono text-xs text-gray-100">
                  {selected.starter_code}
                </pre>
                <button
                  type="button"
                  disabled={busy}
                  className="mt-4 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
                  onClick={() => practiceProblem(selected.id)}
                >
                  {busy ? 'Starting…' : 'Practice this problem'}
                </button>
              </>
            ) : (
              <div className="iv-problem-empty"><span className="iv-quick-icon"><Code2 size={22} /></span>
                <h2>Choose a problem</h2><p>Select a problem to preview its statement, examples, and starter code.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

export function ExecutorStatus({ execution }) {
  const ready = (execution.languages || []).filter((item) => item.available);
  const on = Boolean(execution.available && ready.length);
  const tone = on
    ? 'border-[var(--color-success)]/30 bg-[var(--color-success-soft)] text-[var(--color-success)]'
    : 'border-[var(--color-warn)]/30 bg-[var(--color-warn-soft)] text-[var(--color-warn)]';
  let text;
  if (on) text = `Code execution on: ${ready.map((item) => item.label).join(', ')}.`;
  else if (execution.unknown) text = 'Could not check code execution. Run and Submit may fail; drafts are still saved.';
  else text = 'Code execution is off: you can write and save drafts, but Run and Submit need the local executor (scripts/run_local.py --with-executor).';
  return (
    <p data-testid="executor-status" role="status" className={`mt-3 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${tone}`}>
      <span aria-hidden="true" className="h-2 w-2 rounded-full bg-current" />
      {text}
    </p>
  );
}
