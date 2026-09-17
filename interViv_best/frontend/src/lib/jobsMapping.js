/**
 * Pure helpers for job explorer cards (Adzuna).
 */

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
  };
}

export function jobApplyHref(card) {
  const href = card?.redirectUrl || '';
  if (!href) return '';
  try {
    const u = new URL(href);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return '';
    const host = u.hostname.toLowerCase();
    if (!host.includes('adzuna.')) return '';
    return href;
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
