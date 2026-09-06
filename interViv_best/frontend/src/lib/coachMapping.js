/**
 * Map coach API payload → display model. Pure helpers for UI + tests.
 */

export function mapCoachPlan(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const steps = Array.isArray(payload.steps)
    ? payload.steps
        .map((s) => ({
          title: String(s?.title || '').trim(),
          why: String(s?.why || '').trim(),
          href: String(s?.href || '').trim(),
        }))
        .filter((s) => s.title && s.href.startsWith('/'))
    : [];
  return {
    needsClarification: Boolean(payload.needs_clarification),
    clarifyingQuestions: Array.isArray(payload.clarifying_questions)
      ? payload.clarifying_questions.map(String)
      : [],
    haveSkills: Array.isArray(payload.have_skills) ? payload.have_skills.map(String) : [],
    missingSkills: Array.isArray(payload.missing_skills) ? payload.missing_skills.map(String) : [],
    unrecognized: Array.isArray(payload.unrecognized) ? payload.unrecognized.map(String) : [],
    recognizedSkills: Array.isArray(payload.recognized_skills)
      ? payload.recognized_skills.map(String)
      : [],
    steps,
    practicePreview: {
      skills: Array.isArray(payload.practice_preview?.skills)
        ? payload.practice_preview.skills.map(String)
        : [],
      roundPlan: Array.isArray(payload.practice_preview?.round_plan)
        ? payload.practice_preview.round_plan.map(String)
        : [],
    },
    mode: payload.mode || 'fallback',
    disclaimer:
      payload.disclaimer ||
      'Coach maps your text onto interViv skills. It does not score interviews.',
  };
}
