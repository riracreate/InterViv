/**
 * Primary destinations for the signed-in app shell (unified).
 * Gap / Roadmap need a target role for a deep link; without one they point at
 * Home's target picker so the items stay visible in the nav.
 */

export const PRIMARY_NAV_ITEMS = [
  { to: '/home', label: 'Home' },
  { to: '/dashboard', label: 'Progress' },
  { to: '/practice', label: 'Practice' },
  { to: '/problems', label: 'Problems' },
  { to: '/learn', label: 'Learn' },
  { to: '/resources', label: 'Resources' },
  { to: '/ats', label: 'Resume check' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/coach', label: 'Coach' },
  { to: '/upload', label: 'Resume upload' },
];

/** @param {{ userId?: string, roleId?: string }} opts */
export function contextualNavItems({ userId, roleId } = {}) {
  if (userId && roleId) {
    return [
      {
        to: `/gap-analysis/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}`,
        label: 'Gap',
      },
      {
        to: `/roadmap/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}?days=30`,
        label: 'Roadmap',
      },
    ];
  }
  return [
    { to: '/home#target', label: 'Gap' },
    { to: '/home#target', label: 'Roadmap' },
  ];
}

export function isNavActive(pathname, itemTo) {
  const path = (pathname || '/').split('?')[0];
  const base = (itemTo || '').split('?')[0].split('#')[0];
  if (base === '/dashboard') {
    return path === '/dashboard' || path.startsWith('/dashboard/');
  }
  if (base.startsWith('/gap-analysis')) {
    return path.startsWith('/gap-analysis');
  }
  if (base.startsWith('/roadmap')) {
    return path.startsWith('/roadmap');
  }
  return path === base || path.startsWith(`${base}/`);
}

/** Core trio, then Gap/Roadmap, then the rest of PRIMARY. */
export function navDestinations({ userId, roleId } = {}) {
  const core = PRIMARY_NAV_ITEMS.filter((i) =>
    ['/home', '/dashboard', '/practice'].includes(i.to)
  );
  const rest = PRIMARY_NAV_ITEMS.filter(
    (i) => !['/home', '/dashboard', '/practice'].includes(i.to)
  );
  return [...core, ...contextualNavItems({ userId, roleId }), ...rest];
}
