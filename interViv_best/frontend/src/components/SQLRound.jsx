import React, { useState, useEffect, useRef } from 'react';
import { Play, Send, Database, Table, CheckCircle2, XCircle, AlertTriangle, Clock, RefreshCw } from 'lucide-react';
import { runSqlQuery, saveAnswerDraft, fetchAnswerDraft } from '../lib/api';
import { computeSecondsRemaining } from '../lib/roundContractHelpers';

export default function SQLRound({
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
  submitted = null,
  nextBusy = false,
}) {
  // Result view follows the submission status, scored or not.
  const closed = submitted ?? (currentScore !== null);
  const [query, setQuery] = useState(
    questionContext?.reference_query
      ? ''
      : '-- Write your SQL query here\nSELECT '
  );
  const [activeTab, setActiveTab] = useState('problem'); // 'problem' | 'schema' | 'sample'
  const [isRunningQuery, setIsRunningQuery] = useState(false);
  const [previewResult, setPreviewResult] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const [draftNotice, setDraftNotice] = useState('');
  const draftTimer = useRef(null);
  const draftLoadedFor = useRef('');
  const [secondsRemaining, setSecondsRemaining] = useState(() =>
    computeSecondsRemaining(expiresAt, configJson?.duration_minutes || 25)
  );

  useEffect(() => {
    const key = `${sessionId}:${round}`;
    if (!sessionId || closed || draftLoadedFor.current === key) return undefined;
    draftLoadedFor.current = key;
    let cancelled = false;
    fetchAnswerDraft(sessionId, round)
      .then((data) => {
        if (cancelled) return;
        const saved = String(data?.draft?.answer_text || '').trim();
        if (saved) {
          setQuery(saved);
          setDraftNotice('Restored your saved query.');
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionId, round, closed]);

  useEffect(() => {
    if (!sessionId || closed || !query.trim()) return undefined;
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      saveAnswerDraft(sessionId, { round, answer_text: query }).catch(() => {});
    }, 1500);
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, [query, sessionId, round, closed]);

  // Countdown timer
  useEffect(() => {
    if (closed || isScoring || secondsRemaining <= 0) return undefined;
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
  }, [closed, isScoring, secondsRemaining]);

  const schemaDdl = questionContext?.schema_ddl || '';
  const sampleCases = questionContext?.sample_cases || [];
  const promptText = questionContext?.prompt || question || 'Write a SQL query to solve the problem.';

  const handleRunQuery = async () => {
    if (isRunningQuery || !query.trim()) return;
    setIsRunningQuery(true);
    setPreviewError(null);
    setPreviewResult(null);
    try {
      const resp = await runSqlQuery({
        session_id: sessionId,
        round,
        query: query.trim(),
      });
      if (!resp.error) {
        setPreviewResult(resp);
      } else {
        setPreviewError(resp.error || 'Execution failed.');
      }
    } catch (err) {
      setPreviewError(err.message || 'Failed to preview query.');
    } finally {
      setIsRunningQuery(false);
    }
  };

  const handleFinalSubmit = () => {
    if (isScoring || closed || !query.trim()) return;
    onSubmit({ answer_text: query.trim() });
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col gap-5 p-6 max-w-6xl mx-auto w-full" data-testid="sql-round-container">
      {/* Top Header Bar */}
      <div className="rounded-2xl border border-black/10 bg-white p-4 shadow-sm flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-semibold uppercase">
            SQL Round
          </div>
          <span className="text-sm font-medium text-gray-700">
            Problem Evaluation
          </span>
          {configJson?.timeout_seconds && (
            <span className="text-xs text-gray-400">
              ({configJson.timeout_seconds}s timeout per case)
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
            disabled={isScoring || !query.trim() || closed}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition"
          >
            <Send className="w-3 h-3" />
            <span>{isScoring ? 'Submitting...' : closed ? 'Submitted' : 'Submit Final Solution'}</span>
          </button>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left Column: Problem, Schema, and Sample Data */}
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
              onClick={() => setActiveTab('schema')}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition ${
                activeTab === 'schema' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Table Schema (DDL)
            </button>
            <button
              onClick={() => setActiveTab('sample')}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition ${
                activeTab === 'sample' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Sample Data
            </button>
          </div>

          {/* Tab Content */}
          <div className="p-5 flex-1 overflow-y-auto">
            {activeTab === 'problem' && (
              <div className="prose prose-sm text-gray-800 max-w-none space-y-3">
                <div className="whitespace-pre-line text-sm leading-relaxed">
                  {promptText}
                </div>
              </div>
            )}

            {activeTab === 'schema' && (
              <div className="flex flex-col gap-2">
                <span className="text-xs uppercase tracking-wider text-gray-400 font-mono">SQLite Schema Definition</span>
                <pre className="p-3 bg-gray-900 text-gray-100 rounded-xl text-xs font-mono overflow-x-auto whitespace-pre">
                  {schemaDdl.trim() || '-- No DDL provided'}
                </pre>
              </div>
            )}

            {activeTab === 'sample' && (
              <div className="flex flex-col gap-3">
                <span className="text-xs uppercase tracking-wider text-gray-400 font-mono">Visible Sample Case</span>
                {sampleCases.length > 0 ? (
                  sampleCases.map((sc, idx) => (
                    <div key={idx} className="flex flex-col gap-1.5">
                      <span className="text-xs font-semibold text-gray-700">{sc.description || `Sample ${idx + 1}`}</span>
                      <pre className="p-3 bg-gray-50 border border-gray-200 text-gray-800 rounded-xl text-xs font-mono overflow-x-auto whitespace-pre">
                        {(sc.seed_data || '').trim()}
                      </pre>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-500">No visible sample case data available.</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Query Editor & Output */}
        <div className="flex flex-col gap-4 h-[540px]">
          {/* Query Editor Box */}
          <div className="rounded-2xl border border-black/10 bg-white shadow-sm flex flex-col flex-1 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-100">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider font-mono">
                SQL Query Editor
                {draftNotice && <span className="ml-2 normal-case text-blue-600" role="status">{draftNotice}</span>}
              </span>
              <button
                onClick={handleRunQuery}
                disabled={isRunningQuery || isScoring || !query.trim()}
                className="flex items-center gap-1.5 px-3 py-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition shadow-sm"
              >
                {isRunningQuery ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                <span>{isRunningQuery ? 'Executing...' : 'Run Query'}</span>
              </button>
            </div>

            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={closed || isScoring}
              placeholder="SELECT ... FROM ...;"
              className="flex-1 w-full p-4 font-mono text-xs text-gray-900 bg-white focus:outline-none resize-none leading-relaxed"
              spellCheck={false}
            />
          </div>

          {/* Results / Feedback Panel */}
          <div className="rounded-2xl border border-black/10 bg-white shadow-sm flex flex-col h-[230px] overflow-hidden">
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider font-mono">Query Execution Output</span>
              {previewResult && (
                <span className="text-xs text-gray-400 font-mono">
                  {previewResult.row_count} row{previewResult.row_count !== 1 ? 's' : ''} in {previewResult.execution_time_ms.toFixed(2)}ms
                </span>
              )}
            </div>

            <div className="p-3 flex-1 overflow-auto text-xs">
              {previewError && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <div className="font-mono text-xs whitespace-pre-wrap">{previewError}</div>
                </div>
              )}

              {previewResult && (
                previewResult.rows && previewResult.rows.length > 0 ? (
                  <table className="min-w-full divide-y divide-gray-200 text-left">
                    <thead className="bg-gray-50">
                      <tr>
                        {(previewResult.columns || []).map((col, idx) => (
                          <th key={idx} className="px-3 py-1.5 font-semibold text-gray-700 font-mono text-xs">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 bg-white">
                      {previewResult.rows.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-gray-50/50">
                          {row.map((cell, cIdx) => (
                            <td key={cIdx} className="px-3 py-1.5 text-gray-800 font-mono whitespace-nowrap">
                              {cell === null ? <em className="text-gray-400">NULL</em> : String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="p-4 text-center text-gray-400 font-mono">
                    Query executed successfully. 0 rows returned.
                  </div>
                )
              )}

              {!previewResult && !previewError && (
                <div className="h-full flex items-center justify-center text-gray-400 font-mono">
                  Click &ldquo;Run Query&rdquo; to test your query against the sample dataset.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Submission Score & Test Case Results */}
      {closed && (
        <div className="rounded-2xl border border-black/10 bg-white p-6 shadow-sm flex flex-col gap-4" data-testid="sql-review-summary">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Evaluation Score</span>
              <h3 className="text-2xl font-bold text-gray-900 mt-0.5">{currentScore == null ? 'Not scored' : `${currentScore.toFixed(1)}%`}</h3>
              <p className="text-xs text-gray-500 mt-1">{currentFeedback || 'Query scored deterministically across all test cases.'}</p>
            </div>

            {onNextRound && (
              <button
                onClick={onNextRound}
                disabled={nextBusy}
                className="px-5 py-2.5 bg-gray-900 hover:bg-black text-white rounded-xl text-sm font-medium transition"
              >
                {sessionComplete ? 'View report' : (nextBusy ? 'Opening…' : 'Next Round')}
              </button>
            )}
          </div>

          {/* Safe Aggregate Evaluation Evidence */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
            <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50 flex flex-col">
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Cases Passed</span>
              <span className="text-lg font-bold text-gray-900 mt-0.5">
                {(currentArtifact?.cases_passed ?? currentArtifact?.passed_cases ?? (currentArtifact?.cases ? currentArtifact.cases.filter(c => c.passed).length : 0))} / {(currentArtifact?.evaluation_cases ?? currentArtifact?.total_cases ?? currentArtifact?.cases?.length ?? 0)}
              </span>
            </div>
            <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50 flex flex-col">
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Result Equality</span>
              <span className="text-lg font-bold text-gray-900 mt-0.5">
                {(currentArtifact?.result_equality_points ?? 0).toFixed(1)} / 60.0
              </span>
            </div>
            <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50 flex flex-col">
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Row Count</span>
              <span className="text-lg font-bold text-gray-900 mt-0.5">
                {(currentArtifact?.row_count_points ?? 0).toFixed(1)} / 20.0
              </span>
            </div>
            <div className="p-3.5 rounded-xl border border-gray-200 bg-gray-50/50 flex flex-col">
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Constraints</span>
              <span className="text-lg font-bold text-gray-900 mt-0.5">
                {(currentArtifact?.constraint_points ?? 20.0).toFixed(1)} / 20.0
              </span>
            </div>
          </div>

          {/* Test Case Breakdown if available for backward compatibility */}
          {currentArtifact?.cases && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
              {currentArtifact.cases.map((c, idx) => (
                <div key={idx} className={`p-3.5 rounded-xl border flex items-center gap-3 ${
                  c.passed ? 'bg-green-50/50 border-green-200' : 'bg-red-50/50 border-red-200'
                }`}>
                  {c.passed ? (
                    <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-600 shrink-0" />
                  )}
                  <div className="min-w-0">
                    <span className="block text-xs font-semibold capitalize text-gray-800">
                      {c.case_type === 'sample' ? 'Sample Case' : `Evaluation Case ${idx}`}
                    </span>
                    <span className="block text-[11px] text-gray-500 truncate">
                      {c.description || (c.passed ? 'Passed equality and row count' : c.error || 'Result mismatch')}
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
