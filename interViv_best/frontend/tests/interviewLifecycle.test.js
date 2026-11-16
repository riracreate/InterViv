import assert from 'node:assert/strict';
import test from 'node:test';

import {
  PHASES,
  canRequestManualFollowUp,
  followUpOutcomeFromPayload,
  inputsLocked,
  isShowingResult,
  pendingRoundFromResponse,
  phaseAfterSubmit,
  progressPercent,
  restoreFromSession,
  roundFieldsFromPayload,
  shouldPollNarration,
  technicalSecondsRemaining,
} from '../src/lib/interviewLifecycle.js';
import { interviewStateFromSession } from '../src/lib/accountOverview.js';

test('inputs unlock only while answering; results stay visible through activation', () => {
  assert.equal(inputsLocked(PHASES.ANSWERING), false);
  for (const phase of [PHASES.SUBMITTING, PHASES.REVIEWING, PHASES.ACTIVATING, PHASES.COMPLETED, PHASES.BLOCKED]) {
    assert.equal(inputsLocked(phase), true, phase);
  }
  assert.equal(isShowingResult(PHASES.REVIEWING), true);
  assert.equal(isShowingResult(PHASES.ACTIVATING), true);
  assert.equal(isShowingResult(PHASES.SUBMITTING), false);
});

test('submission response decides the phase; unscored rounds still enter review', () => {
  assert.equal(phaseAfterSubmit({ final_score: 0, session_complete: false }), PHASES.REVIEWING);
  assert.equal(phaseAfterSubmit({ final_score: null }), PHASES.REVIEWING);
  assert.equal(phaseAfterSubmit({ session_complete: true }), PHASES.COMPLETED);
  assert.equal(phaseAfterSubmit({ progression_blocked: true }), PHASES.BLOCKED);
});

test('the prepared next round is identity only; no prompt is applied before Next', () => {
  const pending = pendingRoundFromResponse({
    next_round: 3, next_round_type: 'sql', next_round_status: 'ready',
    next_block_category: 'sql', next_skill: 'SQL', next_question: null,
  });
  assert.deepEqual(pending, {
    round: 3, roundType: 'sql', blockCategory: 'sql', skill: 'SQL', difficulty: null, status: 'ready',
  });
  assert.equal(pendingRoundFromResponse({ next_round: 2, session_complete: true }), null);
  assert.equal(pendingRoundFromResponse({ next_round: 2, progression_blocked: true }), null);
  assert.equal(pendingRoundFromResponse({ next_round: null }), null);
});

test('activation payload maps to the opened round', () => {
  const fields = roundFieldsFromPayload({
    round: 2, question: 'Explain joins.', round_type: 'technical_short_answer',
    block_category: 'interview', difficulty: 'hard', skill: 'SQL',
    question_context: { id: 'q' }, config_json: { duration_seconds: 120 },
    expires_at: '2026-11-03T10:02:00+00:00', started_at: '2026-11-03T10:00:00+00:00',
  });
  assert.equal(fields.round, 2);
  assert.equal(fields.question, 'Explain joins.');
  assert.equal(fields.expiresAt, '2026-11-03T10:02:00+00:00');
  assert.equal(fields.startedAt, '2026-11-03T10:00:00+00:00');
});

test('refresh during review restores the submitted round, its result and the pending round', () => {
  const session = {
    session_id: 's1', status: 'active', total_rounds: 3, current_skill: 'DBMS',
    active_round: null, review_round: 1,
    round_history: [{
      round: 1, question: 'What is ACID?', round_type: 'technical_short_answer',
      status: 'submitted', final_score: 0, feedback: { next_step: 'Define atomicity.' },
      answer_text: 'my answer', elo_after: 1188,
    }],
    pending_round: { round: 2, round_type: 'mcq', status: 'ready', block_category: 'oa' },
  };
  const restored = restoreFromSession(session);
  assert.equal(restored.phase, PHASES.REVIEWING);
  assert.equal(restored.result.score, 0); // a scored zero stays zero
  assert.equal(restored.pendingRound.round, 2);

  const state = interviewStateFromSession(session);
  assert.equal(state.phase, PHASES.REVIEWING);
  assert.equal(state.round, 1);
  assert.equal(state.question, 'What is ACID?');
  assert.equal(state.answerText, 'my answer');
  assert.equal(state.currentScore, 0);
  assert.equal(state.currentFeedback, 'Define atomicity.');
  assert.equal(state.elo, 1188);
  assert.equal(state.pendingRound.roundType, 'mcq');
});

test('refresh during an open round restores answering with the server deadline', () => {
  const state = interviewStateFromSession({
    session_id: 's2', status: 'active', total_rounds: 2,
    active_round: {
      round: 2, status: 'in_progress', question: 'Q2', round_type: 'technical_short_answer',
      started_at: '2026-11-03T10:00:00+00:00', expires_at: null, elo_before: 1210,
    },
    round_history: [{ round: 1, status: 'submitted', final_score: 55 }],
  });
  assert.equal(state.phase, PHASES.ANSWERING);
  assert.equal(state.round, 2);
  assert.equal(state.started_at, '2026-11-03T10:00:00+00:00');
  assert.equal(state.currentScore, undefined);
  assert.equal(state.elo, 1210);
});

test('technical timer counts from activation and never resets on refresh', () => {
  const startedAt = '2026-11-03T10:00:00+00:00';
  const now = Date.parse('2026-11-03T10:00:45Z');
  assert.equal(technicalSecondsRemaining({ startedAt, nowMs: now }), 75);
  assert.equal(technicalSecondsRemaining({ startedAt, nowMs: now + 600000 }), 0);
  // A server deadline wins over the advisory budget.
  assert.equal(technicalSecondsRemaining({
    startedAt, expiresAt: '2026-11-03T10:05:00Z', nowMs: now,
  }), 255);
  assert.equal(technicalSecondsRemaining({ nowMs: now }), null);
});

test('narration is polled only while the server reports a pending job', () => {
  assert.equal(shouldPollNarration('queued'), true);
  assert.equal(shouldPollNarration('processing'), true);
  for (const status of ['skipped', 'done', 'failed', 'unavailable', null, undefined]) {
    assert.equal(shouldPollNarration(status), false);
  }
});

test('header progress counts the reviewed round as answered', () => {
  assert.equal(progressPercent({ round: 1, totalRounds: 4, phase: PHASES.ANSWERING }), 0);
  assert.equal(progressPercent({ round: 1, totalRounds: 4, phase: PHASES.REVIEWING }), 25);
  assert.equal(progressPercent({ round: 4, totalRounds: 4, phase: PHASES.COMPLETED }), 100);
});

test('S1b-2: activation and history carry isFollowUp, followUpParentRound, and concept outcome without percentage', () => {
  const opened = roundFieldsFromPayload({
    round: 2,
    question: 'Follow-up: Why can blocking I/O overlap under the GIL?',
    round_type: 'technical_short_answer',
    difficulty: 'medium',
    skill: 'Python',
    is_follow_up: true,
    follow_up_parent_round: 1,
    config_json: { is_follow_up: true, follow_up_parent_round: 1 },
  });
  assert.equal(opened.isFollowUp, true);
  assert.equal(opened.followUpParentRound, 1);

  const outcome = followUpOutcomeFromPayload({
    follow_up_outcome: {
      targets_concept: 'io_release',
      concept_label: 'Blocking I/O syscalls release the lock',
      demonstrated: true,
      status: 'demonstrated',
    },
  });
  assert.equal(outcome.concept_label, 'Blocking I/O syscalls release the lock');
  assert.equal(outcome.demonstrated, true);

  const restored = restoreFromSession({
    session_id: 's-fu',
    status: 'active',
    total_rounds: 3,
    review_round: 2,
    round_history: [{
      round: 2,
      round_type: 'technical_short_answer',
      status: 'submitted',
      is_follow_up: true,
      follow_up_parent_round: 1,
      final_score: null,
      feedback: {
        content: ['Blocking I/O syscalls release the lock: demonstrated in your follow-up answer.'],
        next_step: 'Continue with the remaining rounds.',
      },
      follow_up_outcome: outcome,
    }],
  });
  assert.equal(restored.current.isFollowUp, true);
  assert.equal(restored.current.followUpParentRound, 1);
  assert.equal(restored.result.score, null);
  assert.equal(restored.result.followUpOutcome.demonstrated, true);
  assert.match(restored.result.feedback, /demonstrated/i);

  const state = interviewStateFromSession({
    session_id: 's-fu2',
    status: 'active',
    total_rounds: 3,
    active_round: {
      round: 2,
      status: 'in_progress',
      question: 'Follow-up Q?',
      round_type: 'technical_short_answer',
      is_follow_up: true,
      follow_up_parent_round: 1,
    },
  });
  assert.equal(state.isFollowUp, true);
  assert.equal(state.followUpParentRound, 1);
});

test('S1b-2: manual follow-up CTA is suppressed when inline follow-up is scheduled or on any follow-up round', () => {
  assert.equal(
    canRequestManualFollowUp({
      roundType: 'technical_short_answer',
      phase: PHASES.REVIEWING,
      followUpNote: '',
      followUpScheduled: false,
      isFollowUp: false,
    }),
    true,
  );
  assert.equal(
    canRequestManualFollowUp({
      roundType: 'technical_short_answer',
      phase: PHASES.REVIEWING,
      followUpNote: '',
      followUpScheduled: true,
      isFollowUp: false,
    }),
    false,
  );
  assert.equal(
    canRequestManualFollowUp({
      roundType: 'technical_short_answer',
      phase: PHASES.REVIEWING,
      followUpNote: '',
      followUpScheduled: false,
      isFollowUp: true,
    }),
    false,
  );
});
