/**
 * Upload skill picker helpers (overhaul Phase 6). Pure.
 * Each skill appears under exactly one domain (its first), and a search
 * narrows domains to matching skills.
 */

export function dedupeDomainSkills(domains) {
  const seen = new Set();
  return (domains || []).map((domain) => ({
    ...domain,
    skills: (domain.skills || []).filter((skill) => {
      const key = String(skill).toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }),
  }));
}

export function filterDomains(domains, query) {
  const q = String(query || '').trim().toLowerCase();
  if (!q) return domains;
  return domains
    .map((domain) => {
      const nameMatch = domain.name.toLowerCase().includes(q) || String(domain.short || '').toLowerCase().includes(q);
      const skills = nameMatch ? domain.skills : domain.skills.filter((s) => s.toLowerCase().includes(q));
      return { ...domain, skills };
    })
    .filter((domain) => domain.skills.length > 0);
}

export function selectedCount(domain, selected) {
  const chosen = new Set((selected || []).map((s) => String(s).toLowerCase()));
  return domain.skills.filter((s) => chosen.has(s.toLowerCase())).length;
}
