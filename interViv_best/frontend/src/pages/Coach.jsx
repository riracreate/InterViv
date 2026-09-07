import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchMe, fetchCoachPlan, fetchCoachStartPractice, saveInterviewState, fetchTargetContext, saveTargetContext } from '../lib/api';
import { mapCoachPlan } from '../lib/coachMapping';
import AppNav from '../components/AppNav';

export default function Coach() {
  const navigate = useNavigate();
  const [authReady, setAuthReady] = useState(false);
  const [mode, setMode] = useState('goal'); // goal | jd
  const [text, setText] = useState('');
  const [textTouched, setTextTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [plan, setPlan] = useState(null);
  const [roleId, setRoleId] = useState('');
  const [userId, setUserId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        setAuthReady(true);
        const u = me.user || me;
        setRoleId(u.target_role_id || me.target_role_id || '');
        setUserId(u.id || u.user_id || null);
      })
      .catch(() => {
        if (!cancelled) navigate('/login', { state: { next: '/coach' } });
      });
    // Prefill from the shared target context only when fields are empty;
    // user input is never overridden.
    fetchTargetContext()
      .then((data) => {
        if (cancelled || !data.target) return;
        if (data.target.role_id) setRoleId((prev) => prev || data.target.role_id);
        if (data.target.jd_text && !textTouched) {
          setText(data.target.jd_text);
          setMode('jd');
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      const body =
        mode === 'jd'
          ? { jd_text: text, goal_text: '', include_dashboard: true, role_id: roleId || null }
          : { goal_text: text, jd_text: '', include_dashboard: true, role_id: roleId || null };
      const data = await fetchCoachPlan(body);
      setPlan(mapCoachPlan(data));
      // Carry a pasted JD forward so ATS and later visits prefill it.
      if (mode === 'jd' && text.trim()) {
        saveTargetContext({ jd_text: text.trim(), jd_source: 'paste' }).catch(() => {});
      }
    } catch (err) {
      setError(err.message || 'Could not build a plan.');
      setPlan(null);
    } finally {
      setBusy(false);
    }
  };

  const startPractice = async () => {
    if (!plan?.practicePreview?.skills?.length) return;
    setBusy(true);
    setError('');
    try {
      const data = await fetchCoachStartPractice({
        skills: plan.practicePreview.skills,
        round_plan: plan.practicePreview.roundPlan,
      });
      const sessionId = data.session_id;
      if (!sessionId) throw new Error('Practice start did not return a session.');
      const state = {
        candidateId: data.candidate_id,
        skill: (data.skills && data.skills[0]) || 'DSA',
        allSkills: data.skills || [],
        sessionId,
        question: data.question,
        difficulty: data.difficulty,
        round_type: data.round_type || 'technical_short_answer',
        block_category: data.block_category || null,
        question_context: data.question_context || {},
        config_json: data.config_json || {},
        expires_at: data.expires_at || null,
        round: data.round || 1,
        elo: data.elo || 1200,
        totalRounds: data.total_rounds || (data.round_plan || []).length || 1,
        roundsPerSkill: 1,
      };
      saveInterviewState(state);
      navigate(data.navigate || `/interview/${sessionId}`, { state });
    } catch (err) {
      setError(err.message || 'Could not start practice.');
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
      <div className="mx-auto w-full max-w-3xl px-[var(--space-4)] py-[var(--space-6)] sm:px-[var(--space-6)]">
        <AppNav userId={userId} roleId={roleId || null} />

        <header className="mt-8 border-b border-[var(--color-border)] pb-6">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">Guidance coach</p>
          <h1 className="mt-2 text-[length:var(--text-3xl)] font-semibold" style={{ fontFamily: 'var(--font-display)' }}>
            Don’t know where to start?
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]" data-testid="coach-disclaimer">
            Coach maps your text onto interViv skills. It does not score interviews.
          </p>
        </header>

        {error && (
          <div className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        <div className="mt-6 flex flex-wrap gap-2 text-sm">
          <button
            type="button"
            className={`rounded-[var(--radius-pill)] px-4 py-2 font-semibold ${
              mode === 'goal'
                ? 'bg-[var(--color-ink)] text-white'
                : 'border border-[var(--color-border)] text-[var(--color-ink-muted)]'
            }`}
            onClick={() => setMode('goal')}
          >
            I have a goal
          </button>
          <button
            type="button"
            className={`rounded-[var(--radius-pill)] px-4 py-2 font-semibold ${
              mode === 'jd'
                ? 'bg-[var(--color-ink)] text-white'
                : 'border border-[var(--color-border)] text-[var(--color-ink-muted)]'
            }`}
            onClick={() => setMode('jd')}
          >
            I have a JD
          </button>
        </div>

        <label className="mt-4 block">
          <span className="sr-only">{mode === 'jd' ? 'Job description' : 'Goal'}</span>
          <textarea
            className="mt-2 w-full min-h-[140px] rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-3 text-sm leading-6"
            value={text}
            onChange={(e) => {
              setTextTouched(true);
              setText(e.target.value);
            }}
            placeholder={
              mode === 'jd'
                ? 'Paste a job description…'
                : 'e.g. SDE1 product company Pune — backend Python, SQL'
            }
            maxLength={8000}
            data-testid="coach-input"
          />
        </label>

        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="mt-4 rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
        >
          {busy ? 'Planning…' : 'Build my plan'}
        </button>

        {plan?.needsClarification && (
          <section className="mt-8 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-base font-semibold">Tell us a bit more</h2>
            <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
              Add YOE, stack, and city (at least ~20 characters), then try again.
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[var(--color-ink-muted)]">
              {plan.clarifyingQuestions.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </section>
        )}

        {plan && !plan.needsClarification && (
          <section className="mt-8 space-y-6" data-testid="coach-result">
            <div>
              <h2 className="text-base font-semibold">Skills</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {plan.haveSkills.map((s) => (
                  <span
                    key={`have-${s}`}
                    className="rounded-md bg-[var(--color-success-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-success)]"
                  >
                    have · {s}
                  </span>
                ))}
                {plan.missingSkills.map((s) => (
                  <span
                    key={`miss-${s}`}
                    className="rounded-md bg-[var(--color-warn-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-warn)]"
                  >
                    missing · {s}
                  </span>
                ))}
                {plan.unrecognized.map((s) => (
                  <span
                    key={`unk-${s}`}
                    className="rounded-md bg-[var(--color-surface-muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-ink-muted)]"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>

            <ol className="space-y-3" data-testid="coach-steps">
              {plan.steps.map((step, i) => (
                <li
                  key={`${step.href}-${i}`}
                  className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-4"
                >
                  <p className="text-sm font-semibold">
                    {i + 1}. {step.title}
                  </p>
                  <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{step.why}</p>
                  <Link
                    to={step.href}
                    className="mt-2 inline-block text-sm font-semibold text-[var(--color-accent)] underline-offset-2 hover:underline"
                    data-testid="coach-step-link"
                  >
                    {step.href}
                  </Link>
                </li>
              ))}
            </ol>

            <button
              type="button"
              disabled={busy || !plan.practicePreview.skills.length}
              onClick={startPractice}
              className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-6 py-3 text-sm font-semibold text-white disabled:opacity-40"
              data-testid="coach-start-practice"
            >
              Start practice
              {plan.practicePreview.skills.length
                ? ` (${plan.practicePreview.skills.slice(0, 5).join(', ')})`
                : ''}
            </button>
          </section>
        )}
      </div>
    </main>
  );
}
