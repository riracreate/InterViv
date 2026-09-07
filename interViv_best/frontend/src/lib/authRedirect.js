const STATIC_PATHS = new Set(['/', '/home', '/dashboard', '/practice', '/upload', '/ats', '/jobs', '/coach', '/resources']);
const DYNAMIC_PATH = /^\/(?:interview|dashboard)\/[A-Za-z0-9_-]+$|^\/(?:gap-analysis|roadmap)\/[A-Za-z0-9_-]+\/[A-Za-z0-9_-]+$/;

// Only application routes can be return destinations. Decode before validating:
// URL parsing alone leaves encoded separators and backslashes in pathname.
export function safeNext(raw, origin) {
  if (typeof raw !== 'string' || !raw.startsWith('/') || raw.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(raw)) return '/home';
  try {
    const url = new URL(raw, origin);
    if (url.origin !== new URL(origin).origin) return '/home';
    const path = decodeURIComponent(url.pathname);
    if (/[\\%\u0000-\u0020\u007f]/.test(path)) return '/home';
    const normalized = new URL(path, origin);
    if (normalized.origin !== url.origin || normalized.pathname !== path) return '/home';
    if (!STATIC_PATHS.has(path) && !DYNAMIC_PATH.test(path)) return '/home';
    return `${path}${url.search}${url.hash}`;
  } catch {
    return '/home';
  }
}

export function authDestination(location, origin) {
  return safeNext(location.state?.next ?? new URLSearchParams(location.search).get('next'), origin);
}
