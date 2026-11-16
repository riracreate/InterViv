import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { mapCoachPlan } from '../src/lib/coachMapping.js';
import {
  jobLaunchScope, jobPracticeBody, jobSkillKey, jobSkillList, jobStartState,
} from '../src/lib/jobsMapping.js';
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
  assert.deepEqual(scope.noContent, []);
  assert.deepEqual(scope.insufficient, []);
  assert.deepEqual(scope.unavailable, []);
});

test('summarizePlannedScope separates the three kinds of gap, which need different advice', () => {
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
  // The budget does not reach these: a warning, nothing blocks the start.
  assert.deepEqual(scope.notCovered, ['Docker', 'Git']);
  // Nothing offline is about the skill: remove it or generate live.
  assert.deepEqual(scope.noContent, ['Agile']);
  // Some questions, fewer than planned: the counts say how far short.
  assert.deepEqual(scope.insufficient, [
    { skill: 'AWS', planned: 2, available: 1, sharedWith: [] },
    { skill: 'OOP', planned: 5, available: 7, sharedWith: ['Java'] },
  ]);
  assert.deepEqual(scope.unavailable, ['AWS', 'OOP', 'Agile']);
  assert.equal(scope.skills[0].note, '2 planned, 1 available offline');
  assert.equal(scope.skills[1].note, '5 planned, 7 available offline, shared with Java');
  assert.equal(scope.skills[2].note, 'no offline questions');
});

test('a skill planned in two blocks reports its plan-wide count', () => {
  const short = (questions) => skill('DBMS', questions, { planned_total: 10, offline_questions: 9, available: false });
  const scope = summarizePlannedScope({
    blocks: [
      { category: 'interview', planned_scope: { questions: 5, skills: [short(5)], not_covered: [] } },
      { category: 'interview', planned_scope: { questions: 5, skills: [short(5)], not_covered: [] } },
    ],
  });
  assert.deepEqual(scope.skills, [
    { skill: 'DBMS', questions: 10, available: false, note: '10 planned, 9 available offline' },
  ]);
  assert.deepEqual(scope.insufficient, [{ skill: 'DBMS', planned: 10, available: 9, sharedWith: [] }]);
  assert.deepEqual(scope.noContent, []);
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
  assert.equal(scope.skills[0].note, 'no offline questions');
  assert.deepEqual(scope.noContent, ['DBMS']);
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
  // Jobs and Coach build their plan on the server and show the same panel.
  assert.match(read('src/pages/Jobs.jsx'), /<PlannedScope\s+scope=\{jobSkillList\(draftSkills\)\.length \? jobLaunchScope\(prepare\) : null\}/);
  assert.match(read('src/pages/Coach.jsx'), /<PlannedScope\s+scope=\{plan\.practicePreview\.plannedScope\}/);
});

test('the scope panel gives each kind of gap its own advice in one shared style', () => {
  const panel = read('src/components/PlannedScope.jsx');
  // A warning for the budget, errors for content; never one catch-all line.
  assert.match(panel, /className="app-notice app-notice-warn" data-testid="planned-scope-not-covered"/);
  assert.match(panel, /className="app-notice app-notice-error" data-testid="planned-scope-no-content"/);
  assert.match(panel, /className="app-notice app-notice-error" data-testid="planned-scope-insufficient"/);
  assert.match(panel, /Remove \{them\(noContent\)\}, or use live\s+question generation where it is configured\./);
  assert.match(panel, /Lower the question count or remove \$\{them\(insufficient\)\}\./);
  assert.match(panel, /has \$\{item\.available\} of \$\{item\.planned\} planned/);
  assert.doesNotMatch(panel, /Remove \{[^}]*\} to start/);
  // Notices are block elements with their own colours. The hub pages colour
  // every paragraph grey, which hid the red on the Jobs dialog.
  assert.doesNotMatch(panel, /<p[\s>]/);
  assert.doesNotMatch(panel, /text-\[var\(--color-danger\)\]/);
  const theme = read('src/styles/theme.css');
  for (const rule of ['.app-notice {', '.app-notice-warn {', '.app-notice-error {', '.app-text-error {']) {
    assert.ok(theme.includes(rule), rule);
  }
  // Fixed-count launches cannot be told to lower the question count.
  assert.match(read('src/pages/Jobs.jsx'), /countFixed/);
  assert.match(read('src/pages/Coach.jsx'), /countFixed/);
  // The Practice preview comes from the endpoint the start itself is checked against.
  assert.match(read('src/pages/Practice.jsx'), /fetchAvailability\(stripClientOnly\(scopePayload\)\)/);
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

const jobDraft = (skills, plannedScope) => ({
  job_id: 'job-1',
  proposed_skills: skills,
  proposed_blocks: skills.slice(0, 3).map((name) => ({ category: 'interview', skills: [name], count: 1 })),
  planned_scope: plannedScope,
});

test('Jobs confirm starts only from a preview built for the skills in the field', () => {
  const draft = jobDraft(['DBMS', 'OOP', 'Django', 'React', 'AWS'], launchScope);
  const text = 'DBMS, OOP, Django, React, AWS';
  const previewKey = jobSkillKey(text);
  assert.deepEqual(jobSkillList(' DBMS ,, OOP,'), ['DBMS', 'OOP']);
  // Spacing and case do not make a different list; a different skill does.
  assert.equal(jobSkillKey('dbms,  OOP, Django, React, AWS'), previewKey);
  assert.notEqual(jobSkillKey('DBMS, OOP, React'), previewKey);
  assert.deepEqual(jobLaunchScope(draft).unavailable, ['Django']);

  // The preview is current but Django has no offline questions.
  assert.deepEqual(jobStartState({ draft, skillsText: text, previewKey }), {
    canStart: false, reason: 'Change the skills marked above to start.',
  });

  // The candidate removes Django. Until the server has rebuilt the draft for
  // the new list, the old preview is not the plan and Start stays off.
  const edited = 'DBMS, OOP, React';
  assert.deepEqual(jobStartState({ draft, skillsText: edited, previewKey }), {
    canStart: false, reason: 'Updating the preview for these skills…',
  });
  assert.equal(jobStartState({ draft, skillsText: edited, previewKey, previewBusy: true }).canStart, false);
  assert.deepEqual(jobStartState({ draft, skillsText: edited, previewKey, previewError: 'timeout' }), {
    canStart: false, reason: 'Could not update the preview: timeout',
  });
  assert.deepEqual(jobStartState({ draft, skillsText: ' , ', previewKey }), {
    canStart: false, reason: 'Enter at least one skill.',
  });

  // The refreshed draft is for the edited skills and nothing is short.
  const refreshed = jobDraft(['DBMS', 'OOP', 'React'], {
    questions: 3, skills: [skill('DBMS', 1), skill('OOP', 1), skill('React', 1)], not_covered: [],
  });
  assert.deepEqual(
    jobStartState({ draft: refreshed, skillsText: edited, previewKey: jobSkillKey(edited) }),
    { canStart: true, reason: '' },
  );
  // A refresh still in flight for a later edit blocks the start again.
  assert.equal(
    jobStartState({ draft: refreshed, skillsText: edited, previewKey: jobSkillKey(edited), previewBusy: true }).canStart,
    false,
  );
});

test('Jobs start request carries the previewed skills and blocks, not the raw field', () => {
  const refreshed = jobDraft(['DBMS', 'OOP', 'React'], null);
  assert.deepEqual(jobPracticeBody(refreshed, { company: 'Acme', role: 'SDE', fullJd: '' }), {
    confirm: true,
    skills: ['DBMS', 'OOP', 'React'],
    blocks: refreshed.proposed_blocks,
    company: 'Acme',
    role: 'SDE',
    full_jd: undefined,
  });
  assert.equal(jobPracticeBody(refreshed, { fullJd: 'full text' }).full_jd, 'full text');
  const jobs = read('src/pages/Jobs.jsx');
  // The dialog asks the server for a draft of the edited skills and holds
  // Start until it has one.
  assert.match(jobs, /fetchJobPrepare\(prepareJobId, \{ skills: jobSkillList\(draftSkills\) \}\)/);
  assert.match(jobs, /disabled=\{busy \|\| !startState\.canStart\}/);
  assert.match(jobs, /if \(!prepare\?\.job_id \|\| !startState\.canStart\) return;/);
  assert.doesNotMatch(jobs, /job-scope-edited/);
});
