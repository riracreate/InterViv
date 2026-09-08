import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import {
  fetchMe,
  fetchCompanies,
  fetchPracticeBank,
  startSession,
  saveInterviewState,
  fetchPresets,
  createPreset,
  deletePreset,
  fetchBuilderDraft,
  saveBuilderDraft,
  fetchTargetContext,
} from '../lib/api';
import CompanySelector from '../components/CompanySelector';
import ResourceLinks from '../components/ResourceLinks';
import AppNav from '../components/AppNav';
import {
  PRACTICE_MODES,
  STANDALONE_MODES,
  BLOCK_CATEGORIES,
  PRESET_VERSION,
  BUILDER_DRAFT_VERSION,
  blockCategoryButtonLabel,
  createBlockId,
  addBlock,
  removeBlock,
  moveBlock,
  duplicateBlock,
  formatBlockLabel,
  totalTimeSummary,
  validateBuilderBlocks,
  validateDraftPayload,
  mapFullInterviewToStartPayload,
  mapOaSqlToStartPayload,
  mapProblemItemToStartPayload,
  mapBlocksToStartPayload,
  mapStandaloneToStartPayload,
  applyTargetPrefill,
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
    block_category: startResp.block_category || null,
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
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = searchParams.get('mode') || '';

  const [authReady, setAuthReady] = useState(false);
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [skills, setSkills] = useState(DEFAULT_SKILLS);
  const [skillsExplicit, setSkillsExplicit] = useState(false);
  const [prefillNote, setPrefillNote] = useState('');
  const [target, setTarget] = useState({ companyId: '', roleId: '' });

  // Full interview
  const [roundsPerSkill, setRoundsPerSkill] = useState(3);

  // OA + SQL
  const [oaDuration, setOaDuration] = useState(45);
  const [mcqCount, setMcqCount] = useState(10);
  const [sqlCases, setSqlCases] = useState(1);

  // Phase B standalone forms
  const [standaloneCount, setStandaloneCount] = useState(10);
  const [standaloneDuration, setStandaloneDuration] = useState(20);
  const [standaloneDifficulty, setStandaloneDifficulty] = useState('');
  const [standaloneTopics, setStandaloneTopics] = useState('DBMS');

  // Phase B block builder
  const [blocks, setBlocks] = useState([]);
  const [builderLoaded, setBuilderLoaded] = useState(false);
  const [draftStatus, setDraftStatus] = useState('');
  const [presets, setPresets] = useState([]);
  const [presetName, setPresetName] = useState('');
  const draftTimer = useRef(null);
  const BUILDER_LOCAL_KEY = 'interviv-builder-draft-v1';

  // Problem bank
  const [bank, setBank] = useState({ mcq: [], verbal: [], sql: [], coding: [], ml_primitives: [] });
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
        return fetchTargetContext().catch(() => null);
      })
      .then((data) => {
        if (cancelled || !data?.target) return;
        if (data.target.company_id && data.target.role_id) {
          setTarget({
            companyId: data.target.company_id,
            roleId: data.target.role_id,
          });
        }
      })
      .catch(() => {
        if (!cancelled) navigate('/login', { replace: true, state: { next: location.pathname + location.search } });
      });
    return () => {
      cancelled = true;
    };
  }, [navigate, location.pathname, location.search]);

  useEffect(() => {
    if (!authReady || mode !== 'problems') return undefined;
    let cancelled = false;
    fetchPracticeBank()
      .then((data) => {
        if (!cancelled) setBank({ mcq: data.mcq || [], verbal: data.verbal || [], sql: data.sql || [], coding: data.coding || [], ml_primitives: data.ml_primitives || [] });
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load practice bank.');
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, mode]);

  // Phase B: load builder draft (server first, local fallback) + presets.
  useEffect(() => {
    if (!authReady || mode !== 'custom') return undefined;
    let cancelled = false;
    fetchBuilderDraft()
      .then((data) => {
        if (cancelled) return;
        const draftError = validateDraftPayload(data);
        if (!draftError && data.blocks?.length) {
          setBlocks(data.blocks.map((b) => ({ ...b, id: b.id || createBlockId() })));
          setBuilderLoaded(true);
          return;
        }
        const raw = localStorage.getItem(BUILDER_LOCAL_KEY);
        if (raw) {
          try {
            const local = JSON.parse(raw);
            if (!validateDraftPayload(local) && local.blocks?.length) {
              setBlocks(local.blocks.map((b) => ({ ...b, id: b.id || createBlockId() })));
              setBuilderLoaded(true);
              return;
            }
          } catch { /* fall through to empty builder */ }
        }
        setBuilderLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        try {
          const raw = localStorage.getItem(BUILDER_LOCAL_KEY);
          if (raw) {
            const local = JSON.parse(raw);
            if (!validateDraftPayload(local) && local.blocks?.length) {
              setBlocks(local.blocks.map((b) => ({ ...b, id: b.id || createBlockId() })));
            }
          }
        } catch { /* empty builder */ }
        setBuilderLoaded(true);
      });
    fetchPresets()
      .then((data) => {
        if (!cancelled) setPresets(data.presets || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [authReady, mode, BUILDER_LOCAL_KEY]);

  // Phase B: autosave builder drafts (debounced server + immediate local).
  useEffect(() => {
    if (!authReady || mode !== 'custom' || !builderLoaded) return undefined;
    try {
      localStorage.setItem(
        BUILDER_LOCAL_KEY,
        JSON.stringify({ version: BUILDER_DRAFT_VERSION, blocks })
      );
    } catch { /* storage full or unavailable */ }
    setDraftStatus(blocks.length ? 'Saving…' : '');
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      saveBuilderDraft({ version: BUILDER_DRAFT_VERSION, blocks })
        .then(() => setDraftStatus(blocks.length ? 'Draft saved' : ''))
        .catch(() => setDraftStatus('Local only (server unavailable)'));
    }, 800);
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, [blocks, authReady, mode, builderLoaded, BUILDER_LOCAL_KEY]);

  // Soft-load role skills when company graph is available. Prefill only:
  // an explicitly chosen topic list is never overridden.
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
        const { skills: next, applied } = applyTargetPrefill(skills, req, skillsExplicit);
        if (applied) {
          setSkills(next);
          setPrefillNote(`Prefilled from ${role?.title || 'target role'} required skills.`);
        } else if (skillsExplicit) {
          setPrefillNote('Showing your explicitly chosen topics; target prefill skipped.');
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.companyId, target.roleId]);

  // Connected hop: gap/roadmap weak-area skills arrive as prefill, not
  // an override. Runs once per navigation state.
  const hopAppliedFor = useRef(null);
  useEffect(() => {
    const incoming = location.state?.prefilledSkills;
    if (!Array.isArray(incoming) || !incoming.length) return undefined;
    const key = JSON.stringify([location.key, incoming]);
    if (hopAppliedFor.current === key) return undefined;
    hopAppliedFor.current = key;
    const { skills: next, applied } = applyTargetPrefill(skills, incoming, skillsExplicit);
    if (applied) {
      setSkills(next);
      setPrefillNote(
        `Prefilled from ${location.state?.prefillSource || 'gap analysis'} weak areas.`
      );
    }
    // Adopt the hop's target only when no target is set yet.
    const hopCompany = location.state?.targetCompanyId || '';
    const hopRole = location.state?.targetRoleId || '';
    if (hopCompany && hopRole && !target.companyId && !target.roleId) {
      setTarget({ companyId: hopCompany, roleId: hopRole });
    }
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key]);

  const bankItems = useMemo(() => {
    let items = [];
    if (bankType === 'all' || bankType === 'mcq') {
      items = items.concat((bank.mcq || []).map((q) => ({ ...q, type: 'mcq' })));
    }
    if (bankType === 'all' || bankType === 'verbal') {
      items = items.concat((bank.verbal || []).map((q) => ({ ...q, type: 'mcq', category: 'verbal' })));
    }
    if (bankType === 'all' || bankType === 'sql') {
      items = items.concat((bank.sql || []).map((q) => ({ ...q, type: 'sql' })));
    }
    if (bankType === 'all' || bankType === 'coding') {
      items = items.concat((bank.coding || []).map((q) => ({ ...q, type: 'coding', skill: 'DSA' })));
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
    (bank.verbal || []).forEach((q) => q.skill && set.add(q.skill));
    (bank.sql || []).forEach(() => set.add('SQL'));
    (bank.coding || []).forEach(() => set.add('DSA'));
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
            Standalone blocks, guided modes, and a custom builder for Verbal, OA, SQL, coding, and interview practice.
            Coding practice runs Python with visible examples and hidden-test scoring; SQL practice uses the sandboxed SQL runner only.
          </p>
        </header>

        {error && (
          <div className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        {!mode && (
          <>
            <section className="mt-6" data-testid="standalone-modes" aria-label="Standalone practice">
              <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">
                Standalone practice
              </h2>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                {STANDALONE_MODES.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    data-mode={m.id}
                    onClick={() => setMode(m.id)}
                    className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5 text-left shadow-sm transition hover:border-slate-300"
                  >
                    <h3 className="text-lg font-semibold text-[var(--color-ink)]">{m.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-[var(--color-ink-muted)]">{m.blurb}</p>
                  </button>
                ))}
              </div>
            </section>
            <section className="mt-8 grid gap-4 sm:grid-cols-2" data-testid="practice-modes" aria-label="Guided modes">
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
          </>
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
                onChange={(e) => {
                  setSkillsExplicit(true);
                  setPrefillNote('');
                  setSkills(
                    e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                  );
                }}
              />
            </label>
            {prefillNote && (
              <p className="mt-2 text-xs text-[var(--color-ink-muted)]">{prefillNote}</p>
            )}
          </section>
        )}

        {(mode === 'verbal' || mode === 'oa' || mode === 'sql' || mode === 'coding' || mode === 'system_design' || mode === 'ml_primitives' || mode === 'interview') && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">
              Target (optional)
            </h3>
            <div className="mt-3">
              <CompanySelector
                isAuthenticated={Boolean(user)}
                initialCompanyId={target.companyId}
                initialRoleId={target.roleId}
                onSelectionChange={setTarget}
              />
            </div>
            <p className="mt-3 text-xs text-[var(--color-ink-muted)]">
              Targets may prefill settings but never override an explicitly chosen topic.
            </p>
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

        {mode === 'verbal' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Verbal Ability</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              English MCQs only — grammar, vocabulary, comprehension, ordering, idioms. Not a speaking assessment.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Questions (1–30)
                <input
                  type="number" min={1} max={30}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneCount}
                  onChange={(e) => setStandaloneCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('verbal', {
                count: standaloneCount, durationMinutes: standaloneDuration,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start Verbal practice'}
            </button>
          </section>
        )}

        {mode === 'oa' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">OA practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Technical MCQs restricted to your selected topics. Other subjects are never mixed in to fill the count.
            </p>
            <label className="mt-4 block text-sm">
              Topics (comma-separated, e.g. DBMS)
              <input
                className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                value={standaloneTopics}
                onChange={(e) => setStandaloneTopics(e.target.value)}
              />
            </label>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <label className="text-sm">
                Questions (1–30)
                <input
                  type="number" min={1} max={30}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneCount}
                  onChange={(e) => setStandaloneCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDifficulty}
                  onChange={(e) => setStandaloneDifficulty(e.target.value)}
                >
                  <option value="">Mixed</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('oa', {
                skills: standaloneTopics.split(',').map((s) => s.trim()).filter(Boolean),
                count: standaloneCount, durationMinutes: standaloneDuration,
                difficulty: standaloneDifficulty || undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start OA practice'}
            </button>
          </section>
        )}

        {mode === 'sql' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">SQL practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              SQL problems with schemas and execution-based evaluation.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDifficulty}
                  onChange={(e) => setStandaloneDifficulty(e.target.value)}
                >
                  <option value="">Mixed</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('sql', {
                durationMinutes: standaloneDuration,
                difficulty: standaloneDifficulty || undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start SQL practice'}
            </button>
          </section>
        )}

        {mode === 'coding' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Coding practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Python problems with visible examples and hidden-test scoring (60% visible, 40% hidden).
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDifficulty}
                  onChange={(e) => setStandaloneDifficulty(e.target.value)}
                >
                  <option value="">Mixed</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('coding', {
                durationMinutes: standaloneDuration,
                difficulty: standaloneDifficulty || undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start coding practice'}
            </button>
          </section>
        )}

        {mode === 'ml_primitives' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-lg font-semibold">ML primitives</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">Implement numerical algorithms in Python. Submissions are saved without being run or graded; scoring is unavailable.</p>
            <label className="mt-4 block text-sm">Problem
              <select value={selectedItem?.type === 'ml_primitives' ? selectedItem.id : ''}
                onChange={e => setSelectedItem(bank.ml_primitives.find(p => p.id === e.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2">
                <option value="">Choose automatically</option>
                {bank.ml_primitives.map(p => <option key={p.id} value={p.id}>{p.title} · {p.difficulty}</option>)}
              </select>
            </label>
            <label className="mt-4 block text-sm">Time budget (minutes)
              <input type="number" min={1} max={180} value={standaloneDuration}
                onChange={e => setStandaloneDuration(Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2" />
            </label>
            <button type="button" disabled={busy}
              className="mt-4 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              onClick={() => runStart(mapStandaloneToStartPayload('ml_primitives', {
                durationMinutes: standaloneDuration,
                problemId: selectedItem?.type === 'ml_primitives' ? selectedItem.id : undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}>
              {busy ? 'Starting…' : 'Start ML primitives'}
            </button>
          </section>
        )}

        {mode === 'system_design' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">System design</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Design prompts with an explicit self-assessment rubric. Scores are self-reported — diagrams are not auto-scored.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Prompts (1–5)
                <input
                  type="number" min={1} max={5}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneCount}
                  onChange={(e) => setStandaloneCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Time budget (minutes)
                <input
                  type="number" min={1} max={180}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDuration}
                  onChange={(e) => setStandaloneDuration(Number(e.target.value))}
                />
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-4 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              onClick={() => runStart(mapStandaloneToStartPayload('system_design', {
                count: Math.min(5, Math.max(1, Number(standaloneCount) || 1)),
                durationMinutes: standaloneDuration,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start system design'}
            </button>
          </section>
        )}

        {mode === 'interview' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Interview practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Technical/HR questions with text and voice input on the interview page.
            </p>
            <label className="mt-4 block text-sm">
              Skills (comma-separated)
              <input
                className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                value={standaloneTopics}
                onChange={(e) => setStandaloneTopics(e.target.value)}
              />
            </label>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                Questions (1–10)
                <input
                  type="number" min={1} max={10}
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneCount}
                  onChange={(e) => setStandaloneCount(Number(e.target.value))}
                />
              </label>
              <label className="text-sm">
                Difficulty
                <select
                  className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                  value={standaloneDifficulty}
                  onChange={(e) => setStandaloneDifficulty(e.target.value)}
                >
                  <option value="">Adaptive (Elo)</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
            <button
              type="button" disabled={busy}
              className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              onClick={() => runStart(mapStandaloneToStartPayload('interview', {
                skills: standaloneTopics.split(',').map((s) => s.trim()).filter(Boolean),
                count: standaloneCount,
                difficulty: standaloneDifficulty || undefined,
                targetCompanyId: target.companyId, targetRoleId: target.roleId,
              }))}
            >
              {busy ? 'Starting…' : 'Start interview practice'}
            </button>
          </section>
        )}

        {mode === 'custom' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Custom interview builder</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Add, reorder, and repeat Verbal, OA, SQL, coding, system design, ML primitives, and interview blocks with independent settings.
              If your settings cannot be combined, you will see an explanation before starting.
            </p>
            {!builderLoaded && (
              <p className="mt-4 text-sm text-[var(--color-ink-muted)]">Loading saved draft…</p>
            )}
            {builderLoaded && (
              <>
                <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Add block">
                  {BLOCK_CATEGORIES.map((category) => (
                    <button
                      key={category}
                      type="button"
                      onClick={() => setBlocks((prev) => addBlock(prev, category))}
                      className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold hover:border-slate-400"
                    >
                      + {blockCategoryButtonLabel(category)}
                    </button>
                  ))}
                </div>

                {blocks.length === 0 && (
                  <p className="mt-4 text-sm text-[var(--color-ink-muted)]">
                    No blocks yet. Add Verbal, OA, SQL, coding, system design, ML primitives, or interview blocks above. Adding Verbal never erases your sequence.
                  </p>
                )}

                <ol className="mt-4 space-y-3">
                  {blocks.map((block, index) => (
                    <li
                      key={block.id}
                      className="rounded-[var(--radius-card)] border border-[var(--color-border)] p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--color-ink)]">
                          {index + 1}. {formatBlockLabel(block)}
                        </p>
                        <div className="flex flex-wrap gap-1.5" role="group" aria-label={`Reorder block ${index + 1}`}>
                          <button
                            type="button"
                            aria-label={`Move block ${index + 1} up`}
                            disabled={index === 0}
                            onClick={() => setBlocks((prev) => moveBlock(prev, block.id, 'up'))}
                            className="rounded border border-[var(--color-border)] px-2 py-1 text-xs disabled:opacity-40"
                          >
                            ↑ Up
                          </button>
                          <button
                            type="button"
                            aria-label={`Move block ${index + 1} down`}
                            disabled={index === blocks.length - 1}
                            onClick={() => setBlocks((prev) => moveBlock(prev, block.id, 'down'))}
                            className="rounded border border-[var(--color-border)] px-2 py-1 text-xs disabled:opacity-40"
                          >
                            ↓ Down
                          </button>
                          <button
                            type="button"
                            onClick={() => setBlocks((prev) => duplicateBlock(prev, block.id))}
                            className="rounded border border-[var(--color-border)] px-2 py-1 text-xs"
                          >
                            Repeat
                          </button>
                          <button
                            type="button"
                            onClick={() => setBlocks((prev) => removeBlock(prev, block.id))}
                            className="rounded border border-[var(--color-danger)]/40 px-2 py-1 text-xs text-[var(--color-danger)]"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        {block.category !== 'verbal' && block.category !== 'sql' && (
                          <label className="text-xs text-[var(--color-ink-muted)]">
                            {block.category === 'oa' ? 'Topics' : 'Skills'} (comma-separated)
                            <input
                              className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm text-[var(--color-ink)]"
                              value={(block.skills || []).join(', ')}
                              onChange={(e) =>
                                setBlocks((prev) =>
                                  prev.map((b) =>
                                    b.id === block.id
                                      ? { ...b, skills: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) }
                                      : b
                                  )
                                )
                              }
                            />
                          </label>
                        )}
                        {block.category === 'verbal' && (
                          <p className="text-xs text-[var(--color-ink-muted)]">
                            Topics: Verbal Ability (fixed English MCQs)
                          </p>
                        )}
                        <label className="text-xs text-[var(--color-ink-muted)]">
                          {['sql', 'coding', 'ml_primitives'].includes(block.category) ? 'Problems' : 'Questions'}
                          <input
                            type="number"
                            min={1}
                            max={['sql', 'coding', 'ml_primitives'].includes(block.category) ? 5 : block.category === 'interview' ? 10 : 30}
                            className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-ink)]"
                            value={block.count}
                            onChange={(e) =>
                              setBlocks((prev) =>
                                prev.map((b) => (b.id === block.id ? { ...b, count: Number(e.target.value) } : b))
                              )
                            }
                          />
                        </label>
                        <label className="text-xs text-[var(--color-ink-muted)]">
                          Time budget (minutes){block.category === 'interview' ? ' — optional' : ''}
                          <input
                            type="number"
                            min={1}
                            max={180}
                            placeholder={block.category === 'interview' ? 'Untimed' : ''}
                            className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-ink)]"
                            value={block.duration_minutes ?? ''}
                            onChange={(e) =>
                              setBlocks((prev) =>
                                prev.map((b) =>
                                  b.id === block.id
                                    ? { ...b, duration_minutes: e.target.value === '' ? undefined : Number(e.target.value) }
                                    : b
                                )
                              )
                            }
                          />
                        </label>
                        <label className="text-xs text-[var(--color-ink-muted)]">
                          Difficulty
                          <select
                            className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-ink)]"
                            value={block.difficulty || ''}
                            onChange={(e) =>
                              setBlocks((prev) =>
                                prev.map((b) =>
                                  b.id === block.id ? { ...b, difficulty: e.target.value || undefined } : b
                                )
                              )
                            }
                          >
                            <option value="">{block.category === 'interview' ? 'Adaptive (Elo)' : 'Mixed'}</option>
                            <option value="easy">Easy</option>
                            <option value="medium">Medium</option>
                            <option value="hard">Hard</option>
                          </select>
                        </label>
                      </div>
                    </li>
                  ))}
                </ol>

                {blocks.length > 0 && (() => {
                  const summary = totalTimeSummary(blocks);
                  return (
                    <p className="mt-4 text-sm text-[var(--color-ink-muted)]" data-testid="builder-summary">
                      {summary.blockCount} {summary.blockCount === 1 ? 'block' : 'blocks'}
                      {' · '}
                      {summary.timedMinutes} timed minutes
                      {summary.untimedBlocks > 0 && ` · ${summary.untimedBlocks} untimed interview block${summary.untimedBlocks === 1 ? '' : 's'}`}
                      {' — '}
                      {blocks.map(formatBlockLabel).join(' → ')}
                    </p>
                  );
                })()}
                {draftStatus && (
                  <p className="mt-2 text-xs text-[var(--color-ink-muted)]" role="status">{draftStatus}</p>
                )}

                <div className="mt-6 border-t border-[var(--color-border)] pt-4">
                  <h3 className="text-sm font-semibold text-[var(--color-ink)]">Saved presets</h3>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <input
                      aria-label="Preset name"
                      placeholder="Preset name"
                      className="min-w-0 flex-1 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm"
                      value={presetName}
                      onChange={(e) => setPresetName(e.target.value)}
                    />
                    <button
                      type="button"
                      disabled={busy || blocks.length === 0 || !presetName.trim()}
                      onClick={async () => {
                        setBusy(true);
                        setError('');
                        try {
                          const saved = await createPreset({
                            name: presetName.trim(),
                            version: PRESET_VERSION,
                            blocks,
                          });
                          setPresets((prev) => [...prev, saved]);
                          setPresetName('');
                        } catch (err) {
                          setError(err.message || 'Could not save preset.');
                        } finally {
                          setBusy(false);
                        }
                      }}
                      className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-sm font-semibold disabled:opacity-40"
                    >
                      Save preset
                    </button>
                  </div>
                  {presets.length > 0 && (
                    <ul className="mt-3 space-y-2">
                      {presets.map((preset) => (
                        <li
                          key={preset.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                        >
                          <span className="text-sm font-medium">{preset.name}</span>
                          <span className="flex gap-1.5">
                            <button
                              type="button"
                              onClick={() => {
                                const loaded = (preset.blocks || []).map((b) => ({ ...b, id: b.id || createBlockId() }));
                                const validation = validateBuilderBlocks(loaded);
                                if (validation) {
                                  setError(`Preset "${preset.name}" is invalid: ${validation}`);
                                  return;
                                }
                                setBlocks(loaded);
                                setError('');
                              }}
                              className="rounded border border-[var(--color-border)] px-2 py-1 text-xs"
                            >
                              Load
                            </button>
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  await deletePreset(preset.id);
                                  setPresets((prev) => prev.filter((p) => p.id !== preset.id));
                                } catch (err) {
                                  setError(err.message || 'Could not delete preset.');
                                }
                              }}
                              className="rounded border border-[var(--color-danger)]/40 px-2 py-1 text-xs text-[var(--color-danger)]"
                            >
                              Delete
                            </button>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <p className="mt-4 text-xs text-[var(--color-ink-muted)]">
                  Mode: text (default). Voice input remains available inside the interview UI — the session API does not
                  distinguish text/voice/mixed starts.
                </p>
                <button
                  type="button"
                  disabled={busy || blocks.length === 0}
                  className="mt-5 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
                  onClick={() =>
                    runStart(
                      mapBlocksToStartPayload(blocks, {
                        targetCompanyId: target.companyId,
                        targetRoleId: target.roleId,
                      })
                    )
                  }
                >
                  {busy ? 'Starting…' : 'Start custom session'}
                </button>
              </>
            )}
          </section>
        )}

        {mode === 'problems' && (
          <section className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-xl font-semibold">Problem practice</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              OA, Verbal Ability, SQL, and coding banks. Coding items score against visible examples and hidden tests.
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
                  <option value="verbal">verbal</option>
                  <option value="sql">sql</option>
                  <option value="coding">coding</option>
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
                      {item.type === 'sql' || item.type === 'coding' ? item.title : item.stem}
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
                  {selectedItem.type === 'sql' || selectedItem.type === 'coding' ? selectedItem.title : selectedItem.stem}
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
