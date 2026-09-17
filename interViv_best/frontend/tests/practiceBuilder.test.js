import assert from 'node:assert/strict';
import test from 'node:test';

import {
  PRACTICE_MODES,
  mapBlocksToStartPayload,
  mapCustomBuilderToStartPayload,
  mapFullInterviewToStartPayload,
  mapOaSqlToStartPayload,
  mapProblemItemToStartPayload,
  mapStandaloneToStartPayload,
  isAvailabilityMessage,
  multiSkillTopicNote,
  payloadHasInterview,
  reconcileTopic,
  sharedTopicsForSkills,
  summarizeAvailability,
  validateBuilderBlocks,
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

test('payloadHasInterview detects interview rounds in blocks and legacy payloads', () => {
  assert.equal(payloadHasInterview({ blocks: [{ round_type: 'mcq', category: 'oa' }] }), false);
  assert.equal(payloadHasInterview({ blocks: [{ round_type: 'sql', category: 'sql' }] }), false);
  assert.equal(
    payloadHasInterview({ blocks: [{ round_type: 'technical_short_answer', category: 'interview' }] }),
    true
  );
  assert.equal(
    payloadHasInterview({ blocks: [{ round_type: 'mcq' }, { round_type: 'technical_short_answer' }] }),
    true
  );
  assert.equal(payloadHasInterview({ round_type: 'technical_short_answer' }), true);
  assert.equal(payloadHasInterview({ round_type: 'mcq', round_plan: ['mcq', 'sql'] }), false);
  assert.equal(
    payloadHasInterview({ round_type: 'mcq', round_plan: ['mcq', 'technical_short_answer'] }),
    true
  );
  assert.equal(payloadHasInterview(null), false);
});

test('summarizeAvailability returns null when everything is available', () => {
  assert.equal(summarizeAvailability({ available: true, reviewed_only: false, blocks: [] }), null);
  assert.equal(summarizeAvailability(null), null);
});

test('summarizeAvailability names the blocked block and skill', () => {
  const summary = summarizeAvailability({
    reviewed_only: true,
    available: false,
    blocks: [
      { position: 1, category: 'interview', skills: ['DBMS'], available: true, reason: null },
      {
        position: 2, category: 'interview', skills: ['OOP'], available: false,
        reason: "No reviewed question bundles are available for skill 'OOP'.",
      },
    ],
  });
  assert.equal(summary.title, 'Assessed practice is unavailable');
  assert.equal(summary.reviewedOnly, true);
  assert.equal(summary.reasons.length, 1);
  assert.match(summary.reasons[0], /Block 2/);
  assert.match(summary.reasons[0], /OOP/);
});

const TOPIC_METADATA = {
  DBMS: ['indexes', 'normalization', 'transactions'],
  OOP: ['pillars', 'solid'],
};

test('sharedTopicsForSkills intersects per-skill topics case-insensitively', () => {
  assert.deepEqual(sharedTopicsForSkills(['DBMS'], TOPIC_METADATA), ['indexes', 'normalization', 'transactions']);
  assert.deepEqual(sharedTopicsForSkills(['dbms'], TOPIC_METADATA), ['indexes', 'normalization', 'transactions']);
  // One block-level topic must suit every skill: no shared topic means
  // no options. A union here would over-promise and fail strict start.
  assert.deepEqual(sharedTopicsForSkills(['DBMS', 'OOP'], TOPIC_METADATA), []);
  assert.deepEqual(sharedTopicsForSkills(['Unknown Skill'], TOPIC_METADATA), []);
  assert.deepEqual(sharedTopicsForSkills([], TOPIC_METADATA), []);
  assert.deepEqual(sharedTopicsForSkills(['DBMS'], null), []);
  assert.deepEqual(sharedTopicsForSkills(['DBMS'], {}), []);
});

test('sharedTopicsForSkills offers topics shared by every skill', () => {
  const metadata = {
    DBMS: ['design', 'indexes', 'normalization'],
    OOP: ['design', 'solid'],
  };
  assert.deepEqual(sharedTopicsForSkills(['DBMS', 'OOP'], metadata), ['design']);
  assert.deepEqual(
    sharedTopicsForSkills(['DBMS'], metadata),
    ['design', 'indexes', 'normalization']
  );
});

test('multiSkillTopicNote explains empty shared offers for multi-skill blocks', () => {
  assert.equal(multiSkillTopicNote(['DBMS'], TOPIC_METADATA, true), null);
  assert.equal(multiSkillTopicNote(['DBMS', 'OOP'], TOPIC_METADATA, false), null);
  const shared = { DBMS: ['design'], OOP: ['design'] };
  assert.equal(multiSkillTopicNote(['DBMS', 'OOP'], shared, true), null);
  const note = multiSkillTopicNote(['DBMS', 'OOP'], TOPIC_METADATA, true);
  assert.match(note, /DBMS and OOP/);
  assert.match(note, /Split into separate blocks/);
});

test('reconcileTopic keeps offered topics and clears the rest', () => {
  assert.deepEqual(reconcileTopic('normalization', ['DBMS'], TOPIC_METADATA), { topic: 'normalization', cleared: false });
  assert.deepEqual(reconcileTopic('normalization', ['OOP'], TOPIC_METADATA), { topic: '', cleared: true });
  assert.deepEqual(reconcileTopic('', ['DBMS'], TOPIC_METADATA), { topic: '', cleared: false });
  assert.deepEqual(reconcileTopic('  ', ['DBMS'], TOPIC_METADATA), { topic: '', cleared: false });
  // Unknown skills offer nothing: a stale selection clears visibly.
  assert.deepEqual(reconcileTopic('normalization', ['Unknown'], TOPIC_METADATA), { topic: '', cleared: true });
});

test('standalone interview maps an explicit topic and omits unrestricted', () => {
  const { error, payload } = mapStandaloneToStartPayload('interview', {
    skills: ['DBMS'], count: 2, topic: 'normalization',
  });
  assert.equal(error, undefined);
  assert.equal(payload.blocks[0].topic, 'normalization');
  const unrestricted = mapStandaloneToStartPayload('interview', { skills: ['DBMS'], count: 2 });
  assert.equal(unrestricted.error, undefined);
  assert.ok(!('topic' in unrestricted.payload.blocks[0]));
  const blank = mapStandaloneToStartPayload('interview', { skills: ['DBMS'], count: 2, topic: '  ' });
  assert.ok(!('topic' in blank.payload.blocks[0]));
});

test('repeated interview blocks keep independent topics', () => {
  const { error, payload } = mapBlocksToStartPayload([
    { id: 'b1', round_type: 'technical_short_answer', category: 'interview', skills: ['DBMS'], count: 1, topic: 'normalization' },
    { id: 'b2', round_type: 'technical_short_answer', category: 'interview', skills: ['DBMS'], count: 1, topic: 'indexes' },
  ]);
  assert.equal(error, undefined);
  assert.equal(payload.blocks[0].topic, 'normalization');
  assert.equal(payload.blocks[1].topic, 'indexes');
});

test('isAvailabilityMessage separates content shortages from malformed requests', () => {
  assert.equal(isAvailabilityMessage('No reviewed question bundles are available.'), true);
  assert.equal(isAvailabilityMessage('Not enough OOP MCQ questions available: found 10, need 15.'), true);
  assert.equal(isAvailabilityMessage('Unknown SQL problem: xyz.'), true);
  assert.equal(isAvailabilityMessage('Block 1: count must be 1–30.'), false);
  assert.equal(isAvailabilityMessage('At most 10 blocks are allowed.'), false);
  assert.equal(isAvailabilityMessage(''), false);
  assert.equal(isAvailabilityMessage(null), false);
});

test('builder validation scopes topics to interview blocks', () => {
  const interview = { round_type: 'technical_short_answer', category: 'interview', skills: ['DBMS'], count: 1 };
  assert.equal(validateBuilderBlocks([{ ...interview }]), null);
  assert.equal(validateBuilderBlocks([{ ...interview, topic: 'normalization' }]), null);
  assert.match(
    validateBuilderBlocks([{ ...interview, topic: 'x'.repeat(121) }]),
    /1–120/
  );
  assert.match(
    validateBuilderBlocks([{
      round_type: 'mcq', category: 'oa', skills: ['DBMS'], count: 2, duration_minutes: 10, topic: 'normalization',
    }]),
    /only supported for interview/
  );
});
