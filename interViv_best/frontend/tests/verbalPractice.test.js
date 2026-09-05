import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildVerbalPracticePayload,
  VERBAL_PRACTICE_CONFIG,
  formatMCQSubmission,
} from '../src/lib/roundContractHelpers.js';

test('verbal payload matches the standalone server contract', () => {
  const payload = buildVerbalPracticePayload('cand-1');
  assert.equal(payload.candidate_id, 'cand-1');
  assert.deepEqual(payload.skills, ['Verbal Ability']);
  assert.equal(payload.rounds_per_skill, 1);
  assert.equal(payload.round_type, 'mcq');
  assert.deepEqual(payload.round_config, {
    count: 15,
    duration_minutes: 20,
    negative_marking: 0.25,
  });
});

test('verbal payload defaults to an empty candidate id', () => {
  assert.equal(buildVerbalPracticePayload().candidate_id, '');
  assert.equal(buildVerbalPracticePayload(null).candidate_id, '');
});

test('verbal config stays in sync with the bank and policy', () => {
  assert.equal(VERBAL_PRACTICE_CONFIG.skill, 'Verbal Ability');
  assert.equal(VERBAL_PRACTICE_CONFIG.roundType, 'mcq');
  assert.equal(VERBAL_PRACTICE_CONFIG.roundsPerSkill, 1);
  assert.equal(VERBAL_PRACTICE_CONFIG.count, 15);
  assert.equal(VERBAL_PRACTICE_CONFIG.durationMinutes, 20);
  assert.equal(VERBAL_PRACTICE_CONFIG.negativeMarking, 0.25);
});

test('verbal answers reuse the canonical MCQ submission format', () => {
  const questions = [{ id: 'mcq_verbal_001' }, { id: 'mcq_verbal_002' }];
  const formatted = formatMCQSubmission(questions, { 'mcq_verbal_001': 'b' });
  assert.deepEqual(formatted, [
    { question_id: 'mcq_verbal_001', selected_option_ids: ['b'] },
    { question_id: 'mcq_verbal_002', selected_option_ids: [] },
  ]);
});
