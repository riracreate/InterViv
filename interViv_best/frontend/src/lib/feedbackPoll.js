/**
 * Focused feedback polling helper (Phase 3B).
 * Pure: no network. Used by Interview and unit tests.
 */

export function shouldKeepPollingNarration(status) {
  return status === 'queued' || status === 'processing';
}

/** True only while the tick still belongs to the live expected round. */
export function isFeedbackPollTickCurrent(expectedRound, tickRound) {
  return expectedRound != null && expectedRound === tickRound;
}

/** Clear a scheduled poll interval; returns null for the stored id. */
export function clearFeedbackPollInterval(intervalId, clearFn = clearInterval) {
  if (intervalId != null) clearFn(intervalId);
  return null;
}

export function applyFeedbackPollResult(state, payload, expectedRound) {
  if (!payload || payload.round !== expectedRound) {
    return { ...state, ignoredStale: true };
  }
  const narration = payload.narration || {};
  const next = {
    ...state,
    ignoredStale: false,
    rulesFeedback: payload.feedback || state.rulesFeedback,
    finalScore: payload.final_score ?? state.finalScore,
    narrationStatus: narration.status || state.narrationStatus,
    narrationScript: narration.script ?? state.narrationScript,
    narrationLabel: narration.label ?? state.narrationLabel,
    narrationDetails: narration.details || state.narrationDetails,
  };
  next.polling = shouldKeepPollingNarration(next.narrationStatus);
  // Replace displayed feedback only after a complete validated AI result.
  if (
    narration.status === 'done'
    && narration.source
    && narration.source !== 'rules_feedback'
    && narration.script
  ) {
    next.displayFeedback = narration.script;
    next.displaySource = narration.label || 'AI narration';
  } else if (!next.displayFeedback && payload.feedback) {
    const fb = payload.feedback;
    next.displayFeedback = fb.next_step || (fb.content && fb.content[0]) || state.displayFeedback;
    next.displaySource = 'Rules feedback';
  }
  return next;
}
