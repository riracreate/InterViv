/**
 * Upload wizard state (overhaul Phase 4). Pure.
 *
 * ``?step=upload|skills|domains`` is the source of truth for the step, so
 * browser Back/Forward move through the wizard. The wizard's metadata is
 * saved per account in session storage (lib/accountStorage.js) and restored
 * when the candidate returns, e.g. from Gap Analysis. Resume bytes are never
 * stored and a browser File cannot be restored; the server keeps the parsed
 * resume under ``candidateId``.
 */

export const WIZARD_STEPS = Object.freeze(['upload', 'skills', 'domains']);
export const WIZARD_STORAGE_NAME = 'upload-wizard';
export const WIZARD_STORAGE_VERSION = 1;

export const EMPTY_WIZARD = Object.freeze({
  candidateId: '',
  fileName: '',
  extractedSkills: [],
  domainProfile: {},
  selectedSkills: [],
  targetSelection: { companyId: '', roleId: '' },
});

function stringList(value, limit = 200) {
  return Array.isArray(value)
    ? value.map((item) => String(item ?? '').trim()).filter(Boolean).slice(0, limit)
    : [];
}

function stringMap(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value)
      .filter(([k, v]) => typeof k === 'string' && typeof v === 'string')
      .slice(0, 200),
  );
}

/** Keep only the fields the wizard owns, in safe shapes. */
export function serializeWizard(state) {
  const target = state?.targetSelection || {};
  return {
    candidateId: String(state?.candidateId || ''),
    fileName: String(state?.fileName || '').slice(0, 255),
    extractedSkills: stringList(state?.extractedSkills),
    domainProfile: stringMap(state?.domainProfile),
    selectedSkills: stringList(state?.selectedSkills),
    targetSelection: {
      companyId: String(target.companyId || ''),
      roleId: String(target.roleId || ''),
    },
  };
}

/** Validate stored data; anything malformed restores as empty. */
export function restoreWizard(raw) {
  if (!raw || typeof raw !== 'object') return { ...EMPTY_WIZARD };
  return serializeWizard(raw);
}

export function hasWizardProgress(state) {
  return Boolean(state?.candidateId) || (state?.extractedSkills?.length || 0) > 0;
}

export function stepFromSearch(search) {
  const value = new URLSearchParams(search || '').get('step');
  return WIZARD_STEPS.includes(value) ? value : null;
}

/**
 * Nearest reachable step: skills needs a parsed resume or chosen domain
 * skills; domains also needs at least one selected skill.
 */
export function resolveWizardStep(requested, state) {
  const wanted = WIZARD_STEPS.includes(requested) ? requested : 'upload';
  const canSkills = hasWizardProgress(state);
  const canDomains = canSkills && (state?.selectedSkills?.length || 0) > 0;
  if (wanted === 'domains') return canDomains ? 'domains' : canSkills ? 'skills' : 'upload';
  if (wanted === 'skills') return canSkills ? 'skills' : 'upload';
  return 'upload';
}

export function previousStep(step) {
  const index = WIZARD_STEPS.indexOf(step);
  return index > 0 ? WIZARD_STEPS[index - 1] : null;
}
