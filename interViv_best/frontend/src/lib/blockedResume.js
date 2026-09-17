/**
 * Pure helpers for restoring blocked-session UI state (Phase 3B resume).
 */

export function blockedResumeFromSession(data) {
  if (!data || data.status !== 'content_blocked') {
    return { progressionBlocked: false, progressionBlockedReason: '' };
  }
  const cr = data.active_round || data.current_round || null;
  let feedback = '';
  if (cr?.feedback) {
    feedback = typeof cr.feedback === 'string'
      ? cr.feedback
      : (cr.feedback.next_step || (cr.feedback.content && cr.feedback.content[0]) || '');
  }
  return {
    progressionBlocked: true,
    progressionBlockedReason: data.progression_blocked_reason || '',
    currentScore: cr?.final_score ?? null,
    currentFeedback: feedback,
    round: cr?.round ?? null,
  };
}
