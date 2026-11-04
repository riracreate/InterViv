/**
 * Typed request errors (overhaul Phase 4). Pure: no network, no storage.
 *
 * Every error thrown by lib/api.js carries ``kind`` and ``status``:
 *   cancelled — the request was aborted (navigation, unmount); never shown
 *   network   — no response (offline, server down); retryable
 *   auth      — 401; confirmed expiry is handled once, centrally, in api.js
 *   server    — 5xx/429; retryable
 *   client    — other 4xx; show the message
 */

export const ERROR_KINDS = Object.freeze({
  CANCELLED: 'cancelled',
  NETWORK: 'network',
  AUTH: 'auth',
  SERVER: 'server',
  CLIENT: 'client',
});

export function kindForStatus(status) {
  if (status === 401) return ERROR_KINDS.AUTH;
  if (status === 429 || status >= 500) return ERROR_KINDS.SERVER;
  return ERROR_KINDS.CLIENT;
}

export function makeRequestError({ kind, status = 0, message, detail, cause } = {}) {
  const error = new Error(message || defaultMessage(kind));
  error.kind = kind;
  error.status = status;
  if (detail !== undefined) error.detail = detail;
  if (cause !== undefined) error.cause = cause;
  return error;
}

function defaultMessage(kind) {
  if (kind === ERROR_KINDS.NETWORK) return 'Could not reach interViv. Check your connection and try again.';
  if (kind === ERROR_KINDS.CANCELLED) return 'Request cancelled.';
  if (kind === ERROR_KINDS.SERVER) return 'interViv is having trouble right now. Please try again.';
  return 'Something went wrong';
}

/** Translate a fetch() rejection (no response) into a typed error. */
export function errorFromFetchFailure(err, signal) {
  if (err?.name === 'AbortError' || signal?.aborted) {
    return makeRequestError({ kind: ERROR_KINDS.CANCELLED, cause: err });
  }
  return makeRequestError({ kind: ERROR_KINDS.NETWORK, cause: err });
}

export function errorKind(err) {
  if (!err) return null;
  if (err.kind) return err.kind;
  if (err.name === 'AbortError') return ERROR_KINDS.CANCELLED;
  if (typeof err.status === 'number' && err.status > 0) return kindForStatus(err.status);
  return ERROR_KINDS.NETWORK;
}

export const isCancelled = (err) => errorKind(err) === ERROR_KINDS.CANCELLED;
export const isAuthError = (err) => errorKind(err) === ERROR_KINDS.AUTH;
export const isRetryable = (err) => [ERROR_KINDS.NETWORK, ERROR_KINDS.SERVER].includes(errorKind(err));

/**
 * What a page should do when loading the signed-in account fails.
 *   ignore — cancelled; the page is going away or reloading
 *   signin — authentication confirmed invalid (api.js already redirects)
 *   retry  — anything else: keep the page and offer "Try again"
 */
export function accountLoadAction(err) {
  if (isCancelled(err)) return 'ignore';
  if (isAuthError(err)) return 'signin';
  return 'retry';
}
