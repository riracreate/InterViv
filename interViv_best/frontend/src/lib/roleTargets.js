/**
 * Role-only targets and role interviews (ROLE_ONLY_TARGETS). Pure helpers.
 *
 * A role target is one of the starter roles plus a level. With the flag on it
 * replaces the company picker on Practice, Home and Upload, and "Start role
 * interview" runs a staged Quick or Full interview from the role plan.
 */
export const ROLE_ONLY_TARGETS = import.meta.env?.VITE_ROLE_ONLY_TARGETS === '1';

export const ROLE_LEVELS = Object.freeze([
  { id: 'intern', label: 'Intern' },
  { id: 'junior', label: 'Junior' },
  { id: 'mid', label: 'Mid' },
]);

export const ROLE_STAGE_LABELS = Object.freeze({
  warm_up: 'Opener',
  core: 'Core',
  practice: 'Practice',
  behavioural: 'Behavioural',
  practical: 'Practical',
});

export function levelLabel(level) {
  return ROLE_LEVELS.find(item => item.id === level)?.label || '';
}

export function roleTargetLabel(target) {
  if (!target?.title) return '';
  const level = levelLabel(target.level);
  return level ? `${target.title} · ${level}` : target.title;
}

export function roleTargetFromContext(data) {
  const target = data?.target?.role_target;
  return target?.role_id ? target : null;
}

export function roleTargetUpdate(roleId, level) {
  return { role_target: { role_id: String(roleId || ''), level: level || 'junior' } };
}

export function coreCompetencies(slots) {
  return (slots || []).filter(slot => slot.kind === 'core').map(slot => slot.competency_id);
}

export function rolePlanRequest({ roleId, level, length, candidateId, useResume, core }) {
  const body = { role_id: roleId, level: level || 'junior', length: length === 'full' ? 'full' : 'quick' };
  if (useResume && candidateId) body.candidate_id = candidateId;
  if (core?.length) body.core_competencies = [...core];
  return body;
}

export function roleInterviewPayload({ roleId, level, length, candidateId, useResume, core }) {
  if (!roleId) throw new Error('Choose a role first.');
  const roleInterview = { role_id: roleId, level: level || 'junior', use_resume: Boolean(useResume && candidateId) };
  if (core?.length) roleInterview.core_competencies = [...core];
  const payload = {
    flow_version: 'staged_v1',
    preset: length === 'full' ? 'full' : 'quick',
    skills: [],
    practice_mode: 'coached_practice',
    allow_optional_follow_ups: true,
    role_interview: roleInterview,
  };
  if (candidateId) payload.candidate_id = candidateId;
  return payload;
}

/** Why a planned slot does or does not count toward the score. */
export function slotNote(slot) {
  if (!slot) return '';
  if (slot.kind === 'core' && slot.content === 'none') return 'practice only · no question bank for this skill yet';
  if (slot.practice_only) return 'practice only · not scored';
  if (slot.scored === false && slot.kind === 'core') return 'feedback only · question awaiting review';
  if (slot.scored === false) return 'not scored';
  return '';
}

export function slotLabel(slot) {
  const stage = ROLE_STAGE_LABELS[slot?.stage] || 'Question';
  const note = slotNote(slot);
  const text = slot?.kind === 'opener' ? slot.reason : slot?.reason || slot?.name || '';
  return { stage, text, note };
}

/** Label for a staged turn of a role interview; empty for scored stages. */
export function stagedTurnNote(stage) {
  if (stage === 'practice') return 'Practice only · not scored';
  if (stage === 'warm_up' || stage === 'behavioural') return 'Not scored';
  return '';
}
