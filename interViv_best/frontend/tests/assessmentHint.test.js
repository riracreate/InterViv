import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { ASSESSMENT_HINT_CONFIRM, assessmentHintConfirmRequired } from '../src/lib/codingHint.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(root, rel), 'utf8');

test('an assessment hint asks after the server requires confirmation, then resends', () => {
  assert.equal(
    ASSESSMENT_HINT_CONFIRM,
    "this attempt becomes Practised with help and won't count toward readiness",
  );
  assert.equal(assessmentHintConfirmRequired({ status: 409, code: 'confirm_required' }), true);
  assert.equal(assessmentHintConfirmRequired({ status: 409, code: 'other' }), false);
  const coding = read('src/components/CodingRound.jsx');
  assert.match(coding, /assessmentHintConfirmRequired\(err\)/);
  assert.match(coding, /window\.confirm\(ASSESSMENT_HINT_CONFIRM\)/);
  assert.match(coding, /await requestHint\(true\)/);
  const hint = read('src/lib/codingHint.js');
  assert.match(hint, /confirm_assessment_help = true/);
});
