import assert from 'node:assert/strict';
import test from 'node:test';

import { PRIMARY_NAV_ITEMS } from '../src/lib/appNav.js';
import { mapCoachPlan } from '../src/lib/coachMapping.js';

test('primary nav separates Home actions from Progress reports', () => {
  const labels = PRIMARY_NAV_ITEMS.map((i) => i.label);
  assert.deepEqual(labels, ['Home', 'Progress', 'Practice', 'Problems', 'Resume check', 'Jobs', 'Coach']);
  const paths = PRIMARY_NAV_ITEMS.map((i) => i.to);
  assert.deepEqual(paths, ['/home', '/dashboard', '/practice', '/problems', '/ats', '/jobs', '/coach']);
});

test('coach steps hrefs include /practice or /jobs', () => {
  const view = mapCoachPlan({
    steps: [
      { title: 'Practice missing', why: 'SQL', href: '/practice?mode=custom&skills=SQL' },
      { title: 'Browse openings', why: 'Pune', href: '/jobs?q=backend' },
      { title: 'ATS', why: 'resume', href: '/ats' },
    ],
    practice_preview: { skills: ['SQL'], round_plan: ['technical_short_answer'] },
  });
  const hrefs = view.steps.map((s) => s.href);
  assert.ok(hrefs.some((h) => h.startsWith('/practice')));
  assert.ok(hrefs.some((h) => h.startsWith('/jobs')));
});
