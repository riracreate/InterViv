import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildReviewSummaryProps,
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
  assert.equal(mapped.overall.score, 0);
  assert.equal(mapped.rounds.length, 0);
  assert.equal(mapped.reviewSummary.completedRounds, 0);
  assert.equal(mapped.reviewSummary.guardCount, 0);
});
