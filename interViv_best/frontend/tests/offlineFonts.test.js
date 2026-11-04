/**
 * Phase P — default CSS must not contact fonts.googleapis.com / fonts.gstatic.com.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

test('index.css does not import Google Fonts CDN under default offline config', () => {
  const css = readFileSync(join(root, 'src/index.css'), 'utf8');
  assert.equal(
    /fonts\.googleapis\.com|fonts\.gstatic\.com/i.test(css),
    false,
    'default index.css must not load Google Fonts (Phase P outbound gate)',
  );
});

test('fonts.css documents the opt-in Google Fonts URL without activating it', () => {
  const css = readFileSync(join(root, 'src/styles/fonts.css'), 'utf8');
  assert.match(css, /fonts\.googleapis\.com/);
  assert.equal(
    /^\s*@import\s+url\(/m.test(css),
    false,
    'opt-in URL must remain commented / inactive in fonts.css',
  );
});
