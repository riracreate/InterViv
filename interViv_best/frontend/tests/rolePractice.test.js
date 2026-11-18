import assert from 'node:assert/strict';
import test from 'node:test';
import { filterRoles, swapCore } from '../src/lib/rolePractice.js';

const roles = [
  { id: 'data-analyst', title: 'Data Analyst', aliases: ['BI Analyst'] },
  { id: 'backend-engineer', title: 'Backend Engineer', aliases: ['SDE-1 (Backend)'] },
];

test('role search matches titles and aliases', () => {
  assert.deepEqual(filterRoles(roles, 'bi').map(role => role.id), ['data-analyst']);
  assert.deepEqual(filterRoles(roles, 'sde').map(role => role.id), ['backend-engineer']);
  assert.equal(filterRoles(roles, '').length, 2);
});

test('swap replaces a core slot and keeps the unused skill available', () => {
  const slots = [
    { kind: 'opener', skill: 'SQL', reason: 'SQL: easy bank warm-up' },
    { kind: 'core', competency_id: 'sql', name: 'SQL', skill: 'SQL', reason: 'SQL: core skill for this role' },
  ];
  const alternatives = [{ competency_id: 'stats', name: 'Statistics', skill: 'Statistics' }];
  const next = swapCore(slots, alternatives, 1);
  assert.equal(next.slots[1].skill, 'Statistics');
  assert.equal(next.slots[1].reason, 'Statistics: swapped in');
  assert.equal(next.alternatives[0].skill, 'SQL');
  assert.equal(swapCore(slots, [], 1).slots[1].skill, 'SQL');
});
