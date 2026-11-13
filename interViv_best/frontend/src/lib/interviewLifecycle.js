/**
 * Interview round lifecycle (overhaul Phase 2). Pure: no React, no network.
 *
 *   answering → submitting → reviewing → activating → answering
 *                         ↘ completed (last round)   ↘ blocked (content unavailable)
 *
 * After a submission the server prepares the next round (status "ready",
 * no clock, prompt hidden). Only "Next Question" opens it through
 * POST /session/{id}/rounds/{n}/activate, so the submitted question, its
 * component and its feedback stay on screen until the candidate moves on.
 */

import { computeSecondsRemaining } from './roundContractHelpers.js';

export const PHASES = Object.freeze({
  ANSWERING: 'answering',
  SUBMITTING: 'submitting',
  REVIEWING: 'reviewing',
  ACTIVATING: 'activating',
  COMPLETED: 'completed',
  BLOCKED: 'blocked',
});

/** Advisory time budget for technical rounds the server does not time. */
export const TECHNICAL_ADVISORY_SECONDS = 120;

/** Answer inputs accept edits only while answering. */
export function inputsLocked(phase) {
  return phase !== PHASES.ANSWERING;
}

/** A submitted result (scored or not) is on screen. */
export function isShowingResult(phase) {
  return phase === PHASES.REVIEWING
    || phase === PHASES.ACTIVATING
    || phase === PHASES.COMPLETED
    || phase === PHASES.BLOCKED;
}

/** Phase after a successful submission response. */
export function phaseAfterSubmit(resp) {
  if (resp?.session_complete) return PHASES.COMPLETED;
  if (resp?.progression_blocked) return PHASES.BLOCKED;
  return PHASES.REVIEWING;
}

/** The prepared next round announced by a submission response, if any. */
export function pendingRoundFromResponse(resp) {
  if (!resp || resp.session_complete || resp.progression_blocked) return null;
  const number = Number(resp.next_round);
  if (!Number.isFinite(number) || number < 1) return null;
  return {
    round: number,
    roundType: resp.next_round_type || 'technical_short_answer',
    blockCategory: resp.next_block_category ?? null,
    skill: resp.next_skill || null,
    difficulty: resp.next_difficulty || null,
    status: resp.next_round_status || 'ready',
  };
}

/** Same shape from GET /session/{id}.pending_round. */
export function pendingRoundFromSession(pending) {
  if (!pending || pending.round == null) return null;
  return {
    round: Number(pending.round),
    roundType: pending.round_type || 'technical_short_answer',
    blockCategory: pending.block_category ?? null,
    skill: pending.skill || null,
    difficulty: pending.difficulty || null,
    status: pending.status || 'ready',
  };
}

/** UI fields for an opened round (activate / continue / GET active_round). */
export function roundFieldsFromPayload(round, fallback = {}) {
  if (!round) return null;
  return {
    round: Number(round.round) || fallback.round || 1,
    question: round.question || '',
    roundType: round.round_type || 'technical_short_answer',
    blockCategory: round.block_category ?? null,
    difficulty: round.difficulty || fallback.difficulty || 'medium',
    skill: round.skill || fallback.skill || '',
    questionContext: round.question_context || {},
    configJson: round.config_json || {},
    expiresAt: round.expires_at ?? null,
    startedAt: round.started_at ?? null,
    // Slice 1 server-derived fields (absent on legacy plans / older servers).
    mandatoryIndex: positiveIntOrNull(round.mandatory_index),
    isFollowUp: Boolean(round.is_follow_up),
    followUpLabel: round.follow_up_label || null,
    progressLabel: round.progress_label || null,
  };
}

function positiveIntOrNull(value) {
  const n = Number(value);
  return value != null && Number.isInteger(n) && n > 0 ? n : null;
}

/** Display text for rules feedback in any of the server's shapes. */
export function feedbackText(feedback) {
  if (!feedback) return '';
  if (typeof feedback === 'string') return feedback;
  return feedback.next_step || (Array.isArray(feedback.content) ? feedback.content[0] : '') || '';
}

/** Result fields for a submitted round from GET /session round_history. */
export function resultFromHistory(entry) {
  if (!entry) return null;
  const breakdown = entry.scoring_breakdown || {};
  return {
    round: Number(entry.round),
    question: entry.question || '',
    roundType: entry.round_type || 'technical_short_answer',
    blockCategory: entry.block_category ?? null,
    difficulty: entry.difficulty || 'medium',
    skill: entry.skill || '',
    questionContext: entry.question_context || {},
    configJson: entry.config_json || {},
    answerText: entry.answer_text || '',
    score: typeof entry.final_score === 'number' ? entry.final_score : null,
    feedback: feedbackText(entry.feedback),
    rubric: breakdown.rubric || null,
    concepts: breakdown.concepts || null,
    artifact: entry.artifact_json || null,
    evaluationMode: entry.evaluation_mode || null,
    eligibility: entry.assessment_eligibility || null,
    isFollowUp: Boolean(entry.is_follow_up),
    mandatoryIndex: positiveIntOrNull(entry.mandatory_index),
    followUpLabel: entry.follow_up_label || null,
    progressLabel: entry.progress_label || null,
    systemFollowUpScheduled: entry.system_follow_up_scheduled === true,
  };
}

/**
 * Restore the interview after a refresh from GET /session/{id}.
 * Returns { phase, current, result, pendingRound, history }.
 */
export function restoreFromSession(session) {
  const history = (session?.round_history || []).map(resultFromHistory).filter(Boolean);
  const reviewNumber = session?.review_round;
  const reviewed = reviewNumber != null
    ? history.find(item => item.round === Number(reviewNumber)) || null
    : null;
  const pendingRound = pendingRoundFromSession(session?.pending_round);
  const active = session?.active_round && session.active_round.status === 'in_progress'
    ? roundFieldsFromPayload(session.active_round)
    : null;

  if (active) {
    return { phase: PHASES.ANSWERING, current: active, result: null, pendingRound: null, history };
  }
  if (session?.status === 'content_blocked') {
    return { phase: PHASES.BLOCKED, current: reviewed, result: reviewed, pendingRound: null, history };
  }
  if (session?.status === 'completed') {
    return { phase: PHASES.COMPLETED, current: reviewed, result: reviewed, pendingRound: null, history };
  }
  if (reviewed) {
    return { phase: PHASES.REVIEWING, current: reviewed, result: reviewed, pendingRound, history };
  }
  // Legacy fallback: the last round served as active_round.
  const legacy = roundFieldsFromPayload(session?.active_round);
  return { phase: PHASES.ANSWERING, current: legacy, result: null, pendingRound, history };
}

function parseServerTime(value) {
  if (!value) return NaN;
  const text = typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(value)
    && !/(Z|[+-]\d\d:\d\d)$/i.test(value) ? `${value}Z` : value;
  return new Date(text).getTime();
}

/**
 * Seconds left in a technical round. Server deadline wins; otherwise an
 * advisory budget counted from the server's activation time, so a refresh
 * never resets it. Null when neither timestamp is known.
 */
export function technicalSecondsRemaining({ expiresAt, startedAt, nowMs = Date.now() }) {
  if (expiresAt) return computeSecondsRemaining(expiresAt, 0, nowMs);
  const started = parseServerTime(startedAt);
  if (Number.isNaN(started)) return null;
  const elapsed = Math.floor((nowMs - started) / 1000);
  return Math.max(0, TECHNICAL_ADVISORY_SECONDS - Math.max(0, elapsed));
}

/** Narration is worth polling only while the server says a job is pending. */
export const MAX_NARRATION_POLLS = 24;
export function shouldPollNarration(status) {
  return status === 'queued' || status === 'processing';
}

/** Header progress: answered rounds out of total. */
export function progressPercent({ round, totalRounds, phase }) {
  if (!totalRounds) return 0;
  const answered = Math.max(0, Number(round) - 1) + (isShowingResult(phase) ? 1 : 0);
  return Math.min(100, (answered / totalRounds) * 100);
}

/**
 * Header progress for indexed plans (Slice 1). The label shows the round's
 * mandatory position (a system follow-up shows its parent's); the bar uses
 * the server's count of completed mandatory rounds, so follow-ups never
 * advance it and it never moves backwards. Without server fields (legacy
 * plans or an older server) this is exactly the historical round/total
 * display.
 *
 * A candidate-requested follow-up carries the server's `progressLabel`
 * ("Optional follow-up") instead of a position. It is only ever delivered
 * after every mandatory round, so mandatory progress stays complete: the
 * server's completed/total count when present, otherwise 100%.
 */
export function mandatoryProgress({
  mandatoryIndex, mandatoryTotal, mandatoryCompleted, round, totalRounds, phase, progressLabel,
}) {
  const index = positiveIntOrNull(mandatoryIndex);
  const total = positiveIntOrNull(mandatoryTotal);
  if (progressLabel) {
    const counted = total && mandatoryCompleted != null && Number.isFinite(Number(mandatoryCompleted));
    return {
      current: null,
      total: total || Number(totalRounds) || 0,
      label: progressLabel,
      percent: counted ? Math.min(100, Math.max(0, (Number(mandatoryCompleted) / total) * 100)) : 100,
      mandatory: Boolean(total),
      optional: true,
    };
  }
  if (index && total) {
    const done = Number.isFinite(Number(mandatoryCompleted)) && mandatoryCompleted != null
      ? Number(mandatoryCompleted)
      : index - 1 + (isShowingResult(phase) ? 1 : 0);
    return {
      current: index,
      total,
      label: `${index}/${total}`,
      percent: Math.min(100, Math.max(0, (done / total) * 100)),
      mandatory: true,
      optional: false,
    };
  }
  return {
    current: Number(round) || 1,
    total: Number(totalRounds) || 0,
    label: `${round}/${totalRounds}`,
    percent: progressPercent({ round, totalRounds, phase }),
    mandatory: false,
    optional: false,
  };
}

/**
 * The optional-follow-up request button: technical rounds under review,
 * not already answered by a note, and hidden once the server reports a
 * system follow-up for this parent (also after a refresh).
 */
export function canRequestFollowUp({ roundType, phase, followUpNote, systemFollowUpScheduled }) {
  return roundType === 'technical_short_answer'
    && phase === PHASES.REVIEWING
    && !followUpNote
    && systemFollowUpScheduled !== true;
}

/** Banner for a system follow-up, from the server label only (never inferred). */
export function systemFollowUpBanner(followUpLabel) {
  if (!followUpLabel) return null;
  return {
    title: followUpLabel,
    body: 'A short clarification of your previous answer. It is not scored and does not count toward your assessment or progress.',
  };
}
