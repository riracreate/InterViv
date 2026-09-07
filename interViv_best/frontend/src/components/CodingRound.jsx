import React, { useState, useEffect, useRef } from 'react';
import { Play, Send, CheckCircle2, XCircle, AlertTriangle, Clock, RefreshCw, Code2 } from 'lucide-react';
import { runCodingPreview, saveAnswerDraft, fetchAnswerDraft } from '../lib/api';
import { computeSecondsRemaining } from '../lib/roundContractHelpers';

export default function CodingRound({
  sessionId,
  round = 1,
  question = '',
  questionContext = {},
  configJson = {},
  expiresAt = null,
  isScoring = false,
  currentScore = null,
  currentArtifact = null,
  currentFeedback = '',
  onSubmit,
  onNextRound,
  sessionComplete = false,
}) {
  const starterCode = questionContext?.starter_code
    || '# Write your Python solution here\n';
  const [source, setSource] = useState(starterCode);
  const [activeTab, setActiveTab] = useState('problem'); // 'problem' | 'examples'
  const [isRunning, setIsRunning] = useState(false);
  const [previewResult, setPreviewResult] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const [runUnavailable, setRunUnavailable] = useState(false);
  const [draftNotice, setDraftNotice] = useState('');
  const draftTimer = useRef(null);
  const draftLoadedFor = useRef('');
  const [secondsRemaining, setSecondsRemaining] = useState(() =>
    computeSecondsRemaining(expiresAt, configJson?.duration_minutes || 30)
  );

  useEffect(() => {
    const key = `${sessionId}:${round}`;
    if (!sessionId || currentScore !== null || draftLoadedFor.current === key) return undefined;
    draftLoadedFor.current = key;
    let cancelled = false;
    fetchAnswerDraft(sessionId, round)
      .then((data) => {
        if (cancelled) return;
        const saved = String(data?.draft?.answer_text || '').trim();
        if (saved) {
          setSource(saved);
          setDraftNotice('Restored your saved solution.');
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionId, round, currentScore]);

  useEffect(() => {
    if (!sessionId || currentScore !== null || !source.trim()) return undefined;
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      saveAnswerDraft(sessionId, { round, answer_text: source }).catch(() => {});
    }, 1500);
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, [source, sessionId, round, currentScore]);

  // Countdown timer
  useEffect(() => {
    if (currentScore !== null || isScoring || secondsRemaining <= 0) return undefined;
    const interval = setInterval(() => {
      setSecondsRemaining(prev => {
        if (prev <= 1) {
          clearInterval(interval);
          handleFinalSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [currentScore, isScoring, secondsRemaining]);

  const statement = questionContext?.statement || questionContext?.prompt || question
    || 'Solve the coding problem below.';
  const constraints = questionContext?.constraints || [];
  const visibleTests = questionContext?.visible_tests || [];
  const functionName = questionContext?.function || '';
  const difficulty = questionContext?.difficulty || '';

  const handleRun = async () => {
    if (isRunning || !source.trim()) return;
    setIsRunning(true);
    setPreviewError(null);
    setPreviewResult(null);
    setRunUnavailable(false);
    try {
      const resp = await runCodingPreview({
        session_id: sessionId,
        round,
        source: source.trim(),
      });
      setPreviewResult(resp);
    } catch (err) {
      if (err.status === 503) {
        setRunUnavailable(true);
      } else {
        setPreviewError(err.message || 'Failed to run solution.');
      }
    } finally {
      setIsRunning(false);
    }
  };

  const handleFinalSubmit = () => {
    if (isScoring || currentScore !== null || !source.trim()) return;
    onSubmit({ answer_text: source.trim() });
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const formatValue = (value) => {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  };

  const visibleArtifact = currentArtifact?.visible || {};
  const hiddenArtifact = currentArtifact?.hidden || {};

  return (
    <div className="flex flex-col gap-5 p-6 max-w-6xl mx-auto w-full" data-testid="coding-round-container">
      {/* Top Header Bar */}
      <div className="rounded-2xl border border-black/10 bg-white p-4 shadow-sm flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-semibold uppercase">
            Coding Round
          </div>
          <span className="text-sm font-medium text-gray-700">
            Python Evaluation
          </span>
          {difficulty && (
            <span className="text-xs text-gray-400 capitalize">
              ({difficulty})
            </span>
          )}
        </div>

        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-mono font-bold ${
            secondsRemaining < 120 ? 'bg-red-50 text-red-700 animate-pulse' : 'bg-gray-100 text-gray-700'
          }`}>
            <Clock className="w-3.5 h-3.5" />
            <span>{formatTime(secondsRemaining)}</span>
          </div>

          <button
            onClick={handleFinalSubmit}
            disabled={isScoring || !source.trim() || currentScore !== null}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition"
          >
            <Send className="w-3 h-3" />
            <span>{isScoring ? 'Submitting...' : currentScore !== null ? 'Submitted' : 'Submit Final Solution'}</span>
          </button>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left Column: Statement and Visible Examples */}
        <div className="rounded-2xl border border-black/10 bg-white shadow-sm flex flex-col overflow-hidden h-[540px]">
          {/* Tabs */}
          <div className="flex border-b border-gray-100 bg-gray-50/70 p-1.5 gap-1">
            <button
              onClick={() => setActiveTab('problem')}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition ${
                activeTab === 'problem' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Problem Description
            </button>
            <button
              onClick={() => setActiveTab('examples')}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition ${
                activeTab === 'examples' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Visible Examples
            </button>
          </div>

          {/* Tab Content */}
          <div className="p-5 flex-1 overflow-y-auto">
            {activeTab === 'problem' && (
              <div className="prose prose-sm text-gray-800 max-w-none space-y-3">
                {functionName && (
                  <div className="flex items-center gap-2 text-xs font-mono text-gray-600">
                    <Code2 className="w-3.5 h-3.5" />
                    <span>Implement: {functionName}(...)</span>
                  </div>
                )}
                <div className="whitespace-pre-line text-sm leading-relaxed">
                  {statement}
                </div>
                {constraints.length > 0 && (
                  <div className="flex flex-col gap-1.5 pt-1">
                    <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Constraints</span>
                    <ul className="list-disc pl-5 text-xs text-gray-600 font-mono space-y-0.5">
                      {constraints.map((c, idx) => (
                        <li key={idx}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'examples' && (
              <div className="flex flex-col gap-3">
                <span className="text-xs uppercase tracking-wider text-gray-400 font-mono">Visible Examples</span>
                {visibleTests.length > 0 ? (
                  visibleTests.map((tc, idx) => (
                    <div key={idx} className="flex flex-col gap-1.5 p-3 bg-gray-50 border border-gray-200 rounded-xl">
                      <span className="text-xs font-semibold text-gray-700">Example {idx + 1}</span>
                      <div className="text-xs font-mono text-gray-800">
                        <span className="text-gray-400">Input: </span>
                        {formatValue(tc.input)}
                      </div>
                      <div className="text-xs font-mono text-gray-800">
                        <span className="text-gray-400">Expected: </span>
                        {formatValue(tc.expected)}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-500">No visible examples available.</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Code Editor & Output */}
        <div className="flex flex-col gap-4 h-[540px]">
          {/* Code Editor Box */}
          <div className="rounded-2xl border border-black/10 bg-white shadow-sm flex flex-col flex-1 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-100">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider font-mono">
                Python Editor
                {draftNotice && <span className="ml-2 normal-case text-blue-600" role="status">{draftNotice}</span>}
              </span>
              <button
                onClick={handleRun}
                disabled={isRunning || isScoring || !source.trim()}
                className="flex items-center gap-1.5 px-3 py-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition shadow-sm"
              >
                {isRunning ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                <span>{isRunning ? 'Executing...' : 'Run Examples'}</span>
              </button>
            </div>

            <textarea
              value={source}
              onChange={(e) => setSource(e.target.value)}
              disabled={currentScore !== null || isScoring}
              placeholder="def solve(...):"
              className="flex-1 w-full p-4 font-mono text-xs text-gray-900 bg-white focus:outline-none resize-none leading-relaxed"
              spellCheck={false}
            />
          </div>

          {/* Results / Feedback Panel */}
          <div className="rounded-2xl border border-black/10 bg-white shadow-sm flex flex-col h-[230px] overflow-hidden">
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider font-mono">Run Output</span>
              {previewResult && (
                <span className="text-xs text-gray-400 font-mono">
                  {previewResult.visible_passed} / {previewResult.visible_total} examples passed
                </span>
              )}
            </div>

            <div className="p-3 flex-1 overflow-auto text-xs">
              {runUnavailable && (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Code execution is currently unavailable.</div>
                    <div className="mt-0.5">Your solution is safe in the editor. Final scoring also requires execution — submitting now will not score this round.</div>
                  </div>
                </div>
              )}

              {previewError && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <div className="font-mono text-xs whitespace-pre-wrap">{previewError}</div>
                </div>
              )}

              {previewResult && (
                <div className="flex flex-col gap-2">
                  {(previewResult.visible || []).map((v, idx) => (
                    <div key={idx} className={`p-2.5 rounded-xl border flex items-start gap-2 ${
                      v.passed ? 'bg-green-50/60 border-green-200' : 'bg-red-50/60 border-red-200'
                    }`}>
                      {v.passed ? (
                        <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0 mt-0.5" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                      )}
                      <div className="min-w-0">
                        <span className="block text-xs font-semibold text-gray-800">
                          Example {idx + 1}: {v.passed ? 'Passed' : 'Failed'}
                        </span>
                        {v.error && (
                          <span className="block text-[11px] text-red-600 font-mono whitespace-pre-wrap break-words">
                            {v.error}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!previewResult && !previewError && !runUnavailable && (
                <div className="h-full flex items-center justify-center text-gray-400 font-mono">
                  Click &ldquo;Run Examples&rdquo; to test your solution against the visible examples.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Submission Score & Aggregate Results */}
      {currentScore !== null && (
        <div className="rounded-2xl border border-black/10 bg-white p-6 shadow-sm flex flex-col gap-4" data-testid="coding-review-summary">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Evaluation Score</span>
              <h3 className="text-2xl font-bold text-gray-900 mt-0.5">{currentScore.toFixed(1)}</h3>
              <p className="text-xs text-gray-500 mt-1">{currentFeedback || 'Solution scored deterministically: 60% visible examples, 40% hidden tests.'}</p>
            </div>

            {onNextRound && (
              <button
                onClick={onNextRound}
                className="px-5 py-2.5 bg-gray-900 hover:bg-black text-white rounded-xl text-sm font-medium transition"
              >
                {sessionComplete ? 'View Summary' : 'Next Round'}
              </button>
            )}
          </div>

          {/* Safe Aggregate Evaluation Evidence */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
            <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50 flex flex-col">
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Visible Examples</span>
              <span className="text-lg font-bold text-gray-900 mt-0.5">
                {visibleArtifact.passed ?? 0} / {visibleArtifact.total ?? 0}
              </span>
            </div>
            <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50 flex flex-col">
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Hidden Tests</span>
              <span className="text-lg font-bold text-gray-900 mt-0.5">
                {hiddenArtifact.passed ?? 0} / {hiddenArtifact.total ?? 0}
              </span>
            </div>
            <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50 flex flex-col">
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Cap Applied</span>
              <span className="text-lg font-bold text-gray-900 mt-0.5">
                {currentArtifact?.capped ? 'Yes (25)' : 'No'}
              </span>
            </div>
          </div>

          {/* Visible per-example breakdown (safe: pass/fail only) */}
          {visibleArtifact.cases && visibleArtifact.cases.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
              {visibleArtifact.cases.map((c, idx) => (
                <div key={idx} className={`p-3.5 rounded-xl border flex items-center gap-3 ${
                  c.passed ? 'bg-green-50/50 border-green-200' : 'bg-red-50/50 border-red-200'
                }`}>
                  {c.passed ? (
                    <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-600 shrink-0" />
                  )}
                  <div className="min-w-0">
                    <span className="block text-xs font-semibold text-gray-800">
                      Example {idx + 1}
                    </span>
                    <span className="block text-[11px] text-gray-500 truncate">
                      {c.passed ? 'Passed' : c.error || 'Output mismatch'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
