/**
 * Map ATS API payload → display model for /ats result UI.
 */

export function mapAtsResultToView(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const components = payload.components || {};
  return {
    total: Number(payload.total) || 0,
    components: [
      {
        key: "parse_health",
        label: "Parse health",
        score: Number(components.parse_health) || 0,
        weight: payload.weights?.parse_health ?? 0.25,
      },
      {
        key: "section_complete",
        label: "Section complete",
        score: Number(components.section_complete) || 0,
        weight: payload.weights?.section_complete ?? 0.2,
      },
      {
        key: "keyword_coverage",
        label: "Keyword coverage",
        score: Number(components.keyword_coverage) || 0,
        weight: payload.weights?.keyword_coverage ?? 0.4,
      },
      {
        key: "content_heuristics",
        label: "Content heuristics",
        score: Number(components.content_heuristics) || 0,
        weight: payload.weights?.content_heuristics ?? 0.15,
      },
    ],
    flags: Array.isArray(payload.flags) ? payload.flags : [],
    presentSkills: Array.isArray(payload.present_skills) ? payload.present_skills : [],
    missingSkills: Array.isArray(payload.missing_skills) ? payload.missing_skills : [],
    // null = no Experience/Projects section found, so it can't be judged.
    unsubstantiatedSkills: Array.isArray(payload.unsubstantiated_skills) ? payload.unsubstantiated_skills : null,
    layout: payload.layout || null,
    suggestedPractice: Array.isArray(payload.suggested_practice_skills)
      ? payload.suggested_practice_skills
      : [],
    roleId: payload.role_id || null,
    resumeId: payload.resume_id || null,
  };
}
