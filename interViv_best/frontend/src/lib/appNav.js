/**
 * Signed-in navigation (overhaul Phase 6): five primary destinations.
 *
 *   Home · Practice · Coding Arena · Career & Resume ▾ · Progress
 *
 * Career & Resume groups Resume check and Jobs (resume upload for interview
 * rounds lives directly inside the Interview setup in Practice). Learn,
 * Resources, Coach, Gap analysis and Roadmap are secondary: reachable from
 * the "More" menu and from contextual links on the pages that need them.
 * Gap / Roadmap need a target role; without one they point at Home's target
 * picker and are never marked active.
 */

export const CAREER_ITEMS = [
  { to: '/ats', label: 'Resume check' },
  { to: '/jobs', label: 'Jobs' },
];

/** Primary destinations in order; a group renders as a dropdown. */
export const PRIMARY_NAV = [
  { to: '/home', label: 'Home' },
  { to: '/practice', label: 'Practice' },
  { to: '/problems', label: 'Coding Arena' },
  { label: 'Career & Resume', id: 'career', children: CAREER_ITEMS },
  { to: '/dashboard', label: 'Progress' },
];

/** Every primary link, flattened (groups expanded). */
export const PRIMARY_NAV_ITEMS = PRIMARY_NAV.flatMap((item) => item.children || [item]);

/** @param {{ userId?: string, roleId?: string }} opts */
export function contextualNavItems({ userId, roleId } = {}) {
  if (userId && roleId) {
    return [
      {
        to: `/gap-analysis/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}`,
        label: 'Gap analysis',
      },
      {
        to: `/roadmap/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}?days=30`,
        label: 'Roadmap',
      },
    ];
  }
  return [
    { to: '/home#target', label: 'Gap analysis' },
    { to: '/home#target', label: 'Roadmap' },
  ];
}

/** Secondary destinations (desktop "More" menu). */
export function secondaryNavItems({ userId, roleId } = {}) {
  return [
    { to: '/learn', label: 'Learn' },
    { to: '/resources', label: 'Resources' },
    { to: '/coach', label: 'Coach' },
    ...contextualNavItems({ userId, roleId }),
  ];
}

export function isNavActive(pathname, itemTo) {
  // "Set a target" prompts point at /home#target; they are not destinations.
  if (String(itemTo || '').includes('#')) return false;
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

/** A group is active when any of its children is. */
export function isGroupActive(pathname, group) {
  return (group.children || []).some((child) => isNavActive(pathname, child.to));
}

/** Small-screen menu sections: primary first, then secondary. */
export function mobileNavSections({ userId, roleId } = {}) {
  return [
    { title: 'Navigate', items: PRIMARY_NAV_ITEMS },
    { title: 'More', items: secondaryNavItems({ userId, roleId }) },
  ];
}
