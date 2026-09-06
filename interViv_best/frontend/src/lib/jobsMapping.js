/**
 * Pure helpers for job explorer cards (Ticket D).
 */

export function mapJobCard(job) {
  if (!job || typeof job !== "object") return null;
  return {
    id: job.id,
    title: job.title || "",
    company: job.company || "",
    location: job.location || "",
    matchPct: job.match_pct == null ? null : Number(job.match_pct),
    skills: Array.isArray(job.skills) ? job.skills : [],
    redirectUrl: job.redirect_url || "",
    salaryMin: job.salary_min ?? null,
    salaryMax: job.salary_max ?? null,
    snippet: job.snippet || "",
  };
}

export function jobApplyHref(card) {
  return card?.redirectUrl || "";
}
