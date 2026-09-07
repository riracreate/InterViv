/**
 * Primary destinations for demo IA. Pure data for UI + tests.
 * Gap/Roadmap are contextual (need userId + roleId) — appended by AppNav when provided.
 */

export const PRIMARY_NAV_ITEMS = [
  { to: '/home', label: 'Home' },
  { to: '/dashboard', label: 'Progress' },
  { to: '/practice', label: 'Practice' },
  { to: '/ats', label: 'Resume check' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/coach', label: 'Coach' },
];

/** @param {{ userId?: string, roleId?: string }} opts */
export function contextualNavItems({ userId, roleId } = {}) {
  if (!userId || !roleId) return [];
  return [
    { to: `/gap-analysis/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}`, label: 'Gap' },
    { to: `/roadmap/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}?days=30`, label: 'Roadmap' },
  ];
}

export function isNavActive(pathname, itemTo) {
  const path = (pathname || '/').split('?')[0];
  const base = (itemTo || '').split('?')[0];
  if (base === '/dashboard') {
    return path === '/dashboard' || path.startsWith('/dashboard/');
  }
  return path === base || path.startsWith(`${base}/`);
}

export function navDestinations({ userId, roleId } = {}) {
  return [...PRIMARY_NAV_ITEMS, ...contextualNavItems({ userId, roleId })];
}
