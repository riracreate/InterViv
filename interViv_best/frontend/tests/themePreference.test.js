import test from 'node:test';
import assert from 'node:assert/strict';
import { readTheme, setTheme } from '../src/lib/theme.js';

test('the appearance preference persists on the device and has a safe default', () => {
  const oldStorage = globalThis.localStorage;
  const oldDocument = globalThis.document;
  const values = new Map();
  globalThis.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
  globalThis.document = { documentElement: { dataset: {} } };
  try {
    assert.equal(readTheme(), 'light');
    assert.equal(setTheme('dark'), 'dark');
    assert.equal(readTheme(), 'dark');
    assert.equal(globalThis.document.documentElement.dataset.theme, 'dark');
    assert.equal(setTheme('unknown'), 'light');
    assert.equal(readTheme(), 'light');
    globalThis.localStorage = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
    assert.equal(readTheme(), 'light');
    assert.equal(setTheme('dark'), 'dark');
  } finally {
    if (oldStorage === undefined) delete globalThis.localStorage; else globalThis.localStorage = oldStorage;
    if (oldDocument === undefined) delete globalThis.document; else globalThis.document = oldDocument;
  }
});
