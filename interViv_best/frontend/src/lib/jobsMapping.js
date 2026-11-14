/**
 * Pure helpers for job explorer cards (Adzuna).
 */
import { summarizeLaunchScope } from './practiceBuilder.js';

function skillList(text) {
  return String(text || '').split(',').map((s) => s.trim()).filter(Boolean);
}

/**
 * True when the skills typed in the confirm dialog are no longer the ones
 * the draft's proposed blocks were built from.
 */
export function jobSkillsEdited(draft, skillsText) {
  const proposed = (draft?.proposed_skills || []).map((s) => String(s).trim().toLowerCase());
  const typed = skillList(skillsText).map((s) => s.toLowerCase());
  return proposed.length !== typed.length || proposed.some((s, i) => s !== typed[i]);
}

/**
 * Planned scope for the confirm dialog. The server's summary describes the
 * proposed blocks, so it is shown only while the skills are unchanged.
 */
export function jobLaunchScope(draft, skillsText) {
  return jobSkillsEdited(draft, skillsText) ? null : summarizeLaunchScope(draft?.planned_scope);
}

/**
 * Body for POST /jobs/{id}/practice. The proposed blocks are sent only while
 * they still match the skills: after an edit the server plans from the
 * confirmed skills (one free-text question for each of the first three)
 * instead of starting the blocks of skills the candidate removed.
 */
export function jobPracticeBody(draft, { skillsText, company, role, fullJd } = {}) {
  const body = {
    confirm: true,
    skills: skillList(skillsText),
    company,
    role,
    full_jd: fullJd || undefined,
  };
  if (!jobSkillsEdited(draft, skillsText)) body.blocks = draft?.proposed_blocks;
  return body;
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
