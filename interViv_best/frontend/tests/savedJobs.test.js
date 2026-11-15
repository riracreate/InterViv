import test from 'node:test';
import assert from 'node:assert/strict';
import { isSavedJob, toggleSavedJob } from '../src/lib/savedJobs.js';

test('saved listings toggle independently by source and id', () => {
  const first = { id: '42', title: 'Engineer', provenance: 'adzuna' };
  const otherSource = { id: '42', title: 'Designer', provenance: 'greenhouse' };
  const saved = toggleSavedJob(toggleSavedJob([], first), otherSource);
  assert.equal(isSavedJob(saved, first), true);
  assert.equal(isSavedJob(saved, otherSource), true);
  assert.deepEqual(toggleSavedJob(saved, first), [otherSource]);
  assert.equal(saved.length, 2);
});
