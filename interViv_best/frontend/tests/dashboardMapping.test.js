import test from 'node:test';
import assert from 'node:assert/strict';
import {
  blockDisplayLabel,
  blockMetricLabel,
  buildReviewSummaryProps,
  eligibilityPracticeHint,
  eligibilityPracticeLabel,
  isMultiBlockSession,
  mapRealDataToDashboard,
  scoreAccent,
} from '../src/lib/dashboardMapping.js';

const SAMPLE_SESSION = {
  started_at: '2026-09-01T10:00:00Z',
  skill: 'DBMS',
  skills: ['DBMS', 'Python'],
  total_rounds: 3,
  averages: { final_score: 62.4, nlp_score: 58, kg_score: 55 },
  elo_progression: [1200, 1215, 1230],
  difficulty_progression: ['easy', 'medium', 'hard'],
  topic_scores: { DBMS: 48, Python: 76 },
  breakdown: { Good: 1, Average: 1, Poor: 1 },
  next_step: 'Review indexing before the next mock.',
  rounds: [
    {
      final_score: 40,
      answer_text: 'Indexes speed up lookups on large tables.',
      difficulty: 'easy',
      question: 'What is an index?',
      skill: 'DBMS',
      guard_applied: 'too_short',
      feedback: { next_step: 'Add B-tree detail.' },
    },
    {
      final_score: 70,
      answer_text: 'Python uses reference counting plus a cyclic garbage collector for memory.',
      difficulty: 'medium',
      question: 'How does Python manage memory?',
      skill: 'Python',
      feedback: { content: ['Solid coverage.'] },
    },
    {
      final_score: 77,
      answer_text:
        'A foreign key references a primary key in another table and enforces referential integrity across joins.',
      difficulty: 'hard',
      question: 'What is a foreign key?',
      skill: 'DBMS',
      scoring_breakdown: { guard_applied: null },
    },
  ],
};

test('mapRealDataToDashboard maps averages, rounds, and performance', () => {
  const mapped = mapRealDataToDashboard(SAMPLE_SESSION);
  assert.equal(mapped.overall.score, 62);
  assert.equal(mapped.overall.gradeLabel, 'Good');
  assert.equal(mapped.rounds.length, 3);
  assert.equal(mapped.rounds[0].difficulty, 'Easy');
  assert.equal(mapped.performance.finalRating, 1230);
  assert.equal(mapped.performance.difficulty[2].value, 60);
  assert.ok(mapped.reviewSummary);
});

test('buildReviewSummaryProps derives guards, words, and priority skill from API fields', () => {
  const mapped = mapRealDataToDashboard(SAMPLE_SESSION);
  const summary = buildReviewSummaryProps(SAMPLE_SESSION, mapped);
  assert.equal(summary.completedRounds, 3);
  assert.equal(summary.totalRounds, 3);
  assert.equal(summary.guardCount, 1);
  assert.ok(summary.averageWords > 0);
  assert.equal(summary.scoreRange, 37);
  assert.equal(summary.prioritySkills[0].skill, 'DBMS');
  assert.equal(summary.priorityRound.id, '1');
  assert.match(summary.nextStep, /indexing/i);
});

test('scoreAccent returns shared tone classes by band', () => {
  assert.match(scoreAccent(90).text, /cyan/);
  assert.match(scoreAccent(40).text, /fuchsia/);
});

test('empty session still yields a safe dashboard shape', () => {
  const mapped = mapRealDataToDashboard({ rounds: [], averages: {} });
  // Phase AB (Z-F02): no measured average is "not measured", never a zero.
  assert.equal(mapped.overall.score, null);
  assert.equal(mapped.overall.gradeLabel, 'Not measured');
  assert.equal(mapped.rounds.length, 0);
  assert.equal(mapped.reviewSummary.completedRounds, 0);
  assert.equal(mapped.reviewSummary.guardCount, 0);
});

const MIXED_SESSION = {
  started_at: '2026-09-01T10:00:00Z',
  skills: ['DBMS'],
  total_rounds: 3,
  averages: { final_score: 66.67, nlp_score: 0, kg_score: 0 },
  block_plan: [
    { id: 'b1', position: 1, category: 'oa' },
    { id: 'b2', position: 2, category: 'sql' },
    { id: 'b3', position: 3, category: 'interview' },
  ],
  block_results: [
    {
      block_id: 'b1', block_position: 1, block_category: 'oa', round_types: ['mcq'],
      skills: ['DBMS'], rounds: 1, attempted_rounds: 1, scored_rounds: 1,
      unscored_rounds: 0, measured_rounds: 1, self_reported_rounds: 0,
      average_score: 80.0, self_reported_average: null, scoring_modes: ['mcq'],
      suggestion: null,
    },
    {
      block_id: 'b2', block_position: 2, block_category: 'sql', round_types: ['sql'],
      skills: ['SQL'], rounds: 1, attempted_rounds: 1, scored_rounds: 1,
      unscored_rounds: 0, measured_rounds: 1, self_reported_rounds: 0,
      average_score: 100.0, self_reported_average: null, scoring_modes: ['sql_execution'],
      suggestion: null,
    },
    {
      block_id: 'b3', block_position: 3, block_category: 'interview', round_types: ['technical_short_answer'],
      skills: ['DBMS'], rounds: 1, attempted_rounds: 1, scored_rounds: 1,
      unscored_rounds: 0, measured_rounds: 1, self_reported_rounds: 0,
      average_score: 20.0, self_reported_average: null, scoring_modes: ['nlp_scorer'],
      suggestion: { text: 'Round 3 scored 20.0 on DBMS; retry DBMS misses next.' },
    },
  ],
  rounds: [
    { final_score: 80, answer_text: '[{"question_id":"q1"}]', question: 'Multiple Choice Assessment' },
    { final_score: 100, answer_text: 'SELECT 1', question: 'SQL problem' },
    { final_score: 20, answer_text: 'A short answer.', question: 'Explain X.' },
  ],
  coverage: { scored_rounds: 3, unscored_rounds: [] },
  breakdown: { Good: 2, Average: 0, Poor: 1 },
};

test('block metric labels stay per-category, never blended', () => {
  assert.equal(blockMetricLabel({ block_category: 'oa', round_types: ['mcq'] }), 'MCQ accuracy');
  assert.equal(blockMetricLabel({ block_category: 'verbal', round_types: ['mcq'] }), 'MCQ accuracy');
  assert.equal(blockMetricLabel({ block_category: 'sql', round_types: ['sql'] }), 'SQL correctness');
  assert.equal(blockMetricLabel({ block_category: 'interview', round_types: ['technical_short_answer'] }), 'Interview score');
  assert.equal(blockMetricLabel({ block_category: 'system_design', round_types: ['system_design'] }), 'Self-reported score');
  assert.equal(blockDisplayLabel({ block_category: 'sql', block_position: 2 }, 1), 'Block 2 · SQL');
});

test('legacy sessions without a block plan are never multi-block', () => {
  assert.equal(isMultiBlockSession(SAMPLE_SESSION), false);
  assert.equal(isMultiBlockSession({ block_plan: [{ id: 'b1' }] }), false);
  assert.equal(isMultiBlockSession(MIXED_SESSION), true);
});

test('mixed session shows no blended overall percentage', () => {
  const mapped = mapRealDataToDashboard(MIXED_SESSION);
  assert.equal(mapped.blended, true);
  assert.equal(mapped.multiBlock, true);
  assert.equal(mapped.overall.score, null);
  assert.equal(mapped.overall.gradeLabel, 'Mixed session');
  assert.match(mapped.overall.deltaLabel, /per-block/i);
  // Average-derived visuals are suppressed; per-round evidence stays.
  assert.deepEqual(mapped.layers, []);
  assert.deepEqual(mapped.radar, []);
  assert.equal(mapped.rounds.length, 3);
  assert.match(mapped.feedbackCards[0].body, /not blended/i);
  assert.equal(mapped.reviewSummary.overallScore, null);
  assert.equal(mapped.reviewSummary.blended, true);
});

test('mixed session maps each block with its own metric and counts', () => {
  const mapped = mapRealDataToDashboard(MIXED_SESSION);
  assert.equal(mapped.blocks.length, 3);
  const [oa, sql, interview] = mapped.blocks;
  assert.equal(oa.title, 'Block 1 · OA');
  assert.equal(oa.metric, 'MCQ accuracy');
  assert.equal(oa.average, 80);
  assert.equal(sql.metric, 'SQL correctness');
  assert.equal(sql.average, 100);
  assert.equal(interview.metric, 'Interview score');
  assert.equal(interview.average, 20);
  assert.match(interview.suggestion, /Round 3/);
  for (const block of mapped.blocks) {
    assert.equal(block.attempted, 1);
    assert.equal(block.scored, 1);
    assert.equal(block.unscored, 0);
  }
});

test('single-block session keeps its historical overall rendering', () => {
  const session = {
    ...SAMPLE_SESSION,
    block_plan: [{ id: 'b1', position: 1, category: 'interview' }],
    block_results: [
      {
        block_id: 'b1', block_position: 1, block_category: 'interview',
        round_types: ['technical_short_answer'], skills: ['DBMS', 'Python'],
        rounds: 3, attempted_rounds: 3, scored_rounds: 3, unscored_rounds: 0,
        measured_rounds: 3, self_reported_rounds: 0, average_score: 62.4,
        self_reported_average: null, scoring_modes: ['nlp_scorer'], suggestion: null,
      },
    ],
  };
  const mapped = mapRealDataToDashboard(session);
  assert.equal(mapped.blended, false);
  assert.equal(mapped.multiBlock, false);
  assert.equal(mapped.overall.score, 62);
  assert.equal(mapped.overall.gradeLabel, 'Good');
  // Only measured components: layer 1 and 2 averages exist; no derived layer 3.
  assert.deepEqual(mapped.layers.map((l) => [l.label, l.score]), [['Content coverage', 58], ['Concept depth', 55]]);
  // Radar comes from real topic scores only — no padded "Clarity/Structure/Depth".
  assert.deepEqual(mapped.radar, [{ skill: 'DBMS', value: 48 }, { skill: 'Python', value: 76 }]);
  assert.ok(!mapped.feedbackCards.some((c) => /C4/.test(c.title)));
  assert.match(mapped.session.title, /Interview session/);
  assert.equal(mapped.blocks.length, 1);
  assert.equal(mapped.blocks[0].average, 62.4);
});

test('per-block zero is a score and null is no measurement', () => {
  const session = {
    ...MIXED_SESSION,
    block_results: MIXED_SESSION.block_results.map((b, i) => ({
      ...b,
      average_score: i === 0 ? 0.0 : null,
      measured_rounds: i === 0 ? 1 : 0,
      scored_rounds: i === 0 ? 1 : 0,
      unscored_rounds: i === 0 ? 0 : 1,
      attempted_rounds: i === 0 ? 1 : 0,
    })),
  };
  const mapped = mapRealDataToDashboard(session);
  // Only one measured block: the average is pure, not blended.
  assert.equal(mapped.blended, false);
  assert.equal(mapped.blocks[0].average, 0.0);
  assert.equal(mapped.blocks[1].average, null);
  assert.equal(mapped.blocks[1].unscored, 1);
  assert.equal(mapped.blocks[1].attempted, 0);
});


test('missing measurements are omitted, never derived from the average', () => {
  const session = {
    ...SAMPLE_SESSION,
    averages: { final_score: 70 },  // no layer averages recorded
    topic_scores: {},
  };
  const mapped = mapRealDataToDashboard(session);
  assert.equal(mapped.overall.score, 70);
  assert.deepEqual(mapped.layers, []);
  assert.deepEqual(mapped.radar, []);
  assert.ok(!mapped.highlights.weaknesses.some((w) => w.title === 'Push for depth'));
});

const UNREVIEWED_HINT =
  'Auto-checked question — feedback is shown for practice; not counted toward readiness or Elo.';

test('eligibilityPracticeLabel and eligibilityPracticeHint label unreviewed_content practice distinctly', () => {
  const unreviewed = {
    assessment_eligibility: 'excluded',
    eligibility_exclusion_reasons: ['unreviewed_content'],
    is_follow_up: false,
    assisted: false,
  };
  assert.equal(eligibilityPracticeLabel(unreviewed), 'Practice, not scored');
  assert.equal(eligibilityPracticeHint(unreviewed), UNREVIEWED_HINT);

  assert.equal(
    eligibilityPracticeLabel({ ...unreviewed, is_follow_up: true }),
    'Follow-up',
  );
  assert.equal(eligibilityPracticeHint({ ...unreviewed, is_follow_up: true }), null);

  assert.equal(
    eligibilityPracticeLabel({
      ...unreviewed,
      eligibility_exclusion_reasons: ['unreviewed_content', 'follow_up'],
    }),
    'Follow-up',
  );
  assert.equal(
    eligibilityPracticeLabel({
      ...unreviewed,
      eligibility_exclusion_reasons: ['unreviewed_content', 'same_item_retry'],
    }),
    'Repeated practice',
  );
  assert.equal(
    eligibilityPracticeHint({
      ...unreviewed,
      eligibility_exclusion_reasons: ['unreviewed_content', 'same_item_retry'],
    }),
    null,
  );

  assert.equal(eligibilityPracticeLabel({ ...unreviewed, assisted: true }), 'Practiced with help');
  assert.equal(eligibilityPracticeHint({ ...unreviewed, assisted: true }), null);

  for (const exposureReason of ['teaching_exposure', 'related_topic_exposure', 'coarse_topic_scope']) {
    const exposed = {
      ...unreviewed,
      eligibility_exclusion_reasons: ['unreviewed_content', exposureReason],
    };
    assert.equal(eligibilityPracticeLabel(exposed), 'Practiced with help', exposureReason);
    assert.equal(eligibilityPracticeHint(exposed), null, exposureReason);
  }

  assert.equal(eligibilityPracticeLabel({ assessment_eligibility: 'eligible' }), 'Assessment');
  assert.equal(eligibilityPracticeHint({ assessment_eligibility: 'eligible' }), null);
  assert.equal(eligibilityPracticeLabel({ assessment_eligibility: 'unknown' }), 'Unscored practice');
  assert.equal(eligibilityPracticeHint({ assessment_eligibility: 'unknown' }), null);
  assert.equal(eligibilityPracticeLabel({ assessment_eligibility: 'legacy_unknown' }), 'Unscored practice');
  assert.equal(eligibilityPracticeLabel({ assisted: true }), 'Practiced with help');
  assert.equal(eligibilityPracticeLabel({}), null);
  assert.equal(eligibilityPracticeHint({}), null);
});

test('mapRealDataToDashboard exposes practiceLabel and practiceHint on mapped rounds', () => {
  const mapped = mapRealDataToDashboard({
    started_at: '2026-09-01T10:00:00Z',
    skills: ['Python'],
    total_rounds: 3,
    averages: { final_score: 80 },
    rounds: [
      {
        final_score: 75,
        question: 'Explain closures.',
        answer_text: 'A closure captures enclosing scope.',
        assessment_eligibility: 'excluded',
        eligibility_exclusion_reasons: ['unreviewed_content'],
        is_follow_up: false,
        assisted: false,
      },
      {
        final_score: 80,
        question: 'Explain generators.',
        answer_text: 'Generators yield values lazily.',
        assessment_eligibility: 'eligible',
        eligibility_exclusion_reasons: [],
      },
      {
        final_score: 65,
        question: 'Explain decorators.',
        answer_text: 'Decorators wrap callables.',
        assessment_eligibility: 'excluded',
        eligibility_exclusion_reasons: ['teaching_exposure'],
        assisted: true,
      },
    ],
  });

  assert.equal(mapped.rounds[0].practiceLabel, 'Practice, not scored');
  assert.equal(mapped.rounds[0].practiceHint, UNREVIEWED_HINT);
  assert.equal(mapped.rounds[1].practiceLabel, 'Assessment');
  assert.equal(mapped.rounds[1].practiceHint, null);
  assert.equal(mapped.rounds[2].practiceLabel, 'Practiced with help');
  assert.equal(mapped.rounds[2].practiceHint, null);
});
