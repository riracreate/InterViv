export function displayScore(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `${Math.round(value)}%` : 'Not measured';
}

export function sessionLabel(types = []) {
  const names = { technical_short_answer: 'Interview', mcq: 'OA', sql: 'SQL', coding: 'Coding', ml_primitives: 'ML primitives' };
  return [...new Set(types)].map(type => names[type] || 'Assessment').join(' + ') || 'Practice';
}

export function interviewStateFromSession(session) {
  const round = session.active_round || session.current_round;
  if (!round || !session.session_id) throw new Error('This session has no available question.');
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
  };
}
