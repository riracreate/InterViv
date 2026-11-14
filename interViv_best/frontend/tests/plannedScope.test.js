import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { mapCoachPlan } from '../src/lib/coachMapping.js';
import { jobLaunchScope, jobPracticeBody, jobSkillsEdited } from '../src/lib/jobsMapping.js';
import { summarizeLaunchScope, summarizePlannedScope } from '../src/lib/practiceBuilder.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(root, rel), 'utf8');

const skill = (name, questions, extra = {}) => ({
  skill: name,
  questions,
  planned_total: questions,
  served_as: null,
  offline_questions: 9,
  offline_needed: questions,
  shared_with: [],
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
          skill('SQL', 2, { served_as: 'DBMS', shared_with: ['DBMS'] }),
          skill('Agile', 1, { source: 'generated', offline_questions: 0 }),
        ],
        not_covered: [],
      },
    }],
  });
  assert.equal(scope.questions, 5);
  assert.deepEqual(scope.skills, [
    { skill: 'DBMS', questions: 2, available: true, note: 'question bank' },
    { skill: 'SQL', questions: 2, available: true, note: 'from the DBMS question bank' },
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
          skill('AWS', 2, { offline_questions: 1, available: false }),
          skill('OOP', 5, { offline_questions: 7, offline_needed: 10, shared_with: ['Java'], available: false }),
          skill('Agile', 2, { offline_questions: 0, available: false }),
        ],
        not_covered: ['Docker', 'Git'],
      },
    }],
  });
  assert.deepEqual(scope.notCovered, ['Docker', 'Git']);
  assert.deepEqual(scope.unavailable, ['AWS', 'OOP', 'Agile']);
  assert.equal(scope.skills[0].note, 'only 1 scored question in the offline bank');
  assert.equal(scope.skills[1].note, 'only 7 scored questions in the offline bank, shared with Java');
  assert.equal(scope.skills[2].note, 'no scored questions in the offline bank');
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
  const panel = read('src/components/PlannedScope.jsx');
  assert.match(panel, /data-testid="planned-scope"/);
  assert.match(panel, /data-testid="planned-scope-not-covered"/);
  assert.match(panel, /data-testid="planned-scope-unavailable"/);
  // Jobs and Coach build their plan on the server and show the same panel.
  assert.match(read('src/pages/Jobs.jsx'), /<PlannedScope\s+scope=\{jobLaunchScope\(prepare, draftSkills\)\}/);
  assert.match(read('src/pages/Coach.jsx'), /<PlannedScope\s+scope=\{plan\.practicePreview\.plannedScope\}/);
  // The preview comes from the endpoint the start itself is checked against.
  assert.match(practice, /fetchAvailability\(stripClientOnly\(scopePayload\)\)/);
});

const launchScope = {
  questions: 3,
  skills: [skill('DBMS', 1), skill('OOP', 1), skill('Django', 1, { offline_questions: 0, available: false })],
  not_covered: ['React', 'AWS'],
};

test('summarizeLaunchScope reads the planned scope of a server-built launch', () => {
  assert.equal(summarizeLaunchScope(null), null);
  assert.equal(summarizeLaunchScope(undefined), null);
  const scope = summarizeLaunchScope(launchScope);
  assert.equal(scope.questions, 3);
  assert.deepEqual(scope.skills.map((item) => item.skill), ['DBMS', 'OOP', 'Django']);
  assert.deepEqual(scope.notCovered, ['React', 'AWS']);
  assert.deepEqual(scope.unavailable, ['Django']);
});

test('Coach plan carries the planned scope of its three-question launch', () => {
  const plan = mapCoachPlan({
    steps: [],
    practice_preview: {
      skills: ['DBMS', 'OOP', 'Django', 'React', 'AWS'],
      round_plan: ['technical_short_answer', 'technical_short_answer', 'technical_short_answer', 'mcq'],
      planned_scope: launchScope,
    },
  });
  assert.equal(plan.practicePreview.plannedScope.questions, 3);
  assert.deepEqual(plan.practicePreview.plannedScope.notCovered, ['React', 'AWS']);
  assert.equal(mapCoachPlan({ steps: [], practice_preview: { skills: [] } }).practicePreview.plannedScope, null);
});

test('Jobs confirm shows the scope of the proposed blocks and sends them only while the skills match', () => {
  const draft = {
    job_id: 'job-1',
    proposed_skills: ['DBMS', 'OOP', 'Django', 'React', 'AWS'],
    proposed_blocks: [{ category: 'interview', skills: ['DBMS'], count: 1 }],
    planned_scope: launchScope,
  };
  const same = 'dbms,  OOP, Django, React, AWS';
  assert.equal(jobSkillsEdited(draft, same), false);
  assert.deepEqual(jobLaunchScope(draft, same).unavailable, ['Django']);
  assert.deepEqual(jobPracticeBody(draft, { skillsText: same, company: 'Acme', role: 'SDE' }), {
    confirm: true,
    skills: ['dbms', 'OOP', 'Django', 'React', 'AWS'],
    company: 'Acme',
    role: 'SDE',
    full_jd: undefined,
    blocks: draft.proposed_blocks,
  });

  // The candidate removed Django: the proposed blocks no longer describe the
  // plan, so they are neither summarised nor sent.
  const edited = 'DBMS, OOP, React';
  assert.equal(jobSkillsEdited(draft, edited), true);
  assert.equal(jobLaunchScope(draft, edited), null);
  const body = jobPracticeBody(draft, { skillsText: edited, fullJd: 'full text' });
  assert.deepEqual(body.skills, ['DBMS', 'OOP', 'React']);
  assert.equal('blocks' in body, false);
  assert.equal(body.full_jd, 'full text');
});
