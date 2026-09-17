import assert from 'node:assert/strict';
import test from 'node:test';

import { formatSalary, jobApplyHref, mapJobCard } from '../src/lib/jobsMapping.js';

test('job card View href comes from redirect_url', () => {
  const card = mapJobCard({
    id: 'adzuna:1',
    title: 'SDE Intern',
    company: 'Acme',
    location: 'Pune',
    match_pct: 40,
    skills: ['Python'],
    redirect_url: 'https://www.adzuna.co.in/details/1',
    salary_min: 10,
    salary_max: 20,
    salary_is_predicted: true,
  });
  assert.equal(card.title, 'SDE Intern');
  assert.equal(jobApplyHref(card), 'https://www.adzuna.co.in/details/1');
  assert.equal(card.matchPct, 40);
  assert.match(formatSalary(card), /Jobsworth/);
});

test('rejects non-Adzuna redirect hosts', () => {
  assert.equal(jobApplyHref({ redirectUrl: 'https://evil.example/x' }), '');
  assert.equal(jobApplyHref({ redirectUrl: 'javascript:alert(1)' }), '');
});
