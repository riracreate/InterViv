import assert from 'node:assert/strict';
import test from 'node:test';

import {
  PRACTICE_MODES,
  mapCustomBuilderToStartPayload,
  mapFullInterviewToStartPayload,
  mapOaSqlToStartPayload,
  mapProblemItemToStartPayload,
} from '../src/lib/practiceBuilder.js';

test('Practice hub exposes four modes with honest OA+SQL labeling', () => {
  assert.equal(PRACTICE_MODES.length, 4);
  const ids = PRACTICE_MODES.map((m) => m.id).sort();
  assert.deepEqual(ids, ['custom', 'full', 'oa_sql', 'problems']);
  const oa = PRACTICE_MODES.find((m) => m.id === 'oa_sql');
  assert.match(oa.title, /OA \+ SQL/);
  assert.doesNotMatch(oa.title, /coding/i);
  assert.match(oa.blurb, /not a general coding judge/i);
});

test('custom builder maps free-text+MCQ+SQL to round_plan payload', () => {
  const { error, payload } = mapCustomBuilderToStartPayload({
    skills: ['DBMS', 'OOP'],
    totalMinutes: 40,
    questionCount: 5,
    includeTechnical: true,
    includeMcq: true,
    includeSql: true,
    targetCompanyId: 'tcs',
    targetRoleId: 'sde-intern',
    mode: 'text',
  });
  assert.equal(error, undefined);
  assert.ok(payload);
  assert.deepEqual(payload.skills, ['DBMS', 'OOP']);
  assert.equal(payload.round_config.duration_minutes, 40);
  assert.ok(payload.round_plan.includes('technical_short_answer'));
  assert.ok(payload.round_plan.includes('mcq'));
  assert.ok(payload.round_plan.includes('sql'));
  assert.equal(payload.round_type, payload.round_plan[0]);
  // 5 questions with 2 blocks → 3 technical + mcq + sql
  assert.equal(payload.round_plan.filter((t) => t === 'technical_short_answer').length, 3);
});

test('custom builder rejects empty mix and voice-only mode', () => {
  const empty = mapCustomBuilderToStartPayload({
    skills: ['DBMS'],
    totalMinutes: 30,
    questionCount: 3,
    includeTechnical: false,
    includeMcq: false,
    includeSql: false,
  });
  assert.match(empty.error, /at least one round type/i);

  const voice = mapCustomBuilderToStartPayload({
    skills: ['DBMS'],
    totalMinutes: 30,
    questionCount: 3,
    includeTechnical: true,
    mode: 'voice',
  });
  assert.match(voice.error, /not a separate session type/i);
});

test('OA+SQL mapper builds mcq-then-sql plan', () => {
  const { error, payload } = mapOaSqlToStartPayload({
    skills: ['DBMS'],
    durationMinutes: 45,
    mcqCount: 8,
    sqlCases: 2,
  });
  assert.equal(error, undefined);
  assert.deepEqual(payload.round_plan, ['mcq', 'sql', 'sql']);
  assert.equal(payload.round_type, 'mcq');
  assert.equal(payload.round_config.count, 8);
});

test('full interview reuses technical start fields', () => {
  const { payload } = mapFullInterviewToStartPayload({
    skills: ['DSA', 'OOP'],
    roundsPerSkill: 2,
    targetRoleId: 'sde',
  });
  assert.equal(payload.round_type, 'technical_short_answer');
  assert.equal(payload.rounds_per_skill, 2);
  assert.equal(payload.round_plan, undefined);
});

test('problem item mapper pins question_ids / problem_id', () => {
  const mcq = mapProblemItemToStartPayload(
    { id: 'mcq_dbms_001', type: 'mcq', skill: 'DBMS' },
    {}
  );
  assert.deepEqual(mcq.payload.round_config.question_ids, ['mcq_dbms_001']);
  const sql = mapProblemItemToStartPayload(
    { id: 'sql_prob_001', type: 'sql' },
    {}
  );
  assert.equal(sql.payload.round_type, 'sql');
  assert.equal(sql.payload.round_config.problem_id, 'sql_prob_001');
});
