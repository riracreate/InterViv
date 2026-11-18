import assert from 'node:assert/strict';
import test from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { build } from 'esbuild';

import {
  REVIEW_CHECKLIST_ITEMS,
  adminErrorNotice,
  availableDecisions,
  buildDecisionPayload,
  canSubmitForReview,
  emptyChecklist,
  formatAutoCheckSummary,
  validateReviewForm,
} from '../src/lib/bundleReview.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const bundled = await build({
  stdin: {
    resolveDir: root,
    loader: 'jsx',
    contents: `
      import React from 'react';
      import { renderToStaticMarkup } from 'react-dom/server';
      import { MemoryRouter } from 'react-router-dom';
      import BundleReview from './src/pages/BundleReview.jsx';
      export const renderReview = props =>
        renderToStaticMarkup(<MemoryRouter><BundleReview {...props} /></MemoryRouter>);
    `,
  },
  bundle: true,
  platform: 'node',
  format: 'cjs',
  write: false,
  logLevel: 'silent',
  define: { 'process.env.NODE_ENV': '"production"' },
});

const mod = { exports: {} };
new Function('require', 'module', 'exports', bundled.outputFiles[0].text)(
  createRequire(path.join(root, 'package.json')),
  mod,
  mod.exports
);
const { renderReview } = mod.exports;

const sampleDetail = (status = 'in_review', extra = {}) => ({
  bundle_id: 'statistics.mean-vs-median-with-outliers-easy',
  version: 1,
  content_hash: 'a'.repeat(64),
  status,
  source: 'llm_draft',
  distinct_approvers: 1,
  distinct_rejecters: 0,
  needs_adjudication: false,
  attribution: {
    auto_check: {
      auto_check_ran: true,
      to_status: 'auto_checked',
      reason: 'Blind answer covered all required concepts with zero misconceptions.',
      check_provider: 'groq',
      check_model: 'openai/gpt-oss-120b',
      coverage: { k_supported: 3, n_required: 3 },
      missed_concepts: [],
      misconception_hits: [],
    },
  },
  content: {
    question: 'Explain how an extreme outlier shifts mean and median differently.',
    reference_answer: 'Outliers pull the arithmetic mean while leaving the sorted median stable.',
    required_concepts: [
      {
        id: 'mean_shift',
        descriptor: 'Mean shifts toward extreme values',
        aliases: ['average pulled'],
        expected_propositions: ['extreme outliers pull arithmetic mean toward tail'],
      },
    ],
    misconceptions: [
      {
        id: 'mean_unchanged',
        description: 'Claiming the mean is unaffected by extreme values.',
        candidate_patterns: ['outliers never affect the mean'],
      },
    ],
    followups: [
      { prompt: 'Why does sorting stabilize the median?', targets_concept: 'mean_shift' },
    ],
  },
  ...extra,
});

const sampleBundles = [
  {
    bundle_id: 'statistics.mean-vs-median-with-outliers-easy',
    skill: 'Statistics',
    topic: 'mean vs median with outliers',
    versions: [
      {
        bundle_id: 'statistics.mean-vs-median-with-outliers-easy',
        version: 1,
        status: 'auto_checked',
        author_id: 'phase1b-dev:concept-authorship',
      },
    ],
  },
];

test('review form helpers validate 7 checklist items, calibration difficulty, and >=20-char reasons', () => {
  const allTrue = emptyChecklist(true);
  assert.equal(REVIEW_CHECKLIST_ITEMS.length, 7);
  assert.equal(canSubmitForReview('draft'), true);
  assert.equal(canSubmitForReview('auto_checked'), true);
  assert.equal(canSubmitForReview('in_review'), false);
  assert.deepEqual(availableDecisions({ needs_adjudication: false }), ['approve', 'reject']);
  assert.deepEqual(availableDecisions({ needs_adjudication: true }), ['adjudicate_approve', 'adjudicate_reject']);

  assert.match(
    validateReviewForm({ decision: 'approve', checklist: { ...allTrue, no_ambiguity: false }, reasons: 'Detailed technical explanation here.', difficulty: 'easy' }),
    /no_ambiguity/
  );
  assert.match(
    validateReviewForm({ decision: 'approve', checklist: allTrue, reasons: 'lgtm', difficulty: 'easy' }),
    /20 characters/
  );
  assert.match(
    validateReviewForm({ decision: 'approve', checklist: allTrue, reasons: 'Clear question and accurate reference.', difficulty: '' }),
    /calibration/
  );
  assert.equal(
    validateReviewForm({ decision: 'reject', checklist: { ...allTrue, no_ambiguity: false }, reasons: 'Ambiguous wording in the prompt needs revision.', difficulty: 'medium' }),
    null
  );

  const payload = buildDecisionPayload({
    contentHash: 'b'.repeat(64),
    decision: 'approve',
    checklist: allTrue,
    reasons: 'Verified all propositions and misconceptions against blind check.',
    difficulty: 'MEDIUM',
  });
  assert.equal(payload.content_hash, 'b'.repeat(64));
  assert.equal(payload.calibration.difficulty, 'medium');
  assert.equal(Object.keys(payload.checklist).length, 7);
});

test('formatAutoCheckSummary and adminErrorNotice format checker and gated access states cleanly', () => {
  const summary = formatAutoCheckSummary(sampleDetail().attribution);
  assert.equal(summary.ran, true);
  assert.equal(summary.verdict, 'Passed');
  assert.equal(summary.coverageText, '3/3');
  assert.equal(summary.providerModel, 'groq / openai/gpt-oss-120b');

  assert.match(adminErrorNotice({ status: 404 }), /ENABLE_ADMIN_ENDPOINTS/);
  assert.match(adminErrorNotice({ status: 403 }), /ADMIN_USER_EMAILS/);
});

test('BundleReview SSR renders question, hidden reference, concepts, misconceptions, follow-ups, verdict, checklist, and disabled notice', () => {
  const inReviewHtml = renderReview({
    initialBundles: sampleBundles,
    initialDetail: sampleDetail('in_review'),
  });
  assert.match(inReviewHtml, /Explain how an extreme outlier shifts mean and median differently/);
  assert.match(inReviewHtml, /Hidden Reference Answer/);
  assert.match(inReviewHtml, /Outliers pull the arithmetic mean while leaving the sorted median stable/);
  assert.match(inReviewHtml, /mean_shift/);
  assert.match(inReviewHtml, /mean_unchanged/);
  assert.match(inReviewHtml, /Why does sorting stabilize the median/);
  assert.match(inReviewHtml, /Automated Checker Verdict/);
  assert.match(inReviewHtml, /groq \/ openai\/gpt-oss-120b/);
  assert.match(inReviewHtml, /Reviewer Decision Checklist/);
  for (const { key } of REVIEW_CHECKLIST_ITEMS) {
    assert.match(inReviewHtml, new RegExp(key));
  }
  assert.match(inReviewHtml, />Approve</);
  assert.match(inReviewHtml, />Reject</);

  const autoCheckedHtml = renderReview({
    initialBundles: sampleBundles,
    initialDetail: sampleDetail('auto_checked'),
  });
  assert.match(autoCheckedHtml, /Submit for review/);
  assert.doesNotMatch(autoCheckedHtml, /Reviewer Decision Checklist/);

  const deniedHtml = renderReview({
    initialBundles: [],
    initialAccessError: adminErrorNotice({ status: 403 }),
  });
  assert.match(deniedHtml, /ADMIN_USER_EMAILS/);
});

test('review page shows concept guidance, flags question-word aliases, and lists positive examples', async () => {
  const { REVIEWER_CONCEPT_GUIDANCE, questionWordTerms } = await import('../src/lib/bundleReview.js');
  assert.equal(
    REVIEWER_CONCEPT_GUIDANCE,
    'Aliases must not be words from the question; propositions must be full claims.'
  );
  const question = 'Explain the difference between lists and tuples in Python.';
  assert.deepEqual(questionWordTerms(question, { id: 'tuple', aliases: ['tuples'] }), ['tuple', 'tuples']);
  assert.deepEqual(questionWordTerms(question, { id: 'tuple_immutability', aliases: ['immutable'] }), []);
  assert.deepEqual(questionWordTerms(question, { id: 'x', aliases: ['between-lists'] }), ['between-lists']);

  const detail = sampleDetail('in_review');
  detail.content = {
    ...detail.content,
    required_concepts: [
      {
        id: 'mean_shift',
        descriptor: 'Mean shifts toward extreme values',
        aliases: ['average pulled', 'outlier'],
        expected_propositions: ['extreme outliers pull arithmetic mean toward tail'],
        positive_examples: ['One huge value drags the average far from the typical case.'],
      },
    ],
  };
  const html = renderReview({ initialBundles: sampleBundles, initialDetail: detail });
  assert.match(html, /Aliases must not be words from the question; propositions must be full claims\./);
  assert.match(html, /Question words used as id\/alias:/);
  assert.match(html, /Positive examples:/);
  assert.match(html, /One huge value drags the average far from the typical case\./);
});
