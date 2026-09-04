import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, HelpCircle, Clock, ChevronLeft, ChevronRight, Send, AlertCircle } from 'lucide-react';

export default function MCQRound({
  sessionId,
  round = 1,
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
  const questions = questionContext?.questions || [];
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [secondsRemaining, setSecondsRemaining] = useState(() => {
    if (expiresAt) {
      const exp = new Date(expiresAt).getTime();
      const now = Date.now();
      return Math.max(0, Math.floor((exp - now) / 1000));
    }
    const mins = configJson?.duration_minutes || 20;
    return mins * 60;
  });

  // Countdown timer
  useEffect(() => {
    if (currentScore !== null || isScoring || secondsRemaining <= 0) return undefined;
    const interval = setInterval(() => {
      setSecondsRemaining(prev => {
        if (prev <= 1) {
          clearInterval(interval);
          // Auto submit if time expires
          handleSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [currentScore, isScoring, secondsRemaining]);

  const currentQ = questions[currentIndex] || null;
  const totalQuestions = questions.length;
  const answeredCount = Object.keys(answers).length;

  const handleSelectOption = (optId) => {
    if (currentScore !== null || isScoring || !currentQ) return;
    setAnswers(prev => {
      // Toggle if already selected, or select new
      if (prev[currentQ.id] === optId) {
        const next = { ...prev };
        delete next[currentQ.id];
        return next;
      }
      return { ...prev, [currentQ.id]: optId };
    });
  };

  const handleSubmit = () => {
    if (isScoring || currentScore !== null) return;
    onSubmit({ answers });
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Review Summary View after scoring
  if (currentScore !== null) {
    const artifactQuestions =
      currentArtifact?.questions ||
      currentArtifact?.question_results ||
      currentArtifact?.artifact_json?.questions ||
      currentArtifact?.artifact_json?.question_results ||
      [];
    const correctCount =
      currentArtifact?.correct_count ??
      (artifactQuestions.filter(q => q.is_correct).length);
    const incorrectCount =
      currentArtifact?.incorrect_count ??
      (artifactQuestions.filter(q => {
        const hasSelection = Array.isArray(q.selected_option_ids)
          ? q.selected_option_ids.length > 0
          : Boolean(q.selected_option_id);
        return hasSelection && !q.is_correct;
      }).length);
    const unansweredCount =
      currentArtifact?.unanswered_count ??
      (totalQuestions - correctCount - incorrectCount);

    return (
      <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto w-full" data-testid="mcq-review-summary">
        {/* Score Header */}
        <div className="rounded-2xl border border-black/10 bg-white p-6 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <span className="text-xs uppercase tracking-wider text-[#6F6F6F] font-semibold">Assessment Completed</span>
            <h2 className="text-2xl font-bold text-gray-900 mt-1">Multiple Choice Results</h2>
            <p className="text-sm text-gray-500 mt-1">{currentFeedback || 'Your score has been computed deterministically.'}</p>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <span className="block text-3xl font-extrabold text-blue-600">{currentScore.toFixed(1)}%</span>
              <span className="text-xs text-gray-500 uppercase font-medium">Final Score</span>
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
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 rounded-xl border border-green-200 bg-green-50 flex items-center gap-3">
            <CheckCircle2 className="w-6 h-6 text-green-600" />
            <div>
              <span className="block text-xl font-bold text-green-900">{correctCount}</span>
              <span className="text-xs text-green-700">Correct (+1.0)</span>
            </div>
          </div>
          <div className="p-4 rounded-xl border border-red-200 bg-red-50 flex items-center gap-3">
            <XCircle className="w-6 h-6 text-red-600" />
            <div>
              <span className="block text-xl font-bold text-red-900">{incorrectCount}</span>
              <span className="text-xs text-red-700">Incorrect (-{configJson?.negative_marking || 0.25})</span>
            </div>
          </div>
          <div className="p-4 rounded-xl border border-gray-200 bg-gray-50 flex items-center gap-3">
            <HelpCircle className="w-6 h-6 text-gray-500" />
            <div>
              <span className="block text-xl font-bold text-gray-900">{unansweredCount}</span>
              <span className="text-xs text-gray-600">Unanswered (0.0)</span>
            </div>
          </div>
        </div>

        {/* Per-Question Details if available */}
        {artifactQuestions.length > 0 && (
          <div className="rounded-2xl border border-black/10 bg-white p-6 shadow-sm flex flex-col gap-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-700">Question Breakdown</h3>
            <div className="divide-y divide-gray-100">
              {artifactQuestions.map((res, idx) => (
                <div key={res.question_id || idx} className="py-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-gray-400 w-6">#{idx + 1}</span>
                    <span className="text-sm font-medium text-gray-800">
                      {questions[idx]?.stem || `Question ${idx + 1}`}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-gray-500">
                      Selected:{' '}
                      <strong className="uppercase">
                        {Array.isArray(res.selected_option_ids)
                          ? (res.selected_option_ids.join(', ') || 'None')
                          : (res.selected_option_id || 'None')}
                      </strong>
                    </span>
                    {res.is_correct ? (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Correct</span>
                    ) : (Array.isArray(res.selected_option_ids) ? res.selected_option_ids.length > 0 : Boolean(res.selected_option_id)) ? (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">Incorrect</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">Skipped</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Active Assessment View
  return (
    <div className="flex flex-col gap-5 p-6 max-w-4xl mx-auto w-full" data-testid="mcq-round-container">
      {/* Top Header Bar: Question count, timer, submit */}
      <div className="rounded-2xl border border-black/10 bg-white p-4 shadow-sm flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="px-3 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-semibold uppercase">
            MCQ Assessment
          </div>
          <span className="text-sm font-medium text-gray-700">
            Question {currentIndex + 1} of {totalQuestions}
          </span>
          <span className="text-xs text-gray-400">
            ({answeredCount} answered)
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-mono font-bold ${
            secondsRemaining < 120 ? 'bg-red-50 text-red-700 animate-pulse' : 'bg-gray-100 text-gray-700'
          }`}>
            <Clock className="w-3.5 h-3.5" />
            <span>{formatTime(secondsRemaining)}</span>
          </div>

          <button
            onClick={handleSubmit}
            disabled={isScoring}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition"
          >
            <Send className="w-3 h-3" />
            <span>{isScoring ? 'Submitting...' : 'Submit Round'}</span>
          </button>
        </div>
      </div>

      {/* Question Navigation Palette */}
      <div className="flex flex-wrap gap-1.5 p-3 rounded-xl border border-black/5 bg-gray-50/70 items-center justify-center">
        {questions.map((q, idx) => {
          const isAnswered = Boolean(answers[q.id]);
          const isCurrent = idx === currentIndex;
          return (
            <button
              key={q.id || idx}
              onClick={() => setCurrentIndex(idx)}
              className={`w-8 h-8 rounded-lg text-xs font-medium transition ${
                isCurrent
                  ? 'bg-blue-600 text-white shadow-sm ring-2 ring-blue-400/50'
                  : isAnswered
                  ? 'bg-blue-100 text-blue-800 border border-blue-200'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-100'
              }`}
            >
              {idx + 1}
            </button>
          );
        })}
      </div>

      {/* Main Question Card */}
      {currentQ ? (
        <div className="rounded-2xl border border-black/10 bg-white p-6 shadow-sm flex flex-col gap-5">
          {/* Metadata badges */}
          <div className="flex items-center gap-2">
            {currentQ.skill && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                {currentQ.skill}
              </span>
            )}
            {currentQ.sub_domain && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                {currentQ.sub_domain}
              </span>
            )}
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${
              currentQ.difficulty === 'easy'
                ? 'bg-green-50 text-green-700'
                : currentQ.difficulty === 'hard'
                ? 'bg-red-50 text-red-700'
                : 'bg-yellow-50 text-yellow-700'
            }`}>
              {currentQ.difficulty}
            </span>
          </div>

          {/* Stem */}
          <h3 className="text-base font-semibold text-gray-900 leading-relaxed">
            {currentQ.stem}
          </h3>

          {/* Options List */}
          <div className="flex flex-col gap-3 mt-2">
            {(currentQ.options || currentQ.options_json || []).map((opt) => {
              const isSelected = answers[currentQ.id] === opt.id;
              return (
                <button
                  key={opt.id}
                  onClick={() => handleSelectOption(opt.id)}
                  className={`p-4 rounded-xl border text-left transition flex items-start gap-3.5 ${
                    isSelected
                      ? 'border-blue-600 bg-blue-50/50 shadow-sm ring-1 ring-blue-500'
                      : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50/50'
                  }`}
                >
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 uppercase ${
                    isSelected
                      ? 'bg-blue-600 text-white'
                      : 'border border-gray-300 text-gray-600 bg-gray-50'
                  }`}>
                    {opt.id}
                  </span>
                  <span className="text-sm text-gray-800 leading-normal pt-0.5">
                    {opt.text}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Bottom Card Navigation */}
          <div className="flex items-center justify-between pt-4 border-t border-gray-100">
            <button
              onClick={() => setCurrentIndex(prev => Math.max(0, prev - 1))}
              disabled={currentIndex === 0}
              className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" /> Previous
            </button>

            {answers[currentQ.id] && (
              <button
                onClick={() => handleSelectOption(answers[currentQ.id])}
                className="text-xs text-gray-400 hover:text-red-500 transition"
              >
                Clear choice
              </button>
            )}

            <button
              onClick={() => setCurrentIndex(prev => Math.min(totalQuestions - 1, prev + 1))}
              disabled={currentIndex === totalQuestions - 1}
              className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      ) : (
        <div className="p-8 text-center text-gray-500 bg-white rounded-2xl border border-black/10">
          No MCQ questions loaded for this round.
        </div>
      )}
    </div>
  );
}
