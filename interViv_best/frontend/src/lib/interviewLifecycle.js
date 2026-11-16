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
  const config = round.config_json || {};
  return {
    round: Number(round.round) || fallback.round || 1,
    question: round.question || '',
    roundType: round.round_type || 'technical_short_answer',
    blockCategory: round.block_category ?? null,
    difficulty: round.difficulty || fallback.difficulty || 'medium',
    skill: round.skill || fallback.skill || '',
    questionContext: round.question_context || {},
    configJson: config,
    expiresAt: round.expires_at ?? null,
    startedAt: round.started_at ?? null,
    isFollowUp: Boolean(round.is_follow_up || config.is_follow_up),
    followUpParentRound: round.follow_up_parent_round ?? config.follow_up_parent_round ?? null,
  };
}

/** Display text for rules feedback in any of the server's shapes. */
export function feedbackText(feedback) {
  if (!feedback) return '';
  if (typeof feedback === 'string') return feedback;
  return feedback.next_step || (Array.isArray(feedback.content) ? feedback.content[0] : '') || '';
}

/** Extract S1b-1 concept outcome object for inline follow-ups when present. */
export function followUpOutcomeFromPayload(payload) {
  const outcome = payload?.follow_up_outcome || payload?.config_json?.follow_up_outcome || null;
  if (!outcome || typeof outcome !== 'object' || !outcome.concept_label) return null;
  return outcome;
}

/** Whether the legacy "Request optional follow-up" CTA may be shown for this round. */
export function canRequestManualFollowUp({
  roundType,
  phase,
  followUpNote,
  followUpScheduled,
  isFollowUp,
}) {
  return (
    roundType === 'technical_short_answer'
    && phase === PHASES.REVIEWING
    && !followUpNote
    && !followUpScheduled
    && !isFollowUp
  );
}

/** Result fields for a submitted round from GET /session round_history. */
export function resultFromHistory(entry) {
  if (!entry) return null;
  const breakdown = entry.scoring_breakdown || {};
  const config = entry.config_json || {};
  const followUpOutcome = followUpOutcomeFromPayload(entry);
  const inlineFeedback = followUpOutcome && Array.isArray(entry.feedback?.content) && entry.feedback.content[0]
    ? entry.feedback.content[0]
    : feedbackText(entry.feedback);
  return {
    round: Number(entry.round),
    question: entry.question || '',
    roundType: entry.round_type || 'technical_short_answer',
    blockCategory: entry.block_category ?? null,
    difficulty: entry.difficulty || 'medium',
    skill: entry.skill || '',
    questionContext: entry.question_context || {},
    configJson: config,
    answerText: entry.answer_text || '',
    score: followUpOutcome ? null : (typeof entry.final_score === 'number' ? entry.final_score : null),
    feedback: inlineFeedback,
    rubric: breakdown.rubric || null,
    concepts: breakdown.concepts || null,
    artifact: entry.artifact_json || null,
    evaluationMode: entry.evaluation_mode || null,
    eligibility: entry.assessment_eligibility || null,
    isFollowUp: Boolean(entry.is_follow_up || config.is_follow_up),
    followUpParentRound: entry.follow_up_parent_round ?? config.follow_up_parent_round ?? null,
    followUpOutcome,
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
