import test from 'node:test';
import assert from 'node:assert/strict';
import {
  applyFeedbackPollResult,
  shouldKeepPollingNarration,
} from '../src/lib/feedbackPoll.js';

test('polling stops on terminal narration statuses', () => {
  assert.equal(shouldKeepPollingNarration('queued'), true);
  assert.equal(shouldKeepPollingNarration('processing'), true);
  assert.equal(shouldKeepPollingNarration('skipped'), false);
  assert.equal(shouldKeepPollingNarration('done'), false);
  assert.equal(shouldKeepPollingNarration('failed'), false);
});

test('stale round responses are ignored', () => {
  const state = {
    rulesFeedback: { content: ['Keep'] },
    displayFeedback: 'Keep',
    narrationStatus: 'queued',
    polling: true,
  };
  const next = applyFeedbackPollResult(state, {
    round: 2,
    feedback: { content: ['Other'] },
    narration: { status: 'done', script: 'Wrong round', source: 'provider' },
  }, 1);
  assert.equal(next.ignoredStale, true);
  assert.equal(next.displayFeedback, 'Keep');
});

test('rules stay visible when narration is skipped', () => {
  const state = {
    displayFeedback: 'Rules text',
    displaySource: 'Rules feedback',
    narrationStatus: 'queued',
    polling: true,
  };
  const next = applyFeedbackPollResult(state, {
    round: 1,
    feedback: { content: ['Rules text'], next_step: 'Practice more.' },
    narration: { status: 'skipped', source: 'rules_feedback', script: 'Rules text', label: 'Rules feedback' },
  }, 1);
  assert.equal(next.polling, false);
  assert.equal(next.displaySource, 'Rules feedback');
  assert.equal(next.narrationStatus, 'skipped');
});
