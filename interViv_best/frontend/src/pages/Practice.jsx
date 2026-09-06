import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  fetchMe,
  fetchCompanies,
  fetchPracticeBank,
  startSession,
  saveInterviewState,
} from '../lib/api';
import CompanySelector from '../components/CompanySelector';
import ResourceLinks from '../components/ResourceLinks';
import AppNav from '../components/AppNav';
import {
  PRACTICE_MODES,
  mapCustomBuilderToStartPayload,
  mapFullInterviewToStartPayload,
  mapOaSqlToStartPayload,
  mapProblemItemToStartPayload,
} from '../lib/practiceBuilder';

const DEFAULT_SKILLS = ['DBMS', 'OOP', 'DSA'];

function stripClientOnly(payload) {
  const next = { ...payload };
  delete next._client_timer_seconds;
  return next;
}

function navigateToInterview(navigate, startResp, extras = {}) {
  const state = {
    candidateId: startResp.candidate_id,
    skill: (startResp.skills && startResp.skills[0]) || 'DBMS',
    allSkills: startResp.skills || [],
    sessionId: startResp.session_id,
    question: startResp.question,
    difficulty: startResp.difficulty,
    round_type: startResp.round_type || 'technical_short_answer',
    question_context: startResp.question_context || {},
    config_json: startResp.config_json || {},
    expires_at: startResp.expires_at || null,
    round: startResp.round || 1,
    elo: startResp.elo || 1200,
    totalRounds: startResp.total_rounds || 1,
    roundsPerSkill: startResp.rounds_per_skill || 1,
    ...extras,
  };
  saveInterviewState(state);
  navigate(`/interview/${startResp.session_id}`, { state });
}

export default function Practice() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = searchParams.get('mode') || '';

  const [authReady, setAuthReady] = useState(false);
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [skills, setSkills] = useState(DEFAULT_SKILLS);
  const [target, setTarget] = useState({ companyId: '', roleId: '' });

  // Full interview
  const [roundsPerSkill, setRoundsPerSkill] = useState(3);

  // OA + SQL
  const [oaDuration, setOaDuration] = useState(45);
  const [mcqCount, setMcqCount] = useState(10);
  const [sqlCases, setSqlCases] = useState(1);

  // Custom builder
  const [totalMinutes, setTotalMinutes] = useState(40);
  const [questionCount, setQuestionCount] = useState(5);
  const [includeTechnical, setIncludeTechnical] = useState(true);
  const [includeMcq, setIncludeMcq] = useState(false);
  const [includeSql, setIncludeSql] = useState(false);

  // Problem bank
  const [bank, setBank] = useState({ mcq: [], sql: [] });
  const [bankType, setBankType] = useState('all');
  const [bankDifficulty, setBankDifficulty] = useState('all');
  const [bankSkill, setBankSkill] = useState('all');
  const [selectedItem, setSelectedItem] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        setUser(me.user || me);
        setAuthReady(true);
        if (me.user?.target_company_id || me.target_company_id) {
          setTarget({
            companyId: me.user?.target_company_id || me.target_company_id || '',
            roleId: me.user?.target_role_id || me.target_role_id || '',
          });
        }
      })
      .catch(() => {
        if (!cancelled) navigate('/login', { state: { next: '/practice' } });
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  useEffect(() => {
    if (!authReady || mode !== 'problems') return undefined;
    let cancelled = false;
    fetchPracticeBank()
      .then((data) => {
        if (!cancelled) setBank({ mcq: data.mcq || [], sql: data.sql || [] });
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load practice bank.');
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, mode]);

  // Soft-load role skills when company graph is available
  useEffect(() => {
    if (!target.companyId || !target.roleId) return undefined;
    let cancelled = false;
    fetchCompanies()
      .then((data) => {
        if (cancelled) return;
        const company = (data.companies || []).find((c) => c.id === target.companyId);
        const role = (company?.roles || []).find((r) => r.id === target.roleId);
        const req = (role?.required_skills || role?.skills || [])
          .map((s) => (typeof s === 'string' ? s : s.canonical_name || s.name || s.skill))
          .filter(Boolean);
        if (req.length) setSkills(req.slice(0, 5));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [target.companyId, target.roleId]);

  const bankItems = useMemo(() => {
    let items = [];
    if (bankType === 'all' || bankType === 'mcq') {
      items = items.concat((bank.mcq || []).map((q) => ({ ...q, type: 'mcq' })));
    }
    if (bankType === 'all' || bankType === 'sql') {
      items = items.concat((bank.sql || []).map((q) => ({ ...q, type: 'sql' })));
    }
    if (bankDifficulty !== 'all') {
      items = items.filter((i) => String(i.difficulty).toLowerCase() === bankDifficulty);
    }
    if (bankSkill !== 'all') {
      items = items.filter((i) => String(i.skill || '') === bankSkill);
    }
    return items;
  }, [bank, bankType, bankDifficulty, bankSkill]);

  const skillFilterOptions = useMemo(() => {
    const set = new Set();
    (bank.mcq || []).forEach((q) => q.skill && set.add(q.skill));
    (bank.sql || []).forEach(() => set.add('SQL'));
    return Array.from(set).sort();
  }, [bank]);

  const setMode = (id) => {
    setError('');
    setSearchParams(id ? { mode: id } : {});
  };

  const runStart = async (mapped) => {
    if (mapped.error) {
      setError(mapped.error);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const body = stripClientOnly(mapped.payload);
      const resp = await startSession(body);
      navigateToInterview(navigate, resp);
    } catch (err) {
      setError(err.message || 'Could not start session.');
    } finally {
      setBusy(false);
    }
  };

  if (!authReady) {
    return (
      <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)] grid place-items-center">
        <p className="text-sm text-[var(--color-ink-muted)]">Checking sign-in…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]">
      <div className="mx-auto w-full max-w-5xl px-[var(--space-4)] py-[var(--space-6)] sm:px-[var(--space-6)]">
        <AppNav
          userId={user?.id || user?.user_id || null}
          roleId={target.roleId || user?.target_role_id || null}
          trailing={
            <Link to="/upload" className="rounded-[var(--radius-pill)] px-3 py-1.5 text-sm text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]">
              Resume upload
            </Link>
          }
        />

        <header className="mt-8 border-b border-[var(--color-border)] pb-6">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">
            Practice Hub
          </p>
          <h1
            className="mt-2 text-[length:var(--text-3xl)] font-semibold tracking-normal sm:text-[length:var(--text-5xl)]"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Choose how you want to practice
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-[var(--color-ink-muted)]">
            Four modes deep-link into the existing interview, MCQ, and SQL flows. There is no general coding judge —
            SQL practice uses the sandboxed SQL runner only.
          </p>
        </header>

        {error && (
          <div className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        {!mode && (
          <section className="mt-6 grid gap-4 sm:grid-cols-2" data-testid="practice-modes">
            {PRACTICE_MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                data-mode={m.id}
                onClick={() => setMode(m.id)}
                className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5 text-left shadow-sm transition hover:border-slate-300"
              >
                <h2 className="text-lg font-semibold text-[var(--color-ink)]">{m.title}</h2>
                <p className="mt-2 text-sm leading-6 text-[var(--color-ink-muted)]">{m.blurb}</p>
              </button>
            ))}
          </section>
        )}

        {mode && (
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setMode('')}
              className="text-sm text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
            >
              ← All modes
            </button>
          </div>
        )}

        {(mode === 'full' || mode === 'oa_sql' || mode === 'custom') && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">
              Target role & skills
            </h3>
            <div className="mt-3">
              <CompanySelector
                isAuthenticated={Boolean(user)}
                initialCompanyId={target.companyId}
                initialRoleId={target.roleId}
                onSelectionChange={setTarget}
              />
            </div>
            <label className="mt-4 block text-sm text-[var(--color-ink-muted)]">
              Skills (comma-separated)
              <input
                className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] bg-white px-3 py-2 text-[var(--color-ink)]"
                value={skills.join(', ')}
                onChange={(e) =>
                  setSkills(
                    e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                  )
                }
              />
            </label>
          </section>
        )}

        {mode === 'full' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Full interview</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Starts a multi-skill free-text session. Difficulty follows your Elo (not a separate start field). Voice
              input is available on the interview page.
            </p>
            <label className="mt-4 block text-sm">
              Rounds per skill
              <input
                type="number"
                min={1}
                max={10}
                className="mt-1 w-32 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                value={roundsPerSkill}
                onChange={(e) => setRoundsPerSkill(Number(e.target.value))}
              />
            </label>
            <button
              type="button"
              disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() =>
                runStart(
                  mapFullInterviewToStartPayload({
                    skills,
                    roundsPerSkill,
                    targetCompanyId: target.companyId,
                    targetRoleId: target.roleId,
                  })
                )
              }
            >
              {busy ? 'Starting…' : 'Start full interview'}
            </button>
          </section>
        )}

        {mode === 'oa_sql' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">OA + SQL</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              One MCQ block, then SQL problem(s). This is not “OA + Coding” — there is no DSA coding judge.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <label className="text-sm">
                Duration (minutes)
                <input
                  type="number"
                  min={10}
                  max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={oaDuration}
                  onChange={(e) => setOaDuration(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                MCQ count
                <input
                  type="number"
                  min={1}
                  max={30}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={mcqCount}
                  onChange={(e) => setMcqCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                SQL cases
                <input
                  type="number"
                  min={1}
                  max={5}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={sqlCases}
                  onChange={(e) => setSqlCases(Number(e.target.value))}
                />
              </label>
            </div>
            <button
              type="button"
              disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() =>
                runStart(
                  mapOaSqlToStartPayload({
                    skills,
                    durationMinutes: oaDuration,
                    mcqCount,
                    sqlCases,
                    targetCompanyId: target.companyId,
                    targetRoleId: target.roleId,
                  })
                )
              }
            >
              {busy ? 'Starting…' : 'Start OA + SQL'}
            </button>
          </section>
        )}

        {mode === 'custom' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Custom interview builder</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Builds a real <code>round_plan</code> and calls <code>POST /session/start</code>. Unsupported mixes fail
              with an inline error — rounds are never silently dropped.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Total time (minutes)
                <input
                  type="number"
                  min={5}
                  max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={totalMinutes}
                  onChange={(e) => setTotalMinutes(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Number of questions / blocks
                <input
                  type="number"
                  min={1}
                  max={20}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={questionCount}
                  onChange={(e) => setQuestionCount(Number(e.target.value))}
                />
              </label>
            </div>
            <fieldset className="mt-4 space-y-2 text-sm">
              <legend className="font-semibold text-[var(--color-ink)]">Round mix</legend>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={includeTechnical}
                  onChange={(e) => setIncludeTechnical(e.target.checked)}
                />
                Free-text (technical / verbal)
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={includeMcq} onChange={(e) => setIncludeMcq(e.target.checked)} />
                MCQ
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={includeSql} onChange={(e) => setIncludeSql(e.target.checked)} />
                SQL
              </label>
            </fieldset>
            <p className="mt-3 text-xs text-[var(--color-ink-muted)]">
              Mode: text (default). Voice input remains available inside the interview UI — the session API does not
              distinguish text/voice/mixed starts.
            </p>
            <button
              type="button"
              disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() =>
                runStart(
                  mapCustomBuilderToStartPayload({
                    skills,
                    totalMinutes,
                    questionCount,
                    includeTechnical,
                    includeMcq,
                    includeSql,
                    targetCompanyId: target.companyId,
                    targetRoleId: target.roleId,
                    mode: 'text',
                  })
                )
              }
            >
              {busy ? 'Starting…' : 'Start custom session'}
            </button>
          </section>
        )}

        {mode === 'problems' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Problem practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Existing MCQ and SQL banks only. No Monaco editor, no hidden-test coding judge.
            </p>
            <div className="mt-4 flex flex-wrap gap-3 text-sm">
              <label>
                Type{' '}
                <select
                  className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
                  value={bankType}
                  onChange={(e) => setBankType(e.target.value)}
                >
                  <option value="all">all</option>
                  <option value="mcq">mcq</option>
                  <option value="sql">sql</option>
                </select>
              </label>
              <label>
                Difficulty{' '}
                <select
                  className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
                  value={bankDifficulty}
                  onChange={(e) => setBankDifficulty(e.target.value)}
                >
                  <option value="all">all</option>
                  <option value="easy">easy</option>
                  <option value="medium">medium</option>
                  <option value="hard">hard</option>
                </select>
              </label>
              <label>
                Skill{' '}
                <select
                  className="ml-1 rounded border border-[var(--color-border)] px-2 py-1"
                  value={bankSkill}
                  onChange={(e) => setBankSkill(e.target.value)}
                >
                  <option value="all">all</option>
                  {skillFilterOptions.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <ul className="mt-4 max-h-[28rem] space-y-2 overflow-auto">
              {bankItems.map((item) => (
                <li
                  key={`${item.type}-${item.id}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => setSelectedItem(item)}
                  >
                    <p className="truncate text-sm font-medium text-[var(--color-ink)]">
                      {item.type === 'sql' ? item.title : item.stem}
                    </p>
                    <p className="text-xs text-[var(--color-ink-muted)]">
                      {item.type} · {item.difficulty || '—'} · {item.skill || '—'}
                    </p>
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
                    onClick={() =>
                      runStart(
                        mapProblemItemToStartPayload(item, {
                          skills: item.skill ? [item.skill] : skills,
                        })
                      )
                    }
                  >
                    Practice
                  </button>
                </li>
              ))}
              {bankItems.length === 0 && (
                <li className="text-sm text-[var(--color-ink-muted)]">No items match these filters.</li>
              )}
            </ul>
            {selectedItem && (
              <div className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] p-4">
                <p className="text-sm font-semibold text-[var(--color-ink)]">
                  {selectedItem.type === 'sql' ? selectedItem.title : selectedItem.stem}
                </p>
                <ResourceLinks
                  questionId={selectedItem.id}
                  heading="Solution / lecture"
                  variant="light"
                  maxPerLevel={3}
                />
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
