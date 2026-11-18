import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { ASSESSMENT_HINT_CONFIRM } from '../src/lib/codingHint.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(root, rel), 'utf8');

test('an assessment hint asks before the attempt stops counting toward readiness', () => {
  assert.equal(
    ASSESSMENT_HINT_CONFIRM,
    "this attempt becomes Practised with help and won't count toward readiness",
  );
  const coding = read('src/components/CodingRound.jsx');
  assert.match(coding, /practiceMode === 'assessment' && !window\.confirm\(ASSESSMENT_HINT_CONFIRM\)/);
  const interview = read('src/pages/Interview.jsx');
  assert.match(interview, /initState\.practice_mode \|\| initState\.practiceMode/);
  assert.match(interview, /practiceMode,/);
  const practice = read('src/pages/Practice.jsx');
  assert.match(practice, /navigateToInterview\(navigate, resp, \{ practice_mode: practiceMode \}\)/);
});
