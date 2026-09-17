import test from 'node:test';
import assert from 'node:assert/strict';
import { mapMcqReview, formatMcqAnswerSummary } from '../src/lib/mcqReviewMapping.js';
import { blockUsesInterviewMedia } from '../src/lib/interviewMedia.js';

test('MCQ review hides keys when policy is none', () => {
  const review = mapMcqReview({
    review_policy: 'none',
    mcq_questions: [{
      id: 'q1',
      stem: 'Pick one',
      options: [{ id: 'a', text: 'Alpha' }, { id: 'b', text: 'Beta' }],
      correct_option_ids: ['a'],
      explanation: 'SECRET',
    }],
    artifact_json: {
      questions: [{ question_id: 'q1', selected_option_ids: ['b'], is_correct: false }],
    },
  }, { assessmentCompleted: true });
  assert.equal(review.keysVisible, false);
  assert.deepEqual(review.items[0].correctIds, []);
  assert.equal(review.items[0].explanation, null);
  assert.deepEqual(review.items[0].selectedLabels, ['Beta']);
  assert.doesNotMatch(formatMcqAnswerSummary(review), /SECRET|Alpha/);
});

test('MCQ review shows keys only for completed after_session', () => {
  const base = {
    review_policy: 'after_session',
    mcq_questions: [{
      id: 'q1',
      stem: 'Pick one',
      options: [{ id: 'a', text: 'Alpha' }, { id: 'b', text: 'Beta' }],
      correct_option_ids: ['a'],
      explanation: 'Because Alpha.',
    }],
    artifact_json: {
      questions: [{ question_id: 'q1', selected_option_ids: ['a'], is_correct: true }],
    },
  };
  const blocked = mapMcqReview(base, { assessmentCompleted: false });
  assert.equal(blocked.keysVisible, false);
  assert.equal(blocked.items[0].explanation, null);

  const done = mapMcqReview(base, { assessmentCompleted: true });
  assert.equal(done.keysVisible, true);
  assert.deepEqual(done.items[0].correctLabels, ['Alpha']);
  assert.equal(done.items[0].explanation, 'Because Alpha.');
});

test('interview media gate disables camera for MCQ and SQL', () => {
  assert.equal(blockUsesInterviewMedia('sql', 'sql'), false);
  assert.equal(blockUsesInterviewMedia(null, 'sql'), false);
  assert.equal(blockUsesInterviewMedia(null, 'mcq'), false);
  assert.equal(blockUsesInterviewMedia('verbal', 'mcq'), false);
  assert.equal(blockUsesInterviewMedia('interview', 'technical_short_answer'), true);
  assert.equal(blockUsesInterviewMedia(null, 'technical_short_answer'), true);
});
