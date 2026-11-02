import { blockedResumeFromSession } from './blockedResume.js';

export function displayScore(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `${Math.round(value)}%` : 'Not measured';
}

/**
 * Observed-average note shown beside the conservative readiness headline, in
 * the same words as the Gap Analysis page. Displays server values only.
 */
export function observedReadinessNote(overview) {
  const observed = overview?.readiness_observed;
  if (typeof observed !== 'number' || !Number.isFinite(observed)) return '';
  const provisional = overview?.readiness_provisional_skill_count || 0;
  if (provisional === 0 && Math.round(observed) === Math.round(overview?.readiness ?? observed)) return '';
  const minAttempts = overview?.target?.established_min_attempts;
  const tail = provisional > 0
    ? ` · ${provisional} skill${provisional === 1 ? '' : 's'} still provisional${minAttempts ? ` (fewer than ${minAttempts} measured attempts)` : ''}`
    : '';
  return `Observed average ${Math.round(observed)}%${tail}`;
}

/** Reason wording for a round that was never evaluated (Progress and the session report). */
export function unscoredReasonLabel(item) {
  if (item.reason !== 'execution_unavailable') return item.reason;
  return item.round_type === 'ml_primitives' ? 'ML scoring unavailable' : 'coding unavailable';
}

export function sessionLabel(types = []) {
  const names = { technical_short_answer: 'Interview', mcq: 'OA', sql: 'SQL', coding: 'Coding', ml_primitives: 'ML primitives' };
  return [...new Set(types)].map(type => names[type] || 'Assessment').join(' + ') || 'Practice';
}

export function interviewStateFromSession(session) {
  const round = session.active_round || session.current_round;
  if (!round || !session.session_id) throw new Error('This session has no available question.');
  const blocked = blockedResumeFromSession(session);
  return {
    sessionId: session.session_id,
    candidateId: session.candidate_id,
    skill: session.current_skill,
    allSkills: session.skills || [session.current_skill],
    question: round.question,
    round_type: round.round_type,
    question_context: round.question_context || {},
    config_json: round.config_json || {},
    expires_at: round.expires_at ?? null,
    difficulty: round.difficulty || session.current_difficulty,
    round: round.round || session.last_round,
    totalRounds: session.total_rounds,
    elo: round.elo_before ?? 1200,
    status: session.status,
    progressionBlocked: blocked.progressionBlocked,
    progressionBlockedReason: blocked.progressionBlockedReason,
    progression_blocked_reason: blocked.progressionBlockedReason,
    // Deep-link first paint: keep committed score/feedback when blocked.
    currentScore: blocked.progressionBlocked ? blocked.currentScore : undefined,
    currentFeedback: blocked.progressionBlocked ? blocked.currentFeedback : undefined,
  };
}
