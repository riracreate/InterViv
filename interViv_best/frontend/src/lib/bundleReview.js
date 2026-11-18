export const REVIEW_CHECKLIST_ITEMS = [
  { key: 'question_clear', label: 'Question is clear and well-scoped' },
  { key: 'reference_correct', label: 'Reference answer is technically accurate' },
  { key: 'required_concepts_right', label: 'Required concepts and propositions are appropriate' },
  { key: 'no_ambiguity', label: 'No ambiguity or contradictory expectations' },
  { key: 'misconceptions_reasonable', label: 'Misconceptions represent plausible false claims' },
  { key: 'descriptors_observable', label: 'Concept descriptors are observable in a candidate answer' },
  { key: 'difficulty_appropriate', label: 'Scope matches the blind difficulty rating' },
];

export const DIFFICULTY_OPTIONS = ['easy', 'medium', 'hard'];
export const MIN_REVIEW_REASON_CHARS = 20;

const PLACEHOLDER_REASONS = new Set([
  '', 'tbd', 'todo', 'n/a', 'na', 'none', 'test', 'testing', 'asdf',
  'lorem ipsum', 'placeholder', 'ok', 'fine', 'good', 'lgtm',
  'approved', 'reject', 'rejected', 'x', '...',
]);

export function emptyChecklist(initial = false) {
  return Object.fromEntries(REVIEW_CHECKLIST_ITEMS.map(({ key }) => [key, Boolean(initial)]));
}

export function canSubmitForReview(status) {
  return status === 'draft' || status === 'auto_checked';
}

export function availableDecisions(detail) {
  if (detail && detail.needs_adjudication) {
    return ['adjudicate_approve', 'adjudicate_reject'];
  }
  return ['approve', 'reject'];
}

export function formatAutoCheckSummary(attribution) {
  const autoCheck = attribution && typeof attribution === 'object' ? attribution.auto_check : null;
  if (!autoCheck || typeof autoCheck !== 'object') {
    return {
      ran: false,
      verdict: 'Not checked',
      reason: 'Automated check has not run on this version.',
      providerModel: null,
      coverageText: null,
      missedConcepts: [],
      misconceptionHits: [],
    };
  }
  const cov = autoCheck.coverage && typeof autoCheck.coverage === 'object' ? autoCheck.coverage : {};
  const hasCov = typeof cov.k_supported === 'number' && typeof cov.n_required === 'number';
  const modelParts = [autoCheck.check_provider, autoCheck.check_model].filter(Boolean);
  return {
    ran: Boolean(autoCheck.auto_check_ran ?? true),
    verdict: autoCheck.to_status === 'auto_checked' ? 'Passed' : (autoCheck.to_status || 'Checked'),
    reason: autoCheck.reason || '',
    providerModel: modelParts.length ? modelParts.join(' / ') : null,
    coverageText: hasCov ? `${cov.k_supported}/${cov.n_required}` : null,
    missedConcepts: Array.isArray(autoCheck.missed_concepts) ? autoCheck.missed_concepts : [],
    misconceptionHits: Array.isArray(autoCheck.misconception_hits) ? autoCheck.misconception_hits : [],
  };
}

export function validateReviewForm({ decision, checklist, reasons, difficulty }) {
  const missingOrNonBool = REVIEW_CHECKLIST_ITEMS
    .map(({ key }) => key)
    .filter((key) => !checklist || typeof checklist[key] !== 'boolean');
  if (missingOrNonBool.length > 0) {
    return `Complete checklist fields: ${missingOrNonBool.join(', ')}.`;
  }
  if (decision === 'approve' || decision === 'adjudicate_approve') {
    const failed = REVIEW_CHECKLIST_ITEMS
      .map(({ key }) => key)
      .filter((key) => !checklist[key]);
    if (failed.length > 0) {
      return `Cannot approve with unchecked items: ${failed.join(', ')}.`;
    }
  }
  const normalizedReason = String(reasons || '')
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/^[ .!?-]+|[ .!?-]+$/g, '')
    .toLowerCase();
  if (normalizedReason.length < MIN_REVIEW_REASON_CHARS || PLACEHOLDER_REASONS.has(normalizedReason)) {
    return `Enter a substantive reason (>= ${MIN_REVIEW_REASON_CHARS} characters, not a placeholder).`;
  }
  if (!DIFFICULTY_OPTIONS.includes(String(difficulty || '').toLowerCase())) {
    return 'Select a blind difficulty calibration rating (easy, medium, or hard).';
  }
  return null;
}

export function buildDecisionPayload({ contentHash, decision, checklist, reasons, difficulty }) {
  return {
    content_hash: String(contentHash || ''),
    decision,
    checklist: REVIEW_CHECKLIST_ITEMS.reduce((acc, { key }) => {
      acc[key] = Boolean(checklist && checklist[key]);
      return acc;
    }, {}),
    reasons: String(reasons || '').trim(),
    calibration: { difficulty: String(difficulty || '').toLowerCase() },
  };
}

export function adminErrorNotice(err) {
  if (!err) return '';
  if (err.status === 404) {
    return 'Admin review endpoints are disabled (enable ENABLE_ADMIN_ENDPOINTS to use this page).';
  }
  if (err.status === 403) {
    return 'Admin review access is restricted to addresses configured in ADMIN_USER_EMAILS.';
  }
  return err.message || 'Unable to load bundle review queue.';
}
