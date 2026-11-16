/**
 * Pure helpers for job explorer cards (Adzuna).
 */
import { summarizeLaunchScope } from './practiceBuilder.js';

/** Skills as typed in the confirm dialog: comma-separated, trimmed, no blanks. */
export function jobSkillList(text) {
  return String(text || '').split(',').map((s) => s.trim()).filter(Boolean);
}

/**
 * Identity of a typed skill list. The dialog records the key its preview was
 * built for; a different key means the preview no longer describes what
 * would be started.
 */
export function jobSkillKey(text) {
  return jobSkillList(text).map((s) => s.toLowerCase()).join('|');
}

/** Planned scope of the draft the dialog currently holds. */
export function jobLaunchScope(draft) {
  return summarizeLaunchScope(draft?.planned_scope);
}

/**
 * Whether the confirm dialog may start practice, and the reason when it may
 * not. Starting is allowed only when the preview on screen was built for
 * the skills in the field and nothing in it is short of content, so the
 * request that is sent is the plan the candidate just saw.
 */
export function jobStartState({ draft, skillsText, previewKey, previewBusy = false, previewError = '' }) {
  if (!jobSkillList(skillsText).length) {
    return { canStart: false, reason: 'Enter at least one skill.' };
  }
  if (previewError) {
    return { canStart: false, reason: `Could not update the preview: ${previewError}` };
  }
  if (previewBusy || jobSkillKey(skillsText) !== previewKey) {
    return { canStart: false, reason: 'Updating the preview for these skills…' };
  }
  const scope = jobLaunchScope(draft);
  if (scope && scope.unavailable.length) {
    return { canStart: false, reason: 'Change the skills marked above to start.' };
  }
  return { canStart: true, reason: '' };
}

/**
 * Body for POST /jobs/{id}/practice: the skills and blocks of the draft that
 * was previewed, never text typed after it. The server refuses blocks that
 * do not belong to those skills.
 */
export function jobPracticeBody(draft, { company, role, fullJd } = {}) {
  return {
    confirm: true,
    skills: [...(draft?.proposed_skills || [])],
    blocks: draft?.proposed_blocks,
    company,
    role,
    full_jd: fullJd || undefined,
  };
}

export function mapJobCard(job) {
  if (!job || typeof job !== 'object') return null;
  return {
    id: job.id,
    title: job.title || '',
    company: job.company || '',
    location: job.location || '',
    matchPct: job.match_pct == null ? null : Number(job.match_pct),
    skills: Array.isArray(job.skills) ? job.skills : [],
    redirectUrl: job.redirect_url || '',
    salaryMin: job.salary_min ?? null,
    salaryMax: job.salary_max ?? null,
    salaryIsPredicted: job.salary_is_predicted === true,
    salaryCurrency: job.salary_currency || null,
    snippet: job.snippet || '',
    attribution: job.attribution || null,
    provenance: job.provenance || '',
  };
}

export function jobApplyHref(card) {
  const href = card?.redirectUrl || '';
  if (!href) return '';
  try {
    const u = new URL(href);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return '';
    const host = u.hostname.toLowerCase();
    const adzuna = host === 'adzuna.com' || host.includes('.adzuna.') || host.startsWith('adzuna.');
    const greenhouseHost = host === 'greenhouse.io' || host.endsWith('.greenhouse.io');
    if (adzuna || greenhouseHost) return href;
    // Board feeds link to the company's own career site.
    if (card?.provenance === 'greenhouse' && u.protocol === 'https:' && host && host !== 'localhost') {
      return href;
    }
    return '';
  } catch {
    return '';
  }
}

export function formatSalary(card) {
  if (card?.salaryMin == null && card?.salaryMax == null) return null;
  const currency = card.salaryCurrency ? `${card.salaryCurrency} ` : '';
  let range;
  if (card.salaryMin != null && card.salaryMax != null) {
    range = `${currency}${card.salaryMin}–${card.salaryMax}`;
  } else if (card.salaryMin != null) {
    range = `${currency}${card.salaryMin}+`;
  } else {
    range = `up to ${currency}${card.salaryMax}`;
  }
  if (card.salaryIsPredicted) {
    return `${range} (Adzuna Jobsworth estimate)`;
  }
  return range;
}
