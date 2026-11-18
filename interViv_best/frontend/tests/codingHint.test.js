import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { codingHintLastError, codingHintPayload } from '../src/lib/codingHint.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(root, rel), 'utf8');

test('a runner error is sent instead of a failed example', () => {
  assert.equal(codingHintLastError({
    runnerError: 'Execution failed. Your solution remains in the editor.',
    visible: [{ passed: false, actual: 1, error: 'mismatch' }],
    tests: [{ input: { args: [1] }, expected: 2 }],
  }), 'Execution failed. Your solution remains in the editor.');
});

test('a compile or timeout failure on a visible case is the runner error', () => {
  assert.equal(codingHintLastError({
    visible: [{ passed: false, error: 'compile', message: 'Line 2: invalid syntax', actual: null }],
    tests: [{ input: { args: [[1], 2] }, expected: [0] }],
  }), 'compile: Line 2: invalid syntax');
});

test('the first failed visible test sends only input, expected and actual', () => {
  const raw = codingHintLastError({
    visible: [
      { passed: true, actual: [0, 1] },
      { passed: false, actual: null, error: 'mismatch' },
      { passed: false, actual: [9], error: 'mismatch' },
    ],
    tests: [
      { input: { args: [[2, 7], 9] }, expected: [0, 1] },
      { input: { args: [[3, 3], 6] }, expected: [0, 1] },
      { input: { args: [[1], 2] }, expected: [0] },
    ],
  });
  assert.deepEqual(JSON.parse(raw), {
    input: [[3, 3], 6],
    expected: [0, 1],
    actual: null,
  });
  assert.equal(raw.includes('hidden'), false);
});

test('the hint request carries source, language and that last error', () => {
  const body = codingHintPayload({
    sessionId: 's-1',
    round: 2,
    level: 1,
    source: 'def two_sum(nums, target):\n    pass\n',
    language: 'python',
    visible: [{ passed: false, actual: [], error: 'mismatch' }],
    tests: [{ input: { args: [[1, 2], 3] }, expected: [0, 1] }],
  });
  assert.equal(body.session_id, 's-1');
  assert.equal(body.language, 'python');
  assert.match(body.source, /def two_sum/);
  assert.deepEqual(JSON.parse(body.last_error), {
    input: [[1, 2], 3],
    expected: [0, 1],
    actual: [],
  });
});

test('CodingRound asks for a hint with the editor source and language', () => {
  const src = read('src/components/CodingRound.jsx');
  assert.match(src, /codingHintPayload\(\{[\s\S]*source,[\s\S]*language,/);
  assert.match(src, /fetchCodingCoach\(payload\)/);
});
