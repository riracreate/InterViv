/**
 * roundContractHelpers.js
 * Helpers for MCQ round payload formatting, session rehydration, and timing calculations.
 */

/**
 * Formats MCQ candidate answers into the canonical submission array structure:
 * [
 *   { question_id: '...', selected_option_ids: ['b'] },
 *   { question_id: '...', selected_option_ids: [] }
 * ]
 *
 * Preserves question order and ensures explicit empty selections [] for skipped questions.
 *
 * @param {Array<{id: string}>} questions - The assigned questions from question_context.questions.
 * @param {Record<string, string>} answersMap - Object mapping questionId -> selectedOptionId.
 * @returns {Array<{question_id: string, selected_option_ids: string[]}>} Canonical answers payload.
 */
export function formatMCQSubmission(questions = [], answersMap = {}) {
  if (!Array.isArray(questions)) return [];
  return questions.map((q) => {
    const qId = q?.id || '';
    const selected = answersMap[qId];
    return {
      question_id: qId,
      selected_option_ids: selected ? [selected] : [],
    };
  });
}

/**
 * Normalizes session response from backend.
 * Ensures active_round is mirrored into current_round so clients reading either property succeed.
 *
 * @param {object} data - Backend response from /session/{session_id}.
 * @returns {object} Normalized session data.
 */
export function normalizeSessionData(data) {
  if (!data || typeof data !== 'object') return data;
  const normalized = { ...data };
  if (normalized.active_round && !normalized.current_round) {
    normalized.current_round = normalized.active_round;
  } else if (normalized.current_round && !normalized.active_round) {
    normalized.active_round = normalized.current_round;
  }
  return normalized;
}

/**
 * Computes remaining seconds from expires_at timestamp or fallback duration.
 *
 * @param {string|number|Date|null} expiresAt - ISO string or timestamp of round deadline.
 * @param {number} fallbackDurationMinutes - Fallback duration in minutes (e.g. 20).
 * @param {number} nowMs - Current epoch in milliseconds (defaults to Date.now()).
 * @returns {number} Seconds remaining, clamped to >= 0.
 */
export function computeSecondsRemaining(expiresAt, fallbackDurationMinutes = 20, nowMs = Date.now()) {
  if (expiresAt) {
    // SQLite-backed API deadlines are UTC even when the ISO string omits Z.
    const timestamp = typeof expiresAt === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(expiresAt)
      && !/(Z|[+-]\d\d:\d\d)$/i.test(expiresAt) ? `${expiresAt}Z` : expiresAt;
    const expMs = new Date(timestamp).getTime();
    if (!isNaN(expMs)) {
      return Math.max(0, Math.floor((expMs - nowMs) / 1000));
    }
  }
  return Math.max(0, fallbackDurationMinutes * 60);
}
