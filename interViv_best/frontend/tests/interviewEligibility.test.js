import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { PHASES } from '../src/lib/interviewLifecycle.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-interview-eligibility-'));
const bundle = path.join(scratch, 'render.cjs');
let renderInterview;
let interviewEligibilityFeedback;

try {
  await build({
    stdin: {
      resolveDir: root,
      loader: 'jsx',
      contents: `
        import React from 'react';
        import { renderToStaticMarkup } from 'react-dom/server';
        import { MemoryRouter, Routes, Route } from 'react-router-dom';
        import Interview, { interviewEligibilityFeedback } from './src/pages/Interview.jsx';
        export { interviewEligibilityFeedback };
        export function render(sessionState) {
          return renderToStaticMarkup(
            <MemoryRouter initialEntries={['/interview/elig-check']}>
              <Routes>
                <Route path="/interview/:sessionId" element={<Interview sessionState={sessionState} />} />
              </Routes>
            </MemoryRouter>
          );
        }
      `,
    },
    outfile: bundle,
    bundle: true,
    platform: 'node',
    format: 'cjs',
    loader: { '.css': 'empty' },
    define: { 'process.env.NODE_ENV': '"production"' },
    logLevel: 'silent',
    plugins: [{
      name: 'omit-camera-models-in-static-render',
      setup(builder) {
        builder.onLoad({ filter: /[/\\]lib[/\\]engagement\.js$/ }, () => ({
          contents: 'export const classifyFrame = async () => null; export const computeEngagementDelta = () => 0; export const loadModels = async () => false; export const modeOfLabels = () => null;',
          loader: 'js',
        }));
        builder.onLoad({ filter: /[/\\]lib[/\\]codingEditor\.js$/ }, () => ({
          contents: 'export const monaco = { editor: { defineTheme() {} } };',
          loader: 'js',
        }));
      },
    }],
  });
  ({ render: renderInterview, interviewEligibilityFeedback } = createRequire(import.meta.url)(bundle));
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

function render(sessionState) {
  const previous = globalThis.window;
  globalThis.window = {};
  try {
    return renderInterview(sessionState);
  } finally {
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
  }
}

const UNREVIEWED_HINT =
  'Auto-checked question — feedback is shown for practice; not counted toward readiness or Elo.';

test('interviewEligibilityFeedback returns Practice, not scored + hint only for standalone unreviewed_content', () => {
  assert.deepEqual(
    interviewEligibilityFeedback(
      {
        assessment_eligibility: 'excluded',
        eligibility_exclusion_reasons: ['unreviewed_content'],
        is_follow_up: false,
        assisted: false,
      },
      78,
    ),
    {
      label: 'Practice, not scored',
      hint: UNREVIEWED_HINT,
    },
  );

  assert.deepEqual(
    interviewEligibilityFeedback({ assessment_eligibility: 'eligible' }, 84),
    { label: 'Assessment', hint: '' },
  );
  assert.deepEqual(
    interviewEligibilityFeedback(
      {
        assessment_eligibility: 'excluded',
        eligibility_exclusion_reasons: ['follow_up'],
        is_follow_up: true,
        assisted: false,
      },
      null,
    ),
    { label: 'Follow-up · Practiced with help', hint: '' },
  );
  assert.deepEqual(
    interviewEligibilityFeedback(
      {
        assessment_eligibility: 'excluded',
        eligibility_exclusion_reasons: ['unreviewed_content'],
        is_follow_up: false,
        assisted: true,
      },
      70,
    ),
    { label: 'Practiced with help', hint: '' },
  );
  assert.deepEqual(
    interviewEligibilityFeedback(
      {
        assessment_eligibility: 'excluded',
        eligibility_exclusion_reasons: ['unreviewed_content', 'teaching_exposure'],
        is_follow_up: false,
        assisted: false,
      },
      70,
    ),
    { label: 'Practiced with help', hint: '' },
  );
  assert.deepEqual(
    interviewEligibilityFeedback(
      {
        assessment_eligibility: 'excluded',
        eligibility_exclusion_reasons: ['unreviewed_content', 'same_item_retry'],
        is_follow_up: false,
        assisted: false,
      },
      70,
    ),
    { label: 'Practiced with help', hint: '' },
  );
  assert.deepEqual(
    interviewEligibilityFeedback({ assessment_eligibility: 'unknown' }, 60),
    { label: 'Unscored practice', hint: '' },
  );
  assert.deepEqual(
    interviewEligibilityFeedback({ assessment_eligibility: 'legacy_unknown' }, 60),
    { label: 'Unscored practice', hint: '' },
  );
  assert.deepEqual(
    interviewEligibilityFeedback({}, null),
    { label: 'Unscored practice', hint: '' },
  );
  assert.deepEqual(
    interviewEligibilityFeedback({}, 88),
    { label: '', hint: '' },
  );
});

test('Interview feedback panel renders Practice, not scored and hint beneath it for unreviewed_content', () => {
  const html = render({
    sessionId: 'elig-check',
    skill: 'Python',
    allSkills: ['Python'],
    round: 1,
    totalRounds: 2,
    round_type: 'technical_short_answer',
    block_category: 'interview',
    question: 'Explain closures in Python.',
    answerText: 'A closure remembers bindings from its enclosing scope.',
    phase: PHASES.REVIEWING,
    currentScore: 76,
    currentFeedback: 'Good explanation of enclosing scope.',
    assessment_eligibility: 'excluded',
    eligibility_exclusion_reasons: ['unreviewed_content'],
    is_follow_up: false,
    assisted: false,
  });

  const labelIdx = html.indexOf('Practice, not scored');
  const hintIdx = html.indexOf(UNREVIEWED_HINT);
  assert.notEqual(labelIdx, -1);
  assert.notEqual(hintIdx, -1);
  assert.ok(hintIdx > labelIdx, 'hint should appear beneath eligibilityLabel');
  assert.match(html, /data-testid="eligibility-label"[^>]*>Practice, not scored</);
  assert.match(html, /data-testid="eligibility-practice-hint"[^>]*>Auto-checked question — feedback is shown for practice; not counted toward readiness or Elo\.</);
});

test('Interview feedback panel omits unreviewed hint for Assessment, Follow-up, Practiced with help, and Unscored practice', () => {
  const base = {
    sessionId: 'elig-check',
    skill: 'Python',
    allSkills: ['Python'],
    round: 1,
    totalRounds: 2,
    round_type: 'technical_short_answer',
    block_category: 'interview',
    question: 'Explain closures in Python.',
    answerText: 'A closure remembers bindings from its enclosing scope.',
    phase: PHASES.REVIEWING,
    currentScore: 82,
    currentFeedback: 'Solid answer.',
  };

  const assessmentHtml = render({
    ...base,
    assessment_eligibility: 'eligible',
    eligibility_exclusion_reasons: [],
  });
  assert.match(assessmentHtml, /data-testid="eligibility-label"[^>]*>Assessment</);
  assert.doesNotMatch(assessmentHtml, /eligibility-practice-hint|Auto-checked question/);

  const followUpHtml = render({
    ...base,
    currentScore: null,
    assessment_eligibility: 'excluded',
    eligibility_exclusion_reasons: ['follow_up'],
    is_follow_up: true,
    assisted: false,
  });
  assert.match(followUpHtml, /data-testid="eligibility-label"[^>]*>Follow-up · Practiced with help</);
  assert.doesNotMatch(followUpHtml, /eligibility-practice-hint|Auto-checked question/);

  const assistedHtml = render({
    ...base,
    assessment_eligibility: 'excluded',
    eligibility_exclusion_reasons: ['teaching_exposure'],
    is_follow_up: false,
    assisted: true,
  });
  assert.match(assistedHtml, /data-testid="eligibility-label"[^>]*>Practiced with help</);
  assert.doesNotMatch(assistedHtml, /eligibility-practice-hint|Auto-checked question/);

  const unscoredHtml = render({
    ...base,
    assessment_eligibility: 'unknown',
    eligibility_exclusion_reasons: [],
  });
  assert.match(unscoredHtml, /data-testid="eligibility-label"[^>]*>Unscored practice</);
  assert.doesNotMatch(unscoredHtml, /eligibility-practice-hint|Auto-checked question/);
});
