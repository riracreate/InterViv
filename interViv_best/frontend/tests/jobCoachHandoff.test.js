import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { jobCoachHandoff } from '../src/lib/jobsMapping.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(root, rel), 'utf8');

test('Continue in Coach uses the edited skills and role and the draft job id', () => {
  const handoff = jobCoachHandoff({
    prepare: {
      job_id: 'job-42',
      role_id: 'role-1',
      role: 'Backend intern',
      title: 'Listing title',
      company: 'Acme',
      skills: ['Django'],
    },
    draftSkills: 'DBMS, SQL',
    draftRole: 'Data intern',
    draftCompany: 'Northwind',
    fullJd: '',
  });
  assert.equal(handoff.target.job_id, 'job-42');
  assert.equal(handoff.goals.confirmed_goal, 'Data intern');
  assert.deepEqual(handoff.goals.planning_context_skills, ['DBMS', 'SQL']);
  assert.equal(handoff.goals.adzuna_context.job_id, 'job-42');
  assert.equal(handoff.goals.adzuna_context.role_title, 'Data intern');
  assert.equal(handoff.goals.adzuna_context.company, 'Northwind');
  assert.deepEqual(handoff.goals.adzuna_context.confirmed_skills, ['DBMS', 'SQL']);
});

test('the Jobs coach button no longer reads an undeclared selected job id', () => {
  const jobs = read('src/pages/Jobs.jsx');
  assert.doesNotMatch(jobs, /selectedJobId/);
  assert.match(jobs, /jobCoachHandoff\(\{\s*prepare, draftSkills, draftRole, draftCompany, fullJd,/);
  const coach = read('src/pages/Coach.jsx');
  assert.match(coach, /fetchStudyPlan\(\{/);
  assert.match(coach, /goals\.confirmed_goal/);
  assert.match(coach, /setStudyPlan\(planResp\.plan\)/);
});
