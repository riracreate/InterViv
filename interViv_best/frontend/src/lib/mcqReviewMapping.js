/**
 * Map completed-session MCQ review payloads for the dashboard.
 * Never invents keys — only surfaces fields the API already allowed.
 */

function optionLabel(options, id) {
  const match = (options || []).find((opt) => String(opt.id) === String(id));
  return match?.text ? String(match.text) : String(id);
}

/**
 * @param {object} round — dashboard round (may include mcq_questions, artifact_json, config)
 * @param {{ assessmentCompleted?: boolean }} opts
 */
export function mapMcqReview(round, opts = {}) {
  const assessmentCompleted = opts.assessmentCompleted !== false;
  const policy = String(
    round?.review_policy
    || round?.config_json?.review_policy
    || 'none',
  );
  const questions = Array.isArray(round?.mcq_questions)
    ? round.mcq_questions
    : (round?.question_context?.questions || []);
  if (!questions.length) return null;

  const artifactById = new Map();
  for (const row of round?.artifact_json?.questions || []) {
    if (row?.question_id != null) artifactById.set(String(row.question_id), row);
  }

  const allowKeys = assessmentCompleted && policy === 'after_session';
  const items = questions.map((q, index) => {
    const id = String(q.id ?? index);
    const art = artifactById.get(id) || {};
    const selected = Array.isArray(art.selected_option_ids) ? art.selected_option_ids : [];
    const correct = allowKeys && Array.isArray(q.correct_option_ids)
      ? q.correct_option_ids
      : [];
    const explanation = allowKeys && q.explanation ? String(q.explanation) : null;
    return {
      id,
      stem: q.stem || `Question ${index + 1}`,
      options: q.options || [],
      selectedIds: selected,
      selectedLabels: selected.map((sid) => optionLabel(q.options, sid)),
      correctIds: correct,
      correctLabels: correct.map((cid) => optionLabel(q.options, cid)),
      explanation,
      isCorrect: typeof art.is_correct === 'boolean' ? art.is_correct : null,
      rawMarks: art.raw_marks ?? null,
    };
  });

  return {
    reviewPolicy: policy,
    keysVisible: allowKeys && items.some((item) => item.correctIds.length > 0 || item.explanation),
    items,
  };
}

export function formatMcqAnswerSummary(review) {
  if (!review?.items?.length) return '';
  return review.items
    .map((item, i) => {
      const picked = item.selectedLabels.length
        ? item.selectedLabels.join(', ')
        : 'No selection';
      return `Q${i + 1}: ${picked}`;
    })
    .join(' · ');
}
