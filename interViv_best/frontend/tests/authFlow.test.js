// Phase 4: a single 401 never logs anyone out; only a confirmed expiry does.
// Exercises the production request wrapper (lib/api.js) with stubbed transport.
import assert from 'node:assert/strict';
import test from 'node:test';

class MemoryStorage {
  constructor() { this.map = new Map(); }
  get length() { return this.map.size; }
  key(i) { return [...this.map.keys()][i] ?? null; }
  getItem(k) { return this.map.has(k) ? this.map.get(k) : null; }
  setItem(k, v) { this.map.set(k, String(v)); }
  removeItem(k) { this.map.delete(k); }
}

const TOKEN_KEY = 'interviv-auth-token';

function setup({ meStatus = 200, routeStatus = 401, delayRoute = null } = {}) {
  const calls = [];
  const redirects = [];
  globalThis.localStorage = new MemoryStorage();
  globalThis.sessionStorage = new MemoryStorage();
  globalThis.window = {
    location: {
      pathname: '/practice', search: '?mode=full', hash: '', origin: 'http://localhost',
      replace: (url) => redirects.push(url),
    },
  };
  globalThis.fetch = async (url, options = {}) => {
    const auth = options.headers instanceof Headers
      ? options.headers.get('Authorization')
      : options.headers?.Authorization;
    calls.push({ url, auth });
    if (url === '/api/auth/me') {
      return { ok: meStatus < 300, status: meStatus, json: async () => ({ id: 'u1' }) };
    }
    if (delayRoute) await delayRoute();
    return { ok: routeStatus < 300, status: routeStatus, json: async () => ({ detail: 'nope' }) };
  };
  return { calls, redirects };
}

function teardown() {
  for (const key of ['fetch', 'localStorage', 'sessionStorage', 'window']) delete globalThis[key];
}

const api = await import('../src/lib/api.js');

test('a 401 from an ordinary endpoint with a valid session keeps the user signed in', async () => {
  const { calls, redirects } = setup({ meStatus: 200 });
  localStorage.setItem(TOKEN_KEY, 't1');
  await assert.rejects(api.fetchNotebook(), (err) => err.kind === 'auth' && err.status === 401);
  assert.equal(localStorage.getItem(TOKEN_KEY), 't1');
  assert.deepEqual(redirects, []);
  assert.equal(calls.filter((c) => c.url === '/api/auth/me').length, 1);
  teardown();
});

test('confirmed expiry signs out once, even for concurrent 401s, and clears scoped state', async () => {
  const { calls, redirects } = setup({ meStatus: 401 });
  localStorage.setItem(TOKEN_KEY, 't1');
  sessionStorage.setItem('interviv:v1:u1:upload-wizard', '{"candidateId":"c1"}');
  await Promise.allSettled([api.fetchNotebook(), api.fetchBookmarks(), api.fetchRetrySets()]);
  assert.equal(calls.filter((c) => c.url === '/api/auth/me').length, 1);
  assert.equal(localStorage.getItem(TOKEN_KEY), null);
  assert.equal(sessionStorage.getItem('interviv:v1:u1:upload-wizard'), null);
  assert.equal(redirects.length, 1);
  assert.match(redirects[0], /^\/login\?next=%2Fpractice%3Fmode%3Dfull$/);
  teardown();
});

test('a 401 for a token that was replaced meanwhile is ignored', async () => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const { calls, redirects } = setup({ meStatus: 401, delayRoute: () => gate });
  localStorage.setItem(TOKEN_KEY, 'old');
  const pending = api.fetchNotebook();
  localStorage.setItem(TOKEN_KEY, 'new'); // signed in again while the request was in flight
  release();
  await assert.rejects(pending, (err) => err.status === 401);
  assert.equal(localStorage.getItem(TOKEN_KEY), 'new');
  assert.deepEqual(redirects, []);
  assert.equal(calls.filter((c) => c.url === '/api/auth/me').length, 0);
  teardown();
});

test('GET /auth/me answering 401 for the current token is itself the confirmation', async () => {
  const { redirects } = setup({ meStatus: 401 });
  localStorage.setItem(TOKEN_KEY, 't1');
  await assert.rejects(api.fetchMe(), (err) => err.kind === 'auth');
  assert.equal(localStorage.getItem(TOKEN_KEY), null);
  assert.equal(redirects.length, 1);
  teardown();
});

test('aborted requests are cancellations and network failures are retryable; neither logs out', async () => {
  setup();
  localStorage.setItem(TOKEN_KEY, 't1');
  globalThis.fetch = async () => { throw Object.assign(new Error('aborted'), { name: 'AbortError' }); };
  await assert.rejects(api.fetchNotebook(), (err) => err.kind === 'cancelled');
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(api.fetchNotebook(), (err) => err.kind === 'network' && /connection/.test(err.message));
  assert.equal(localStorage.getItem(TOKEN_KEY), 't1');
  teardown();
});

test('server errors are typed retryable errors and keep the session', async () => {
  setup({ routeStatus: 503 });
  localStorage.setItem(TOKEN_KEY, 't1');
  await assert.rejects(api.fetchNotebook(), (err) => err.kind === 'server' && err.status === 503);
  assert.equal(localStorage.getItem(TOKEN_KEY), 't1');
  teardown();
});

test('sign-in failures are credential errors, not session expiry', async () => {
  const { redirects } = setup({ routeStatus: 401 });
  await assert.rejects(api.login({ email: 'a@b.c', password: 'x' }), (err) => err.status === 401);
  assert.deepEqual(redirects, []);
  teardown();
});

test('signOut clears the token, the interview resume and scoped session values', () => {
  setup();
  localStorage.setItem(TOKEN_KEY, 't1');
  localStorage.setItem('adaptive-mock-interview-state', '{}');
  sessionStorage.setItem('interviv:v1:u1:upload-wizard', '{}');
  api.signOut();
  assert.equal(localStorage.getItem(TOKEN_KEY), null);
  assert.equal(localStorage.getItem('adaptive-mock-interview-state'), null);
  assert.equal(sessionStorage.length, 0);
  teardown();
});
