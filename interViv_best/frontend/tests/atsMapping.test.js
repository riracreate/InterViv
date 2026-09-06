import assert from 'node:assert/strict';
import test from 'node:test';

import { mapAtsResultToView } from '../src/lib/atsMapping.js';

test('ATS mapping exposes component scores for the result UI', () => {
  const view = mapAtsResultToView({
    total: 72.5,
    components: {
      parse_health: 100,
      section_complete: 75,
      keyword_coverage: 60,
      content_heuristics: 50,
    },
    weights: {
      parse_health: 0.25,
      section_complete: 0.2,
      keyword_coverage: 0.4,
      content_heuristics: 0.15,
    },
    flags: ['extract_layout_unchecked'],
    present_skills: ['DSA', 'DBMS'],
    missing_skills: ['HR'],
    suggested_practice_skills: ['HR'],
    role_id: 'tcs_swe',
    resume_id: 'cand-1',
  });
  assert.equal(view.total, 72.5);
  assert.equal(view.components.length, 4);
  assert.equal(view.components[0].key, 'parse_health');
  assert.equal(view.components[0].score, 100);
  assert.deepEqual(view.flags, ['extract_layout_unchecked']);
  assert.deepEqual(view.missingSkills, ['HR']);
  assert.equal(view.components[2].label, 'Keyword coverage');
});
