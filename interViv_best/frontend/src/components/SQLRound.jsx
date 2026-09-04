import React, { useState, useEffect } from 'react';
import { Play, Send, Database, Table, CheckCircle2, XCircle, AlertTriangle, Clock, RefreshCw } from 'lucide-react';
import { runSqlQuery } from '../lib/api';

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
}) {
  const [query, setQuery] = useState(
    questionContext?.reference_query
      ? ''
      : '-- Write your SQL query here\nSELECT '
  );
  const [activeTab, setActiveTab] = useState('problem'); // 'problem' | 'schema' | 'sample'
  const [isRunningQuery, setIsRunningQuery] = useState(false);
  const [previewResult, setPreviewResult] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const [secondsRemaining, setSecondsRemaining] = useState(() => {
    if (expiresAt) {
      const exp = new Date(expiresAt).getTime();
      const now = Date.now();
      return Math.max(0, Math.floor((exp - now) / 1000));
    }
    const mins = configJson?.duration_minutes || 25;
    return mins * 60;
  });

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
    if (isScoring || currentScore !== null || !query.trim()) return;
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
            disabled={isScoring || !query.trim() || currentScore !== null}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition"
          >
            <Send className="w-3 h-3" />
            <span>{isScoring ? 'Submitting...' : currentScore !== null ? 'Submitted' : 'Submit Final Solution'}</span>
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
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider font-mono">SQL Query Editor</span>
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
              disabled={currentScore !== null || isScoring}
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
      {currentScore !== null && (
        <div className="rounded-2xl border border-black/10 bg-white p-6 shadow-sm flex flex-col gap-4" data-testid="sql-review-summary">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Evaluation Score</span>
              <h3 className="text-2xl font-bold text-gray-900 mt-0.5">{currentScore.toFixed(1)}%</h3>
              <p className="text-xs text-gray-500 mt-1">{currentFeedback || 'Query scored deterministically across all test cases.'}</p>
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

          {/* Test Case Breakdown */}
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
