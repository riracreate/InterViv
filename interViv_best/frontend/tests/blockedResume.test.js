import test from 'node:test';
import assert from 'node:assert/strict';
import { blockedResumeFromSession } from '../src/lib/blockedResume.js';

test('active sessions are not treated as blocked', () => {
  const next = blockedResumeFromSession({ status: 'active', active_round: { final_score: 80 } });
  assert.equal(next.progressionBlocked, false);
});

test('content_blocked restores score feedback and retry hint', () => {
  const next = blockedResumeFromSession({
    status: 'content_blocked',
    progression_blocked_reason: 'No matching inventory.',
    active_round: {
      round: 1,
      final_score: 70,
      feedback: { content: ['Keep going'], next_step: 'Review ACID' },
    },
  });
  assert.equal(next.progressionBlocked, true);
  assert.equal(next.progressionBlockedReason, 'No matching inventory.');
  assert.equal(next.currentScore, 70);
  assert.equal(next.currentFeedback, 'Review ACID');
  assert.equal(next.round, 1);
});
