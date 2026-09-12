import assert from 'node:assert/strict';
import test from 'node:test';

import {
  PRIMARY_NAV_ITEMS,
  contextualNavItems,
  navDestinations,
} from '../src/lib/appNav.js';
import { mapCoachPlan } from '../src/lib/coachMapping.js';

test('primary nav includes unified destinations with Resources', () => {
  const labels = PRIMARY_NAV_ITEMS.map((i) => i.label);
  assert.deepEqual(labels, [
    'Home',
    'Progress',
    'Practice',
    'Problems',
    'Learn',
    'Resources',
    'Resume check',
    'Jobs',
    'Coach',
    'Resume upload',
  ]);
});

test('nav destinations always include Gap and Roadmap', () => {
  const labels = navDestinations({}).map((i) => i.label);
  assert.ok(labels.includes('Gap'));
  assert.ok(labels.includes('Roadmap'));
  assert.ok(labels.includes('Resources'));
  assert.ok(labels.includes('Problems'));

  const withTarget = contextualNavItems({ userId: 'u1', roleId: 'r1' });
  assert.match(withTarget[0].to, /\/gap-analysis\/u1\/r1/);
  assert.match(withTarget[1].to, /\/roadmap\/u1\/r1/);
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
