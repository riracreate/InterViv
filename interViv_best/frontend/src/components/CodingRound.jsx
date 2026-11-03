import React, { useEffect, useRef, useState } from 'react';
import { Play, Send, Check, X, Clock3, RotateCcw, Code2, BookOpen, Lightbulb, Terminal } from 'lucide-react';
import { runCodingPreview, saveAnswerDraft, fetchAnswerDraft, fetchCodingExecutionStatus, fetchCodingCoach } from '../lib/api';
import { computeSecondsRemaining } from '../lib/roundContractHelpers';
import CodeEditor from './CodeEditor';
import './coding-workspace.css';

const LABELS = { python: 'Python 3.12', javascript: 'JavaScript', java: 'Java 15', cpp: 'C++17' };
const json = value => value === undefined ? 'No output' : JSON.stringify(value);

export default function CodingRound({ sessionId, round = 1, question = '', questionContext = {},
  configJson = {}, expiresAt = null, isScoring = false, currentScore = null, currentArtifact = null,
  currentFeedback = '', onSubmit, onNextRound, sessionComplete = false, submitted = null, nextBusy = false }) {
  const starters = questionContext.starter_codes || { python: questionContext.starter_code || '# Write your solution here\n' };
  const [language, setLanguage] = useState(configJson.language || 'python');
  const [sources, setSources] = useState(starters);
  const source = sources[language] || '';
  const [tab, setTab] = useState('description');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [running, setRunning] = useState(false);
  const [draftReady, setDraftReady] = useState(false);
  const [draftNotice, setDraftNotice] = useState('Loading saved solution…');
  const [execution, setExecution] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [coach, setCoach] = useState(null);
  const [coachBusy, setCoachBusy] = useState(false);
  const generation = useRef(0);
  const remaining = computeSecondsRemaining(expiresAt, configJson.duration_minutes || 30, now);
  // Result view follows the submission status, scored or not.
  const closed = submitted ?? (currentScore !== null);
  const expired = remaining <= 0;
  const activeLanguage = execution?.languages?.find(item => item.id === language);
  // Only block when the status endpoint says so; an unknown status keeps Run/Submit enabled.
  const executionDown = Boolean(activeLanguage && !activeLanguage.available);
  const tests = questionContext.visible_tests || [];

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchCodingExecutionStatus().then(data => { if (!cancelled) setExecution(data); }).catch(() => {});
    if (closed) { setDraftReady(true); setDraftNotice('Submitted solution'); return; }
    fetchAnswerDraft(sessionId, round).then(({ draft }) => {
      if (cancelled) return;
      const savedLanguage = draft.language || configJson.language || 'python';
      setSources({ ...starters, ...draft.language_sources, [savedLanguage]: draft.answer_text ?? starters[savedLanguage] });
      setLanguage(savedLanguage);
      setDraftNotice('Saved solution restored');
    }).catch(err => {
      if (!cancelled) setDraftNotice(err.status === 404 ? 'Draft ready' : 'Draft recovery unavailable — keep a local copy');
    }).finally(() => { if (!cancelled) setDraftReady(true); });
    return () => { cancelled = true; };
  }, [sessionId, round]);

  useEffect(() => {
    if (!draftReady || closed || expired || isScoring) return;
    const saveGeneration = ++generation.current;
    setDraftNotice('Saving…');
    const timer = setTimeout(() => {
      saveAnswerDraft(sessionId, { round, answer_text: source, language, language_sources: sources })
        .then(() => { if (saveGeneration === generation.current) setDraftNotice('All changes saved'); })
        .catch(err => { if (saveGeneration === generation.current) setDraftNotice(`Not saved: ${err.message}`); });
    }, 1000);
    return () => clearTimeout(timer);
  }, [sources, language, draftReady, closed, expired, isScoring, sessionId, round]);

  const run = async () => {
    if (running || isScoring || closed || expired || executionDown || !draftReady || !source.trim()) return;
    setRunning(true); setError(''); setResult(null);
    try { setResult(await runCodingPreview({ session_id: sessionId, round, source, language })); }
    catch (err) { setError(err.message || 'Execution failed. Your solution remains in the editor.'); }
    finally { setRunning(false); }
  };
  const submit = () => {
    if (!running && !isScoring && !closed && !expired && !executionDown && draftReady && source.trim()) onSubmit({ answer_text: source, language });
  };
  const requestHint = async () => {
    setCoachBusy(true); setError('');
    try { setCoach(await fetchCodingCoach({ session_id: sessionId, round, level: Math.min((coach?.level || 0) + 1, 3) })); }
    catch (err) { setError(err.message); }
    finally { setCoachBusy(false); }
  };
  const totalPassed = (currentArtifact?.visible?.passed || 0) + (currentArtifact?.hidden?.passed || 0);
  const totalTests = (currentArtifact?.visible?.total || 0) + (currentArtifact?.hidden?.total || 0);

  return <section className="coding-workspace" data-testid="coding-round-container">
    <div className="coding-toolbar">
      <div className="coding-title"><Code2 size={19} /><span>Coding practice</span><span className="coding-round-label">Round {round}</span></div>
      <div className="coding-actions">
        <span className={`coding-clock ${expired ? 'is-expired' : ''}`}><Clock3 size={15} />{String(Math.floor(remaining / 60)).padStart(2, '0')}:{String(remaining % 60).padStart(2, '0')}</span>
        <button className="coding-button" onClick={run} disabled={running || isScoring || closed || expired || executionDown || !draftReady}><Play size={15} />{running ? 'Running…' : 'Run'}</button>
        <button className="coding-button coding-submit" onClick={submit} disabled={running || isScoring || closed || expired || executionDown || !draftReady}><Send size={14} />{isScoring ? 'Submitting…' : closed ? 'Submitted' : 'Submit'}</button>
      </div>
    </div>
    <div className="coding-panes">
      <aside className="coding-description">
        <div className="coding-tabs" role="tablist" aria-label="Problem information">
          <button role="tab" aria-selected={tab === 'description'} onClick={() => setTab('description')}><BookOpen size={14} />Description</button>
          <button role="tab" aria-selected={tab === 'coach'} onClick={() => setTab('coach')}><Lightbulb size={14} />Coach</button>
        </div>
        <div className="coding-problem-body" role="tabpanel">
          {tab === 'description' ? <>
            <span className={`coding-difficulty ${questionContext.difficulty || 'easy'}`}>{questionContext.difficulty || 'Practice'}</span>
            <h1>{questionContext.title || question}</h1>
            <div className="coding-tags">{questionContext.topics?.map(t => <span key={t}>{t.replaceAll('_', ' ')}</span>)}</div>
            <p className="coding-statement">{questionContext.statement || questionContext.prompt || question}</p>
            <p className="coding-signature">Implement <code>{questionContext.function}(…)</code>. Return the result; the test driver calls your function.</p>
            {tests.map((test, index) => <div className="coding-example" key={index}>
              <h3>Example {index + 1}</h3><dl><dt>Input</dt><dd><code>{json(test.input.args ?? test.input)}</code></dd><dt>Output</dt><dd><code>{json(test.expected)}</code></dd></dl>
            </div>)}
            <h3>Constraints</h3><ul className="coding-constraints">{questionContext.constraints?.map(c => <li key={c}>{c}</li>)}</ul>
            <p className="coding-attribution">Original interViv exercise · Test-based evaluation</p>
          </> : <>
            <span className="coding-eyebrow">Build the reasoning</span><h2>A nudge, when you need it.</h2>
            <p>Reveal one hint at a time. Hints are recorded as assistance; they do not change the test verdict.</p>
            {coach && <div className="coding-hint"><span>{coach.kind === 'ai' ? 'AI explanation' : 'Curated hint'} · {coach.level}/3</span><p>{coach.hint}</p>{coach.ai_withheld && <p className="coding-muted">The local model's hint contained solution code, so a curated hint is shown instead.</p>}</div>}
            <button className="coding-button" disabled={coachBusy || coach?.level === 3} onClick={requestHint}><Lightbulb size={15} />{coachBusy ? 'Loading…' : coach ? 'Next hint' : 'Get a hint'}</button>
            <p className="coding-attribution">AI coaching requires a separately configured local model. Scores always come from execution results.</p>
          </>}
        </div>
      </aside>
      <div className="coding-right">
        <div className="coding-editor-panel">
          <div className="coding-editor-toolbar"><label className="sr-only" htmlFor="coding-language">Programming language</label>
            <select id="coding-language" value={language} disabled={!draftReady || closed || running || isScoring} onChange={event => { setLanguage(event.target.value); setResult(null); setError(''); }}>
              {Object.keys(starters).map(id => <option key={id} value={id}>{LABELS[id] || id}</option>)}
            </select>
            <span className="coding-draft-status" role="status">{draftNotice}</span>
            <button className="coding-reset" title="Reset current language to starter" aria-label="Reset current language to starter" disabled={closed || isScoring || !draftReady} onClick={() => { if (window.confirm('Replace this language’s draft with the starter code?')) setSources(p => ({ ...p, [language]: starters[language] })); }}><RotateCcw size={15} /></button>
          </div>
          <CodeEditor value={source} language={language} documentKey={`${sessionId}:${round}:${language}`} readOnly={!draftReady || closed || isScoring}
            onChange={value => setSources(previous => ({ ...previous, [language]: value }))} onRun={run} onSubmit={submit} />
          <div className="coding-editor-footer"><span>{source.split('\n').length} lines · UTF-8</span><span>⌘/Ctrl + Enter to run</span></div>
        </div>
        <div className="coding-console" aria-live="polite">
          <div className="coding-console-title"><Terminal size={15} /><span>Test results</span>{result && <strong>{result.visible_passed}/{result.visible_total} passed</strong>}</div>
          <div className="coding-console-body">
            {expired && !closed && <p className="coding-warning" role="alert">This round has ended. Your code remains available to copy; start a new practice round to run it.</p>}
            {executionDown && !closed && <p className="coding-warning" data-testid="coding-execution-down">{LABELS[language]} execution is unavailable, so Run and Submit are off. Your draft is still saved.</p>}
            {(error || (!closed && currentFeedback)) && <p className="coding-error" role="alert">{error || currentFeedback}</p>}
            {running && <p className="coding-muted">Running visible examples in the execution service…</p>}
            {!result && !error && !running && !closed && <div className="coding-console-empty"><Terminal size={25} /><p>Your next idea starts here.</p><span>Run checks the examples. Submit also runs hidden tests.</span></div>}
            {result?.visible?.map((item, index) => <div className={`coding-test-case ${item.passed ? 'passed' : 'failed'}`} key={index}>
              <div>{item.passed ? <Check size={15} /> : <X size={15} />}<strong>Case {index + 1}</strong><span>{item.passed ? 'Passed' : item.error || 'Failed'}</span></div>
              {!item.passed && <><p>Expected <code>{json(tests[index]?.expected)}</code></p><p>Returned <code>{json(item.actual)}</code></p>{item.message && <pre>{item.message}</pre>}</>}
            </div>)}
            {closed && <div className="coding-verdict" data-testid="coding-review-summary"><h2>{totalTests > 0 && totalPassed === totalTests ? 'Accepted' : 'Tests not passed'}</h2><p>{totalPassed}/{totalTests} tests passed · Score {currentScore == null ? 'not recorded' : `${currentScore.toFixed(1)}/100`}</p><p>{currentFeedback}</p>{onNextRound && <button className="coding-button" disabled={nextBusy} onClick={onNextRound}>{sessionComplete ? 'View report' : (nextBusy ? 'Opening…' : 'Next round')}</button>}</div>}
          </div>
        </div>
      </div>
    </div>
  </section>;
}
