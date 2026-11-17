export const ROLE_PRACTICE_ENABLED = import.meta.env?.VITE_ROLE_PRACTICE === '1';

export function filterRoles(roles, query) {
  const needle = String(query || '').trim().toLowerCase();
  if (!needle) return roles;
  return roles.filter(role => {
    const names = [role.title, ...(role.aliases || [])].join(' ').toLowerCase();
    return names.includes(needle);
  });
}

export function swapCore(slots, alternatives, index) {
  const current = slots[index];
  const next = (alternatives || [])[0];
  if (!current || current.kind !== 'core' || !next) return { slots, alternatives };
  const swapped = {
    ...current,
    competency_id: next.competency_id,
    name: next.name,
    skill: next.skill,
    reason: `${next.skill}: swapped in`,
  };
  const unused = {
    competency_id: current.competency_id,
    name: current.name,
    skill: current.skill,
  };
  return {
    slots: slots.map((slot, slotIndex) => slotIndex === index ? swapped : slot),
    alternatives: [...alternatives.slice(1), unused],
  };
}
