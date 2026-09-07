import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMe, fetchProblems, startSession, saveInterviewState, fetchItemStatus, fetchBookmarks, saveBookmark, removeBookmark } from '../lib/api';
import { mapStandaloneToStartPayload } from '../lib/practiceBuilder';
import AppNav from '../components/AppNav';

/** Phase C Problems experience: browse the coding bank and start a coding round. */
export default function Problems() {
  const navigate = useNavigate();
  const [authReady, setAuthReady] = useState(false);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });
  const [problems, setProblems] = useState([]);
  const [count, setCount] = useState(0);
  const [difficulty, setDifficulty] = useState('');
  const [topic, setTopic] = useState('');
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [states, setStates] = useState({});
  const [bookmarked, setBookmarked] = useState(new Set());

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
      .catch(() => {
        if (!cancelled) navigate('/login', { state: { next: '/problems' } });
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

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
        <p className="text-sm text-[var(--color-ink-muted)]">Checking sign-in…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]">
      <div className="mx-auto w-full max-w-5xl px-[var(--space-4)] py-[var(--space-6)]">
        <AppNav userId={navUser.userId} roleId={navUser.roleId} />
        <h1 className="mt-6 text-[length:var(--text-3xl)] font-semibold" style={{ fontFamily: 'var(--font-display)' }}>
          Problems
        </h1>
        <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
          Python coding problems with visible examples. Final scoring adds hidden tests
          (60% visible, 40% hidden); a compile or runtime failure caps the score at 25.
        </p>

        {error && (
          <div className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-3 text-sm">
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

        <div className="mt-4 grid gap-4 lg:grid-cols-[5fr_7fr]">
          <ul className="max-h-[32rem] space-y-2 overflow-auto">
            {visibleProblems.map((p) => (
              <li
                key={p.id}
                className={`flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border px-3 py-2 ${
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
                >
                  {bookmarked.has(p.id) ? '★' : '☆'}
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

          <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
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
              <p className="text-sm text-[var(--color-ink-muted)]">
                Select a problem to preview its statement, examples, and starter code.
              </p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
