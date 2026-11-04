/**
 * Back navigation that never strands the user (overhaul Phase 4). Pure.
 *
 * React Router gives the first entry of a fresh tab/deep link the key
 * "default"; any later in-app navigation has a generated key. Going back
 * one step is safe only when the app put an entry there itself.
 */

export function hasInAppHistory(location) {
  return Boolean(location?.key) && location.key !== 'default';
}

/** ``-1`` to go back in-app, otherwise the fallback route. */
export function backDestination(location, fallback = '/home') {
  return hasInAppHistory(location) ? -1 : fallback;
}

/** Path segments for app links, always encoded. */
export function gapAnalysisPath(userId, roleId) {
  return `/gap-analysis/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}`;
}

export function roadmapPath(userId, roleId, days = 30) {
  return `/roadmap/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}?days=${encodeURIComponent(days)}`;
}
