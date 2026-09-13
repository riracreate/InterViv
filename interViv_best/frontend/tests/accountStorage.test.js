// Phase AB (Z-F03): browser-persisted state must not cross accounts on a
// shared browser. Signin/signup call saveAuthToken; signout calls
// clearAuthToken — the same functions the pages use.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  clearAuthToken,
  loadInterviewState,
  saveAuthToken,
  saveInterviewState,
} from '../src/lib/api.js';
import {
  LEGACY_BUILDER_DRAFT_KEY,
  BUILDER_DRAFT_VERSION,
  loadLocalBuilderDraft,
  saveLocalBuilderDraft,
  validateBuilderBlocks,
} from '../src/lib/practiceBuilder.js';

class MemoryStorage {
  #items = new Map();
  getItem(key) { return this.#items.has(key) ? this.#items.get(key) : null; }
  setItem(key, value) { this.#items.set(key, String(value)); }
  removeItem(key) { this.#items.delete(key); }
  clear() { this.#items.clear(); }
}

const ONE = [{ id: 'b1', category: 'coding', round_type: 'coding', skills: ['DSA'], count: 1, duration_minutes: 1 }];
const TWO = [{ id: 'b2', category: 'oa', round_type: 'mcq', skills: ['Python'], count: 1, duration_minutes: 5 }];
const signIn = (user) => saveAuthToken(`token-${user}`);
const signOut = () => clearAuthToken();

test.beforeEach(() => {
  globalThis.localStorage = new MemoryStorage();
});

test('fixtures are valid builder drafts', () => {
  assert.equal(validateBuilderBlocks(ONE), null);
  assert.equal(validateBuilderBlocks(TWO), null);
});

test('builder draft saved under one account is not visible to another after signout and signin', () => {
  signIn('one');
  saveLocalBuilderDraft('user-one', ONE);
  signOut();
  signIn('two');
  assert.equal(loadLocalBuilderDraft('user-two'), null);
  // Reload: nothing new was written, so the draft still does not appear.
  assert.equal(loadLocalBuilderDraft('user-two'), null);
});

test('pre-existing unnamespaced legacy draft never surfaces and is removed on signin and signout', () => {
  const legacy = JSON.stringify({ version: BUILDER_DRAFT_VERSION, blocks: ONE });
  localStorage.setItem(LEGACY_BUILDER_DRAFT_KEY, legacy);
  assert.equal(loadLocalBuilderDraft('user-one'), null);
  assert.equal(loadLocalBuilderDraft('user-two'), null);
  signIn('two');
  assert.equal(localStorage.getItem(LEGACY_BUILDER_DRAFT_KEY), null);
  localStorage.setItem(LEGACY_BUILDER_DRAFT_KEY, legacy);
  signOut();
  assert.equal(localStorage.getItem(LEGACY_BUILDER_DRAFT_KEY), null);
});

test('each account keeps and recovers its own builder draft across signout and signin', () => {
  signIn('one');
  saveLocalBuilderDraft('user-one', ONE);
  signOut();
  signIn('two');
  saveLocalBuilderDraft('user-two', TWO);
  signOut();
  signIn('one');
  assert.deepEqual(loadLocalBuilderDraft('user-one'), ONE);
  assert.deepEqual(loadLocalBuilderDraft('user-two'), TWO);
});

test('builder draft is not written or read without a signed-in account id', () => {
  saveLocalBuilderDraft(null, ONE);
  assert.equal(localStorage.getItem(LEGACY_BUILDER_DRAFT_KEY), null);
  assert.equal(loadLocalBuilderDraft(null), null);
});

test('auth token key: signout removes it and signin replaces it', () => {
  signIn('one');
  assert.equal(localStorage.getItem('interviv-auth-token'), 'token-one');
  signOut();
  assert.equal(localStorage.getItem('interviv-auth-token'), null);
  signIn('two');
  assert.equal(localStorage.getItem('interviv-auth-token'), 'token-two');
});

test('interview state key is cleared on signout and on signin without a signout', () => {
  signIn('one');
  saveInterviewState({ sessionId: 'one-session', question: 'account one question' });
  signOut();
  assert.equal(loadInterviewState(), null);
  signIn('one');
  saveInterviewState({ sessionId: 'one-session', question: 'account one question' });
  signIn('two'); // expired token → login as another account, no signout click
  assert.equal(loadInterviewState(), null);
});

const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src');
function sources(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? sources(full) : /\.(jsx?|tsx?)$/.test(entry.name) ? [full] : [];
  });
}

test('audit pin: no sessionStorage, IndexedDB or cookies; localStorage only in api.js and practiceBuilder.js', () => {
  for (const file of sources(srcDir)) {
    const text = readFileSync(file, 'utf8');
    const rel = path.relative(srcDir, file);
    assert.doesNotMatch(text, /sessionStorage|indexedDB|document\.cookie/, rel);
    if (!['lib/api.js', 'lib/practiceBuilder.js'].includes(rel.split(path.sep).join('/'))) {
      assert.doesNotMatch(text, /localStorage/, `${rel} writes browser storage outside the audited modules`);
    }
  }
});
