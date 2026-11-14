import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { summarizePlannedScope } from '../src/lib/practiceBuilder.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(root, rel), 'utf8');

const skill = (name, questions, extra = {}) => ({
  skill: name,
  questions,
  served_as: null,
  offline_questions: 100,
  offline_needed: questions,
  source: 'bank',
  available: true,
  ...extra,
});

test('summarizePlannedScope is null without an interview scope', () => {
  assert.equal(summarizePlannedScope(null), null);
  assert.equal(summarizePlannedScope({ blocks: [] }), null);
  // An OA block, or a server that predates the field.
  assert.equal(summarizePlannedScope({ blocks: [{ category: 'oa', available: true }] }), null);
});

test('summarizePlannedScope lists questions per confirmed skill and their source', () => {
  const scope = summarizePlannedScope({
    available: true,
    blocks: [{
      category: 'interview',
      planned_scope: {
        questions: 5,
        skills: [
          skill('DBMS', 2),
          skill('AWS', 2, { served_as: 'System Design' }),
          skill('Agile', 1, { source: 'generated', offline_questions: 0 }),
        ],
        not_covered: [],
      },
    }],
  });
  assert.equal(scope.questions, 5);
  assert.deepEqual(scope.skills, [
    { skill: 'DBMS', questions: 2, available: true, note: 'question bank' },
    { skill: 'AWS', questions: 2, available: true, note: 'from the System Design question bank' },
    { skill: 'Agile', questions: 1, available: true, note: 'generated for this skill' },
  ]);
  assert.deepEqual(scope.notCovered, []);
  assert.deepEqual(scope.unavailable, []);
});

test('summarizePlannedScope discloses skills the budget or the content cannot cover', () => {
  const scope = summarizePlannedScope({
    available: false,
    blocks: [{
      category: 'interview',
      planned_scope: {
        questions: 3,
        skills: [
          skill('AWS', 1, { served_as: 'System Design', offline_questions: 3, offline_needed: 4, available: false }),
          skill('Agile', 2, { offline_questions: 0, available: false }),
        ],
        not_covered: ['Docker', 'Git'],
      },
    }],
  });
  assert.deepEqual(scope.notCovered, ['Docker', 'Git']);
  assert.deepEqual(scope.unavailable, ['AWS', 'Agile']);
  assert.equal(
    scope.skills[0].note,
    'not enough scored questions: this plan needs 4 from the System Design bank, which has 3',
  );
  assert.equal(scope.skills[1].note, 'no scored questions in the offline bank');
});

test('summarizePlannedScope adds up the blocks of a Full Interview', () => {
  const scope = summarizePlannedScope({
    blocks: [
      { category: 'interview', planned_scope: { questions: 3, skills: [skill('DBMS', 3)], not_covered: [] } },
      { category: 'interview', planned_scope: { questions: 3, skills: [skill('OOP', 3)], not_covered: [] } },
    ],
  });
  assert.equal(scope.questions, 6);
  assert.deepEqual(scope.skills.map((item) => [item.skill, item.questions]), [['DBMS', 3], ['OOP', 3]]);
});

test('summarizePlannedScope keeps one row per skill across blocks', () => {
  const scope = summarizePlannedScope({
    blocks: [
      { category: 'interview', planned_scope: { questions: 2, skills: [skill('DBMS', 1), skill('OOP', 1)], not_covered: ['DSA'] } },
      { category: 'oa', available: true },
      {
        category: 'interview',
        planned_scope: {
          questions: 3,
          skills: [skill('DBMS', 2, { available: false, offline_questions: 0 }), skill('DSA', 1)],
          not_covered: ['OS', 'OS'],
        },
      },
    ],
  });
  assert.equal(scope.questions, 5);
  assert.deepEqual(scope.skills.map((item) => [item.skill, item.questions, item.available]), [
    ['DBMS', 3, false], ['OOP', 1, true], ['DSA', 1, true],
  ]);
  assert.equal(scope.skills[0].note, 'no scored questions in the offline bank');
  // DSA is planned by the second block, so it is covered.
  assert.deepEqual(scope.notCovered, ['OS']);
  assert.deepEqual(scope.unavailable, ['DBMS']);
});

test('a resume never selects skills for the candidate', () => {
  // The extracted list is alphabetical. Taking its first few entries made a
  // five-skill interview out of whatever sorted first.
  const practice = read('src/pages/Practice.jsx');
  assert.doesNotMatch(practice, /topSkills/);
  assert.doesNotMatch(practice, /extractedSkills[^;\n]*\.slice\(/);
  assert.match(practice, /Choose the ones to practise/);
  const panel = read('src/components/InterviewResumePanel.jsx');
  assert.doesNotMatch(panel, /Use top resume skills/);
  assert.doesNotMatch(panel, /extractedSkills\.slice\(/);
  assert.match(panel, /listed A–Z/);
});

test('every setup that can ask interview questions shows the planned scope before its start button', () => {
  const practice = read('src/pages/Practice.jsx');
  // Full Interview, Interview practice and the block builder.
  assert.equal((practice.match(/<PlannedScope scope=\{plannedScope\} \/>/g) || []).length, 3);
  assert.match(practice, /payloadHasInterview\(mapped\.payload\) \? mapped\.payload : null/);
  assert.match(practice, /data-testid="planned-scope"/);
  assert.match(practice, /data-testid="planned-scope-not-covered"/);
  assert.match(practice, /data-testid="planned-scope-unavailable"/);
  // The preview comes from the endpoint the start itself is checked against.
  assert.match(practice, /fetchAvailability\(stripClientOnly\(scopePayload\)\)/);
});
