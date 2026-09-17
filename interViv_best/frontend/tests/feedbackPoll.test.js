import test from 'node:test';
import assert from 'node:assert/strict';
import {
  applyFeedbackPollResult,
  clearFeedbackPollInterval,
  isFeedbackPollTickCurrent,
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

test('tick is rejected after unmount clears expected round', () => {
  let expectedRound = 1;
  assert.equal(isFeedbackPollTickCurrent(expectedRound, 1), true);
  // Unmount / navigate away: clear expected round so late ticks no-op.
  expectedRound = null;
  assert.equal(isFeedbackPollTickCurrent(expectedRound, 1), false);
});

test('tick is rejected after advancing to another round', () => {
  let expectedRound = 1;
  assert.equal(isFeedbackPollTickCurrent(expectedRound, 1), true);
  expectedRound = 2;
  assert.equal(isFeedbackPollTickCurrent(expectedRound, 1), false);
  assert.equal(isFeedbackPollTickCurrent(expectedRound, 2), true);
});

test('clearFeedbackPollInterval cancels scheduled polling', () => {
  const cleared = [];
  const id = 42;
  const next = clearFeedbackPollInterval(id, (value) => cleared.push(value));
  assert.equal(next, null);
  assert.deepEqual(cleared, [42]);
  assert.equal(clearFeedbackPollInterval(null, (value) => cleared.push(value)), null);
  assert.deepEqual(cleared, [42]);
});

test('terminal narration clears polling flag so UI can stop the interval', () => {
  const state = {
    displayFeedback: 'Rules',
    narrationStatus: 'processing',
    polling: true,
  };
  const done = applyFeedbackPollResult(state, {
    round: 3,
    feedback: { content: ['Rules'] },
    narration: { status: 'done', script: 'AI text', source: 'provider', label: 'AI narration' },
  }, 3);
  assert.equal(done.polling, false);
  assert.equal(shouldKeepPollingNarration(done.narrationStatus), false);

  const failed = applyFeedbackPollResult(state, {
    round: 3,
    feedback: { content: ['Rules'] },
    narration: { status: 'failed' },
  }, 3);
  assert.equal(failed.polling, false);
});
