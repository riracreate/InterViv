import { blockedResumeFromSession } from './blockedResume.js';
import { PHASES, restoreFromSession, resultFromHistory } from './interviewLifecycle.js';

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
  if (!session?.session_id) throw new Error('This session has no available question.');
  const restored = restoreFromSession(session);
  const blocked = blockedResumeFromSession(session);
  const legacyResult = restored.phase !== PHASES.ANSWERING && !restored.result && session.active_round
    ? resultFromHistory(session.active_round)
    : null;
  const current = restored.current || legacyResult;
  if (!current) throw new Error('This session has no available question.');
  const result = restored.result || legacyResult;
  const servedRound = session.active_round || null;
  const lastElo = [...(session.round_history || [])].reverse().find(r => r.elo_after != null)?.elo_after;
  const progressionBlocked = restored.phase === PHASES.BLOCKED || blocked.progressionBlocked;
  return {
    sessionId: session.session_id,
    candidateId: session.candidate_id,
    skill: current.skill || session.current_skill,
    allSkills: session.skills || [session.current_skill],
    question: current.question,
    round_type: current.roundType,
    block_category: current.blockCategory,
    question_context: current.questionContext || {},
    config_json: current.configJson || {},
    expires_at: current.expiresAt ?? null,
    started_at: current.startedAt ?? null,
    difficulty: current.difficulty || session.current_difficulty,
    round: current.round || session.last_round,
    totalRounds: session.total_rounds,
    elo: servedRound?.status === 'in_progress'
      ? (servedRound.elo_before ?? 1200)
      : (lastElo ?? servedRound?.elo_before ?? 1200),
    status: session.status,
    phase: restored.phase,
    pendingRound: restored.pendingRound,
    roundHistory: restored.history,
    progressionBlocked,
    progressionBlockedReason: blocked.progressionBlockedReason || session.progression_blocked_reason || '',
    progression_blocked_reason: blocked.progressionBlockedReason || session.progression_blocked_reason || '',
    // Review after a refresh: the submitted answer and its result.
    answerText: result ? result.answerText : '',
    currentScore: result ? result.score : undefined,
    currentFeedback: result ? result.feedback : undefined,
    currentRubric: result ? result.rubric : undefined,
    currentConcepts: result ? result.concepts : undefined,
    currentArtifact: result ? result.artifact : undefined,
    evaluationMode: result ? result.evaluationMode : undefined,
    // Slice 1 server-derived fields (null on legacy plans / older servers).
    mandatoryIndex: current.mandatoryIndex ?? null,
    mandatoryTotal: session.mandatory_total ?? null,
    mandatoryCompleted: session.mandatory_completed ?? null,
    isFollowUpRound: Boolean(current.isFollowUp),
    followUpLabel: current.followUpLabel || null,
    progressLabel: current.progressLabel || null,
    systemFollowUpScheduled: Boolean(result && result.systemFollowUpScheduled),
  };
}
