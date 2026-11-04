import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock, XCircle } from 'lucide-react';
import { fetchAnswerDraft, fetchMLAttempts, saveAnswerDraft, submitAnswer } from '../lib/api';
import { computeSecondsRemaining } from '../lib/roundContractHelpers';

const ERROR_LABELS = {
  mismatch: 'Wrong values',
  runtime: 'Raised an error',
  timeout: 'Time limit',
  memory: 'Memory limit',
  output_limit: 'Too much output',
  invalid_output: 'Not a NumPy array',
  load: 'Module did not load',
  syntax: 'Syntax error',
  prohibited_import: 'Import not allowed',
};

/**
 * ML primitives round. When the server can execute NumPy (trusted local
 * runner), submission goes through the shared session path: the result
 * stays visible until Next. Otherwise the source is stored ungraded and the
 * round stays open for retry.
 */
export default function MLPrimitivesRound({
  sessionId,
  round,
  questionContext = {},
  expiresAt,
  configJson = {},
  isScoring = false,
  currentScore = null,
  currentArtifact = null,
  currentFeedback = '',
  onSubmit,
  onNextRound,
  sessionComplete = false,
  submitted = null,
  nextBusy = false,
}) {
  const scoringAvailable = configJson.scoring_available === true;
  const closed = submitted ?? (currentScore !== null);
  const [source, setSource] = useState(questionContext.starter_code || '');
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [seconds, setSeconds] = useState(() => computeSecondsRemaining(expiresAt, configJson.duration_minutes || 30));

  useEffect(() => {
    let cancelled = false;
    if (closed) { setLoaded(true); return undefined; }
    Promise.all([fetchAnswerDraft(sessionId, round).catch(() => null), fetchMLAttempts()])
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
  }, [sessionId, round, closed]);

  useEffect(() => {
    if (!loaded || closed || seconds <= 0) return undefined;
    const timer = setTimeout(() => {
      saveAnswerDraft(sessionId, { round, answer_text: source })
        .catch(() => setNotice('Draft could not be saved. Keep this editor open and retry.'));
    }, 1500);
    return () => clearTimeout(timer);
  }, [source, loaded, closed, sessionId, round, seconds <= 0]);

  useEffect(() => {
    if (closed) return undefined;
    const timer = setInterval(() => setSeconds(computeSecondsRemaining(expiresAt, configJson.duration_minutes || 30)), 1000);
    return () => clearInterval(timer);
  }, [expiresAt, configJson.duration_minutes, closed]);

  async function storeUngraded() {
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

  function submit() {
    if (busy || isScoring || closed || !source.trim() || seconds <= 0) return;
    if (scoringAvailable && onSubmit) onSubmit({ answer_text: source });
    else storeUngraded();
  }

  const cases = currentArtifact?.cases || [];
  const properties = currentArtifact?.properties || [];
  const findings = currentArtifact?.static_findings || [];

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 p-6" data-testid="ml-primitives-round">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--color-border)] bg-white p-4">
        <div><p className="text-sm text-gray-500">ML primitives · Python + NumPy · {questionContext.difficulty}</p>
          <h1 className="text-xl font-semibold">{questionContext.title}</h1></div>
        {!closed && (
          <span className="flex items-center gap-2 font-mono"><Clock size={16} />
            {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}
          </span>
        )}
      </div>
      {!scoringAvailable && !closed && (
        <div role="status" className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-800" data-testid="ml-scoring-unavailable">
          <AlertTriangle className="mt-0.5 shrink-0" size={18} />
          <div><p className="font-semibold">Scoring is currently unavailable.</p>
            <p>{saved ? 'Your submission was stored without being run or graded. No score was recorded.'
              : 'You can write and submit a solution. Submissions are stored without being run or graded.'}</p>
            <p>The round stays open for retry. Later blocks wait until this round can be completed.</p></div>
        </div>
      )}
      {closed && (
        <section className="rounded-2xl border border-[var(--color-border)] bg-white p-5" data-testid="ml-review-summary">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-wider text-gray-500">Numerical checks</p>
              <p className="text-3xl font-semibold">{currentScore == null ? 'Not scored' : `${Number(currentScore).toFixed(1)}%`}</p>
              <p className="text-sm text-gray-600">
                {currentArtifact?.cases_total
                  ? `${currentArtifact.cases_passed}/${currentArtifact.cases_total} cases passed every check`
                  : currentFeedback}
              </p>
            </div>
            {onNextRound && (
              <button type="button" onClick={onNextRound} disabled={nextBusy}
                className="rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">
                {sessionComplete ? 'View report' : (nextBusy ? 'Opening…' : 'Next round')}
              </button>
            )}
          </div>
          {cases.length > 0 && (
            <ul className="mt-4 grid gap-2 sm:grid-cols-2" aria-label="Case results">
              {cases.map(item => (
                <li key={item.case_id} className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
                  {item.passed
                    ? <CheckCircle2 size={16} className="text-emerald-600" aria-hidden="true" />
                    : <XCircle size={16} className="text-red-600" aria-hidden="true" />}
                  <span className="font-mono">{item.case_id}</span>
                  {!item.passed && <span className="ml-auto text-xs text-gray-600">{ERROR_LABELS[item.error] || 'Failed'}</span>}
                </li>
              ))}
            </ul>
          )}
          {properties.length > 0 && (
            <p className="mt-3 text-sm text-gray-700">
              Checks: {properties.map(p => `${p.name} ${p.passed ? '✓' : '✗'}`).join(' · ')}
            </p>
          )}
          {findings.length > 0 && (
            <p className="mt-2 text-sm text-gray-600">
              Code signals (not scored): {[...new Set(findings.map(f => f.name))].join(', ')}
            </p>
          )}
          {currentFeedback && cases.length > 0 && <p className="mt-2 text-sm text-gray-600">{currentFeedback}</p>}
        </section>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-[var(--color-border)] bg-white p-5">
          <h2 className="mb-3 font-semibold">Statement</h2>
          <div className="whitespace-pre-wrap text-sm leading-6">{questionContext.statement}</div>
          <h2 className="mb-2 mt-5 font-semibold">Constraints</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">{(questionContext.constraints || []).map(c => <li key={c}>{c}</li>)}</ul>
        </section>
        <section className="flex flex-col gap-3 rounded-2xl border border-[var(--color-border)] bg-white p-5">
          <label htmlFor="ml-source" className="font-semibold">Python solution</label>
          <textarea id="ml-source" aria-label="Python solution" value={source} disabled={!loaded || closed}
            onChange={e => setSource(e.target.value)} spellCheck={false} maxLength={100000}
            className="min-h-[360px] w-full resize-y rounded-xl border border-gray-300 bg-gray-950 p-4 font-mono text-sm text-gray-100"
          />
          {notice && <p role="status" className="text-sm text-gray-600">{notice}</p>}
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          {seconds <= 0 && !closed && <p className="text-sm text-amber-800">The time window has ended. Your source remains available to copy; no score was recorded.</p>}
          {!closed && (
            <button type="button" onClick={submit} disabled={!loaded || busy || isScoring || !source.trim() || seconds <= 0}
              className="rounded-xl bg-gray-900 px-4 py-3 font-semibold text-white disabled:opacity-50">
              {scoringAvailable
                ? (isScoring ? 'Running checks…' : 'Submit solution')
                : (busy ? 'Storing submission…' : saved ? 'Submit again (ungraded)' : 'Submit solution (ungraded)')}
            </button>
          )}
        </section>
      </div>
    </div>
  );
}
