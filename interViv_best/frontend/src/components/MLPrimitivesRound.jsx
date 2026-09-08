import React, { useEffect, useState } from 'react';
import { AlertTriangle, Clock } from 'lucide-react';
import { fetchAnswerDraft, fetchMLAttempts, saveAnswerDraft, submitAnswer } from '../lib/api';
import { computeSecondsRemaining } from '../lib/roundContractHelpers';

export default function MLPrimitivesRound({ sessionId, round, questionContext = {}, expiresAt, configJson = {} }) {
  const [source, setSource] = useState(questionContext.starter_code || '');
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [seconds, setSeconds] = useState(() => computeSecondsRemaining(expiresAt, configJson.duration_minutes || 30));

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchAnswerDraft(sessionId, round), fetchMLAttempts()])
      .then(([draft, history]) => {
        if (cancelled) return;
        const attempts = history.attempts.filter(a => a.session_id === sessionId && a.round === round)
          .sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
        const last = attempts.at(-1);
        setSaved(Boolean(last));
        const recovered = draft?.draft?.answer_text ?? last?.source;
        if (recovered !== undefined) {
          setSource(recovered);
          setNotice('Restored your saved source.');
        }
      })
      .catch(() => { if (!cancelled) setNotice('Saved source could not be recovered. Reload to retry recovery.'); })
      .finally(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [sessionId, round]);

  useEffect(() => {
    if (!loaded || seconds <= 0) return undefined;
    const timer = setTimeout(() => {
      saveAnswerDraft(sessionId, { round, answer_text: source })
        .catch(() => setNotice('Draft could not be saved. Keep this editor open and retry.'));
    }, 1500);
    return () => clearTimeout(timer);
  }, [source, loaded, sessionId, round, seconds <= 0]);

  useEffect(() => {
    const timer = setInterval(() => setSeconds(computeSecondsRemaining(expiresAt, configJson.duration_minutes || 30)), 1000);
    return () => clearInterval(timer);
  }, [expiresAt, configJson.duration_minutes]);

  async function submit() {
    if (busy || !source.trim() || seconds <= 0) return;
    setBusy(true);
    setError('');
    try {
      await submitAnswer({ session_id: sessionId, round, answer_text: source });
      setError('Unexpected response. Submission status could not be confirmed.');
    } catch (err) {
      if (err.status === 503 && err.detail?.submission_saved === true) {
        setSaved(true);
        setNotice('Submission stored. You can edit and submit again while the round is open.');
      } else {
        setError(err.detail?.message || err.message || 'Submission could not be stored. Please retry.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 p-6" data-testid="ml-primitives-round">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-black/10 bg-white p-4">
        <div><p className="text-sm text-gray-500">ML primitives · Python · {questionContext.difficulty}</p>
          <h1 className="text-xl font-semibold">{questionContext.title}</h1></div>
        <span className="flex items-center gap-2 font-mono"><Clock size={16} />
          {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}
        </span>
      </div>
      <div role="status" className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-800" data-testid="ml-scoring-unavailable">
        <AlertTriangle className="mt-0.5 shrink-0" size={18} />
        <div><p className="font-semibold">Scoring is currently unavailable.</p>
          <p>{saved ? 'Your submission was stored without being run or graded. No score was recorded.'
            : 'You can write and submit a solution. Submissions are stored without being run or graded.'}</p>
          <p>The round stays open for retry. Later blocks wait until this round can be completed.</p></div>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-black/10 bg-white p-5">
          <h2 className="mb-3 font-semibold">Statement</h2>
          <div className="whitespace-pre-wrap text-sm leading-6">{questionContext.statement}</div>
          <h2 className="mb-2 mt-5 font-semibold">Constraints</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">{(questionContext.constraints || []).map(c => <li key={c}>{c}</li>)}</ul>
        </section>
        <section className="flex flex-col gap-3 rounded-2xl border border-black/10 bg-white p-5">
          <label htmlFor="ml-source" className="font-semibold">Python solution</label>
          <textarea id="ml-source" aria-label="Python solution" value={source} disabled={!loaded}
            onChange={e => setSource(e.target.value)} spellCheck={false} maxLength={100000}
            className="min-h-[360px] w-full resize-y rounded-xl border border-gray-300 bg-gray-950 p-4 font-mono text-sm text-gray-100"
          />
          {notice && <p role="status" className="text-sm text-gray-600">{notice}</p>}
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          {seconds <= 0 && <p className="text-sm text-amber-800">The time window has ended. Your source remains available to copy; no score was recorded.</p>}
          <button type="button" onClick={submit} disabled={!loaded || busy || !source.trim() || seconds <= 0}
            className="rounded-xl bg-gray-900 px-4 py-3 font-semibold text-white disabled:opacity-50">
            {busy ? 'Storing submission…' : saved ? 'Submit again (ungraded)' : 'Submit solution (ungraded)'}
          </button>
        </section>
      </div>
    </div>
  );
}
