/**
 * Central 401 handling (overhaul Phase 4). Pure apart from injected effects.
 *
 * A 401 from an ordinary endpoint is not proof the session expired (a stale
 * response from a replaced token, a race during sign-in, a misrouted
 * request). Before logging anyone out we ask GET /auth/me once — shared by
 * every concurrent 401 for the same token — and act only when that check
 * confirms the token the failing request used is still the current token
 * and is no longer valid.
 */

export const AUTH_CHECK = Object.freeze({
  VALID: 'valid',
  EXPIRED: 'expired',
  STALE: 'stale',
  UNKNOWN: 'unknown',
});

/**
 * @param {{
 *   verifyToken: (token: string) => Promise<number>,  // resolves to /auth/me HTTP status
 *   currentToken: () => string | null,
 *   onExpired: () => void,
 * }} deps
 */
export function createUnauthorizedHandler({ verifyToken, currentToken, onExpired }) {
  const inFlight = new Map();

  async function check(token) {
    let status;
    try {
      status = await verifyToken(token);
    } catch {
      return AUTH_CHECK.UNKNOWN; // network trouble is not an expiry
    }
    if (status === 401) {
      if (currentToken() !== token) return AUTH_CHECK.STALE;
      onExpired();
      return AUTH_CHECK.EXPIRED;
    }
    return status >= 200 && status < 300 ? AUTH_CHECK.VALID : AUTH_CHECK.UNKNOWN;
  }

  /** Call with the token the failing request was sent with. */
  return function handleUnauthorized(tokenUsed) {
    if (!tokenUsed || currentToken() !== tokenUsed) return Promise.resolve(AUTH_CHECK.STALE);
    if (inFlight.has(tokenUsed)) return inFlight.get(tokenUsed);
    const pending = check(tokenUsed).finally(() => inFlight.delete(tokenUsed));
    inFlight.set(tokenUsed, pending);
    return pending;
  };
}

/**
 * GET /auth/me answering 401 for the current token is itself the
 * confirmation; sign-in/sign-up 401s are credential errors, not expiry.
 */
export function unauthorizedRoute(path, method = 'GET') {
  const clean = String(path || '').split('?')[0];
  if (clean === '/auth/me' && String(method).toUpperCase() === 'GET') return 'confirmed';
  if (clean.startsWith('/auth/login') || clean.startsWith('/auth/signup')) return 'credentials';
  return 'verify';
}
