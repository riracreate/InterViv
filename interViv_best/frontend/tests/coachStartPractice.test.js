import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'src/pages/Coach.jsx'), 'utf8');

test('Assess independently sends assessment mode', () => {
  const run = src.slice(src.indexOf('const runAction'), src.indexOf('const startPractice'));
  assert.match(run, /action\.type === 'assess_independently' \? \{ practice_mode: 'assessment' \}/);
});
