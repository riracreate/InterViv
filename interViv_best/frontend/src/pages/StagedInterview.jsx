import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import AppNav from '../components/AppNav';
import { createStagedSessionController, stagedSessionState } from '../lib/stagedSession';

const STAGE_LABELS = { warm_up: 'Warm-up', core: 'Core', follow_up: 'Follow-up', behavioural: 'Behavioural' };

export default function StagedInterview({ session }) {
  const [view, setView] = useState(() => stagedSessionState(session));
  const [answer, setAnswer] = useState('');
  const [draftReady, setDraftReady] = useState(false);
  const [draftNotice, setDraftNotice] = useState('Loading saved answer…');
  const controller = useRef(null);
  const dirty = useRef(false);

  useEffect(() => {
    const current = createStagedSessionController({ session, onChange: setView });
    controller.current = current;
    setView(current.snapshot());
    return () => { current.dispose(); controller.current = null; };
  }, [session]);

  const round = view.active?.round;
  useEffect(() => {
    let cancelled = false;
    dirty.current = false;
    setAnswer('');
    setDraftReady(false);
    if (view.phase !== 'answering' || view.active?.type !== 'technical_short_answer') return undefined;
    setDraftNotice('Loading saved answer…');
    controller.current.readDraft(round).then(saved => {
      if (!cancelled) { setAnswer(saved || ''); setDraftNotice(saved ? 'Saved answer restored.' : 'Your answer saves as you type.'); }
    }).catch(() => {
      if (!cancelled) setDraftNotice('The saved answer could not be loaded. You can type an answer and retry saving.');
    }).finally(() => { if (!cancelled) setDraftReady(true); });
    return () => { cancelled = true; };
  }, [session.session_id, round, view.phase, view.active?.type]);

  useEffect(() => {
    if (!draftReady || !dirty.current || view.phase !== 'answering' || view.busy) return undefined;
    let cancelled = false;
    const timer = setTimeout(() => {
      setDraftNotice('Saving answer…');
      controller.current.saveDraft(round, answer).then(saved => {
        if (!cancelled && saved) setDraftNotice('Answer saved.');
      }).catch(() => { if (!cancelled) setDraftNotice('Answer could not be saved. Your text is still here; submit it or retry saving.'); });
    }, 600);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [answer, draftReady, round, view.phase, view.busy]);

  const supported = view.active?.type === 'technical_short_answer';
  const locked = view.busy || view.needsRefresh || !draftReady;
  const stageLabel = STAGE_LABELS[view.active?.stage || view.stage] || 'Interview';
  return <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-ink)]">
    <div className="app-container">
      <AppNav />
      <main className="mx-auto max-w-3xl px-4 py-8 sm:py-12" data-testid="staged-interview">
        <header className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">{view.preset === 'full' ? 'Full' : 'Quick'} interview</p>
          <h1 className="mt-2 text-3xl font-semibold">{view.phase === 'completed' ? 'Interview complete' : stageLabel}</h1>
          <p className="mt-3 text-sm text-[var(--color-ink-muted)]">{view.answeredCount} of {view.totalRounds} answers saved</p>
        </header>

        {view.error && <div role="alert" className="mb-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <p>{view.error}</p>
          <button type="button" className="app-button mt-3" disabled={view.busy} onClick={() => controller.current.refresh()}>Refresh interview</button>
        </div>}

        {view.phase === 'completed' ? <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-6">
          <h2 className="text-xl font-semibold">Your answers are saved.</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]">Open your dashboard to review this interview.</p>
          <Link className="app-button app-button-primary mt-5" to={`/dashboard/${encodeURIComponent(view.sessionId)}`}>View dashboard</Link>
        </section> : view.phase === 'blocked' ? <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-6" role="status">
          <h2 className="text-xl font-semibold">Answer saved; next question unavailable</h2>
          <p className="mt-3 text-sm leading-6">{view.blockedReason}</p>
          <button type="button" className="app-button mt-5" disabled={view.busy || view.needsRefresh} onClick={() => controller.current.retryBlocked()}>{view.busy ? 'Checking…' : 'Retry continuation'}</button>
        </section> : view.phase === 'ready' ? <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-6" role="status">
          <h2 className="text-xl font-semibold">Answer saved</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]">Continue when you are ready for the next question. Evaluations stay hidden until the interview is complete.</p>
          <button type="button" className="app-button app-button-primary mt-5" disabled={view.busy || view.needsRefresh} onClick={() => controller.current.advance()}>{view.busy ? 'Opening…' : 'Continue interview'}</button>
        </section> : view.phase === 'answering' && supported ? <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5 sm:p-7">
          <div className="flex flex-wrap items-center gap-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">
            <span>Question {round} of {view.totalRounds}</span>
            {view.active.skill && <span>{view.active.skill}</span>}
            {view.active.isFollowUp && <span>Follow-up{view.active.parentRound ? ` to question ${view.active.parentRound}` : ''}</span>}
          </div>
          <h2 className="mt-4 text-xl font-medium leading-8">{view.active.question}</h2>
          {view.active.expiresAt && <p className="mt-3 text-xs text-[var(--color-ink-muted)]">Round ends at <time dateTime={view.active.expiresAt}>{new Date(view.active.expiresAt).toLocaleTimeString()}</time>.</p>}
          <form className="mt-6" onSubmit={event => { event.preventDefault(); if (!locked && answer.trim()) controller.current.submit(answer); }}>
            <label htmlFor="staged-answer" className="block text-sm font-semibold">Your answer</label>
            <textarea id="staged-answer" value={answer} disabled={locked} onChange={event => { dirty.current = true; setAnswer(event.target.value); }} rows={9}
              className="mt-2 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-4 text-base leading-7 disabled:opacity-60" />
            <p className="mt-2 text-xs text-[var(--color-ink-muted)]" role="status">{draftNotice}</p>
            <button type="submit" className="app-button app-button-primary mt-5" disabled={locked || !answer.trim()}>{view.busy ? 'Saving answer…' : 'Submit answer'}</button>
          </form>
        </section> : <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
          <h2 className="text-xl font-semibold">This round is unavailable on this screen</h2>
          <p className="mt-3 text-sm">Your progress is saved. You can refresh this interview or return to practice.</p>
          <button type="button" className="app-button mt-5" disabled={view.busy} onClick={() => controller.current.refresh()}>Refresh interview</button>
        </section>}
        <Link className="mt-6 inline-block text-sm underline" to="/practice">Back to practice</Link>
      </main>
    </div>
  </div>;
}
