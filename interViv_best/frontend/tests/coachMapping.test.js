import assert from 'node:assert/strict';
import test from 'node:test';

import { mapCoachPlan } from '../src/lib/coachMapping.js';

test('coach steps render hrefs from mock payload', () => {
  const view = mapCoachPlan({
    needs_clarification: false,
    have_skills: ['Python'],
    missing_skills: ['SQL'],
    unrecognized: ['FooLang — unrecognized — not practiced on this platform'],
    recognized_skills: ['Python', 'SQL'],
    steps: [
      { title: 'Practice', why: 'Missing SQL', href: '/practice?mode=custom&skills=SQL' },
      { title: 'Jobs', why: 'Openings', href: '/jobs?q=backend' },
      { title: 'Bad', why: 'skip', href: 'https://evil.example' },
    ],
    practice_preview: { skills: ['SQL'], round_plan: ['technical_short_answer'] },
    disclaimer: 'Coach maps your text onto interViv skills. It does not score interviews.',
  });
  assert.equal(view.steps.length, 2);
  assert.equal(view.steps[0].href, '/practice?mode=custom&skills=SQL');
  assert.equal(view.steps[1].href, '/jobs?q=backend');
  assert.equal(view.practicePreview.skills[0], 'SQL');
  assert.ok(view.disclaimer.includes('does not score'));
});
