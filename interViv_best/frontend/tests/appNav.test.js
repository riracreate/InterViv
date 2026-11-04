import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CAREER_ITEMS,
  PRIMARY_NAV,
  PRIMARY_NAV_ITEMS,
  contextualNavItems,
  isGroupActive,
  mobileNavSections,
  secondaryNavItems,
} from '../src/lib/appNav.js';
import { mapCoachPlan } from '../src/lib/coachMapping.js';

test('five primary destinations, with Career & Resume as a group', () => {
  assert.deepEqual(PRIMARY_NAV.map((i) => i.label),
    ['Home', 'Practice', 'Coding Arena', 'Career & Resume', 'Progress']);
  assert.deepEqual(CAREER_ITEMS.map((i) => `${i.label}:${i.to}`),
    ['Resume check:/ats', 'Jobs:/jobs']);
  assert.equal(PRIMARY_NAV.find((i) => i.label === 'Coding Arena').to, '/problems');
  assert.deepEqual(PRIMARY_NAV_ITEMS.map((i) => i.to),
    ['/home', '/practice', '/problems', '/ats', '/jobs', '/dashboard']);
});

test('Learn, Resources, Coach, Gap analysis and Roadmap are secondary', () => {
  const labels = secondaryNavItems({}).map((i) => i.label);
  assert.deepEqual(labels, ['Learn', 'Resources', 'Coach', 'Gap analysis', 'Roadmap']);
  const withTarget = contextualNavItems({ userId: 'u1', roleId: 'r1' });
  assert.match(withTarget[0].to, /\/gap-analysis\/u1\/r1/);
  assert.match(withTarget[1].to, /\/roadmap\/u1\/r1/);
  assert.deepEqual(contextualNavItems({}).map((i) => i.to), ['/home#target', '/home#target']);
});

test('the Career group is active on any of its pages; small screens list everything', () => {
  const career = PRIMARY_NAV.find((i) => i.children);
  assert.equal(isGroupActive('/ats', career), true);
  assert.equal(isGroupActive('/practice', career), false);
  const sections = mobileNavSections({});
  const all = sections.flatMap((s) => s.items.map((i) => i.label));
  for (const label of ['Home', 'Practice', 'Coding Arena', 'Resume check', 'Jobs', 'Progress', 'Learn', 'Coach']) {
    assert.ok(all.includes(label), label);
  }
  assert.ok(!all.includes('Resume upload'));
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
