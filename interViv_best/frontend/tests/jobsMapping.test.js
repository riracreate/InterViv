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

test('rejects hosts that are not Adzuna or Greenhouse', () => {
  assert.equal(jobApplyHref({ redirectUrl: 'https://evil.example/x' }), '');
  assert.equal(jobApplyHref({ redirectUrl: 'https://evilgreenhouse.io/phish' }), '');
  assert.equal(jobApplyHref({ redirectUrl: 'https://greenhouse.io.evil.com/x' }), '');
  assert.equal(jobApplyHref({ redirectUrl: 'javascript:alert(1)' }), '');
});

test('allows a Greenhouse board posting', () => {
  const href = 'https://boards.greenhouse.io/stripe/jobs/1';
  assert.equal(jobApplyHref({ redirectUrl: href }), href);
});

test('allows the company career site on a Greenhouse card', () => {
  const href = 'https://stripe.com/jobs/listing/backend/1';
  assert.equal(jobApplyHref({ redirectUrl: href, provenance: 'greenhouse' }), href);
  assert.equal(jobApplyHref({ redirectUrl: href }), '');
});
