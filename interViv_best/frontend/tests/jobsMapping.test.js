import assert from 'node:assert/strict';
import test from 'node:test';

import { jobApplyHref, mapJobCard } from '../src/lib/jobsMapping.js';

test('job card Apply href comes from redirect_url', () => {
  const card = mapJobCard({
    id: 'adzuna:1',
    title: 'SDE Intern',
    company: 'Acme',
    location: 'Pune',
    match_pct: 40,
    skills: ['Python'],
    redirect_url: 'https://www.adzuna.co.in/details/1',
  });
  assert.equal(card.title, 'SDE Intern');
  assert.equal(jobApplyHref(card), 'https://www.adzuna.co.in/details/1');
  assert.equal(card.matchPct, 40);
});
