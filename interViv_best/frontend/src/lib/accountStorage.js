/**
 * Account-scoped, versioned browser storage (overhaul Phase 4).
 *
 * Keys look like ``interviv:v1:<userId>:<name>`` so one account's state
 * never surfaces under another account on a shared browser. Every access is
 * wrapped: private windows, blocked storage and quota errors degrade to
 * "nothing saved", never to an exception. Session-scoped values are cleared
 * on sign-in, sign-up and sign-out.
 */

const PREFIX = 'interviv:';

function storageArea(kind) {
  try {
    const area = kind === 'local' ? globalThis.localStorage : globalThis.sessionStorage;
    return area || null;
  } catch {
    return null;
  }
}

export function scopedKey(userId, name, version = 1) {
  if (!userId || !name) return null;
  return `${PREFIX}v${version}:${userId}:${name}`;
}

export function readScoped(kind, userId, name, version = 1) {
  const key = scopedKey(userId, name, version);
  const area = storageArea(kind);
  if (!key || !area) return null;
  try {
    const raw = area.getItem(key);
    return raw == null ? null : JSON.parse(raw);
  } catch {
    return null;
  }
}

export function writeScoped(kind, userId, name, value, version = 1) {
  const key = scopedKey(userId, name, version);
  const area = storageArea(kind);
  if (!key || !area) return false;
  try {
    area.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function removeScoped(kind, userId, name, version = 1) {
  const key = scopedKey(userId, name, version);
  const area = storageArea(kind);
  if (!key || !area) return;
  try { area.removeItem(key); } catch { /* storage unavailable */ }
}

/** Non-sensitive appearance preferences are shared across accounts on a device. */
export function readDevicePreference(name) {
  if (!name) return null;
  try {
    const raw = storageArea('local')?.getItem(`${PREFIX}preference:${name}`);
    return raw == null ? null : JSON.parse(raw);
  } catch { return null; }
}

export function writeDevicePreference(name, value) {
  if (!name) return false;
  try {
    const area = storageArea('local');
    if (!area) return false;
    area.setItem(`${PREFIX}preference:${name}`, JSON.stringify(value));
    return true;
  } catch { return false; }
}

/** Remove every scoped session value (sign-in, sign-up, sign-out). */
export function clearSessionScopedState() {
  const area = storageArea('session');
  if (!area) return;
  try {
    const keys = [];
    for (let i = 0; i < area.length; i += 1) {
      const key = area.key(i);
      if (key && key.startsWith(PREFIX)) keys.push(key);
    }
    keys.forEach((key) => area.removeItem(key));
  } catch { /* storage unavailable */ }
}
