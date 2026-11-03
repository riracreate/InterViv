import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Send, Clock, RefreshCw, LayoutTemplate } from 'lucide-react';
import { saveAnswerDraft, fetchAnswerDraft } from '../lib/api';
import { computeSecondsRemaining } from '../lib/roundContractHelpers';

/**
 * System-design practice: free-text design notes + structured self-assessment.
 * Diagrams are not auto-scored. Evaluation mode is labeled on screen.
 */
export default function SystemDesignRound({
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
  evaluationMode = null,
  evaluationBoundary = null,
  onSubmit,
  onNextRound,
  sessionComplete = false,
  submitted = null,
  nextBusy = false,
}) {
  // Result view follows the submission status, scored or not.
  const closed = submitted ?? (currentScore !== null);
  const rubric = useMemo(
    () => listRubric(questionContext),
    [questionContext],
  );
  const [answer, setAnswer] = useState('');
  const [ratings, setRatings] = useState(() => Object.fromEntries(rubric.map((c) => [c.id, ''])));
  const [draftNotice, setDraftNotice] = useState('');
  const [localError, setLocalError] = useState('');
  const draftTimer = useRef(null);
  const draftLoadedFor = useRef('');
  const [secondsRemaining, setSecondsRemaining] = useState(() =>
    computeSecondsRemaining(expiresAt, configJson?.duration_minutes || 25),
  );

  useEffect(() => {
    const key = `${sessionId}:${round}`;
    if (!sessionId || closed || draftLoadedFor.current === key) return undefined;
    draftLoadedFor.current = key;
    let cancelled = false;
    fetchAnswerDraft(sessionId, round)
      .then((data) => {
        if (cancelled) return;
        const saved = data?.draft || {};
        if (saved.answer_text) setAnswer(String(saved.answer_text));
        if (saved.rubric_ratings && typeof saved.rubric_ratings === 'object') {
          setRatings((prev) => ({ ...prev, ...saved.rubric_ratings }));
        }
        if (saved.answer_text || saved.rubric_ratings) {
          setDraftNotice('Restored your saved design notes.');
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionId, round, closed]);

  useEffect(() => {
    if (!sessionId || closed) return undefined;
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      saveAnswerDraft(sessionId, {
        round,
        answer_text: answer,
        rubric_ratings: ratings,
      }).catch(() => {});
    }, 1500);
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, [answer, ratings, sessionId, round, closed]);

  useEffect(() => {
    if (closed || isScoring || secondsRemaining <= 0) return undefined;
    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [closed, isScoring, secondsRemaining]);

  const boundary =
    evaluationBoundary
    || questionContext?.evaluation_boundary
    || 'Structured self-assessment only. Diagrams are not auto-scored.';
  const mode =
    evaluationMode
    || configJson?.evaluation_mode
    || 'structured_self_assessment';

  const handleSubmit = () => {
    setLocalError('');
    const missing = rubric.filter((c) => {
      const v = Number(ratings[c.id]);
      return !Number.isFinite(v) || v < 1 || v > 5;
    });
    if (missing.length) {
      setLocalError('Rate every rubric criterion (1–5) before submitting.');
      return;
    }
    const rubric_ratings = Object.fromEntries(
      rubric.map((c) => [c.id, Number(ratings[c.id])]),
    );
    onSubmit?.({
      answer_text: answer,
      rubric_ratings,
    });
  };

  const mm = String(Math.floor(secondsRemaining / 60)).padStart(2, '0');
  const ss = String(secondsRemaining % 60).padStart(2, '0');

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 md:p-6" data-testid="system-design-round">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[#6F6F6F]">
          <LayoutTemplate size={16} />
          <span className="text-xs font-medium uppercase tracking-wider">
            System design · self-assessment
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm text-[#6F6F6F]">
          <Clock size={14} />
          <span>{mm}:{ss}</span>
        </div>
      </div>

      <h2
        className="text-2xl text-black"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {question || questionContext?.title || 'System design prompt'}
      </h2>
      <p className="text-sm leading-relaxed text-[#333]">
        {questionContext?.prompt || ''}
      </p>
      {(questionContext?.constraints || []).length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-sm text-[#555]">
          {questionContext.constraints.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      ) : null}

      <div className="rounded-xl border border-black/10 bg-black/[0.02] px-4 py-3 text-sm">
        <div className="font-medium text-black">Evaluation boundary</div>
        <p className="mt-1 text-[#444]">{boundary}</p>
        <p className="mt-2 text-xs uppercase tracking-wider text-[#6F6F6F]">
          Mode: {mode}
        </p>
      </div>

      {draftNotice ? (
        <p className="text-xs text-emerald-700">{draftNotice}</p>
      ) : null}

      {!closed ? (
        <>
          <label className="block text-sm font-medium text-black">
            Design notes (text)
            <textarea
              className="mt-2 min-h-[180px] w-full rounded-xl border border-black/10 p-3 text-sm"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Outline requirements, APIs, storage, scale, and trade-offs. Diagrams are optional notes only — not auto-validated."
              disabled={isScoring}
            />
          </label>

          <div className="space-y-3">
            <div className="text-sm font-medium text-black">Rubric self-ratings (1–5)</div>
            {rubric.map((criterion) => (
              <div
                key={criterion.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-black/8 px-3 py-2"
              >
                <div>
                  <div className="text-sm font-medium">{criterion.name}</div>
                  <div className="text-xs text-[#6F6F6F]">{criterion.description}</div>
                </div>
                <select
                  aria-label={`Rating for ${criterion.name}`}
                  className="rounded-md border border-black/15 px-2 py-1 text-sm"
                  value={ratings[criterion.id] ?? ''}
                  onChange={(e) =>
                    setRatings((prev) => ({ ...prev, [criterion.id]: e.target.value }))
                  }
                  disabled={isScoring}
                >
                  <option value="">—</option>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          {localError ? (
            <p className="text-sm text-red-700" role="alert">{localError}</p>
          ) : null}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={isScoring}
            className="inline-flex items-center gap-2 rounded-xl bg-black px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            <Send size={14} />
            {isScoring ? 'Recording…' : 'Submit self-assessment'}
          </button>
        </>
      ) : (
        <div className="space-y-3 rounded-xl border border-black/10 p-4">
          <div className="text-sm text-[#6F6F6F]">Self-assessment score</div>
          <div className="text-3xl font-medium">{currentScore == null ? 'Not scored' : Number(currentScore).toFixed(1)}</div>
          <p className="text-sm text-[#444]">{currentFeedback}</p>
          {currentArtifact?.evaluation_mode ? (
            <p className="text-xs uppercase tracking-wider text-[#6F6F6F]">
              {currentArtifact.evaluation_mode}
            </p>
          ) : null}
          <CalibrationPanel calibration={currentArtifact?.calibration} />
          {onNextRound && (
            <button
              type="button"
              onClick={onNextRound}
              disabled={nextBusy}
              className="inline-flex items-center gap-2 rounded-xl border border-black/15 px-4 py-2 text-sm disabled:opacity-50"
            >
              <RefreshCw size={14} />
              {sessionComplete ? 'View report' : (nextBusy ? 'Opening…' : 'Next')}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function listRubric(ctx) {
  const items = Array.isArray(ctx?.rubric) ? ctx.rubric : [];
  return items.map((c) => ({
    id: c.id,
    name: c.name || c.id,
    description: c.description || '',
  }));
}

export function CalibrationPanel({ calibration }) {
  if (!calibration) return null;
  if (!calibration.available) {
    return calibration.reason
      ? <p className="text-xs text-[#6F6F6F]" data-testid="sd-calibration-unavailable">{calibration.reason}</p>
      : null;
  }
  const rows = calibration.criteria || [];
  const flagged = rows.filter((row) => row.overconfident);
  return (
    <div className="space-y-2 rounded-lg border border-black/10 bg-black/[0.02] p-3" data-testid="sd-calibration">
      <div className="text-sm font-medium">Your ratings vs. what your notes mention</div>
      <ul className="space-y-2 text-sm">
        {rows.map((row) => (
          <li key={row.id} className={row.overconfident ? 'text-amber-800' : 'text-[#444]'}>
            <span className="font-medium">{row.name}</span>
            {`: you rated ${row.self_rating} · notes show ${row.evidence_level}`}
            {row.overconfident && row.not_mentioned?.length > 0 && (
              <span className="block text-xs">Not mentioned: {row.not_mentioned.join(', ')}</span>
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-[#6F6F6F]">
        {flagged.length > 0
          ? 'Highlighted criteria are rated well above what the notes show. Try covering them in your next design.'
          : 'Your notes back up your ratings.'}
        {' '}{calibration.note}
      </p>
    </div>
  );
}
