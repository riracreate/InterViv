const dsn = import.meta.env.VITE_SENTRY_DSN || '';
const environment = import.meta.env.VITE_SENTRY_ENVIRONMENT || import.meta.env.MODE || 'development';
const release = import.meta.env.VITE_SENTRY_RELEASE || undefined;

function parseDsn(value) {
  try {
    const url = new URL(value);
    const projectId = url.pathname.replace('/', '').trim();
    if (!url.username || !projectId) return null;
    return {
      dsn: value,
      endpoint: `${url.protocol}//${url.host}/api/${projectId}/envelope/`,
      publicKey: url.username,
    };
  } catch {
    return null;
  }
}

function uuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replaceAll('-', '');
  return Math.random().toString(16).slice(2).padEnd(32, '0').slice(0, 32);
}

function stackFrames(error) {
  const stack = String(error?.stack || '').split('\n').slice(1, 30);
  return stack.map((line) => ({ filename: line.trim() })).reverse();
}

export function captureFrontendError(error, context = {}) {
  const parsed = parseDsn(dsn);
  if (!parsed) return;

  const eventId = uuid();
  const now = new Date().toISOString();
  const name = error?.name || 'Error';
  const message = error?.message || String(error || 'Unknown frontend error');
  const event = {
    event_id: eventId,
    timestamp: now,
    platform: 'javascript',
    level: 'error',
    environment,
    release,
    tags: { app: 'interviv-frontend' },
    extra: context,
    exception: {
      values: [
        {
          type: name,
          value: message,
          stacktrace: { frames: stackFrames(error) },
        },
      ],
    },
  };
  const envelope = [
    JSON.stringify({ event_id: eventId, dsn: parsed.dsn, sent_at: now }),
    JSON.stringify({ type: 'event' }),
    JSON.stringify(event),
  ].join('\n');

  navigator.sendBeacon?.(parsed.endpoint, new Blob([envelope], { type: 'text/plain' })) ||
    fetch(parsed.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: envelope,
      keepalive: true,
    }).catch(() => {});
}

export function initSentry() {
  if (!parseDsn(dsn)) return false;
  window.addEventListener('error', (event) => {
    captureFrontendError(event.error || event.message, { source: 'window.error' });
  });
  window.addEventListener('unhandledrejection', (event) => {
    captureFrontendError(event.reason, { source: 'unhandledrejection' });
  });
  return true;
}
