import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-interview-render-'));
const bundle = path.join(scratch, 'render.cjs');
let renderInterview;
try {
  await build({
    stdin: {
      resolveDir: root,
      loader: 'jsx',
      contents: `
        import React from 'react';
        import { renderToStaticMarkup } from 'react-dom/server';
        import { MemoryRouter, Routes, Route } from 'react-router-dom';
        import Interview from './src/pages/Interview.jsx';
        export function render(opts = {}) {
          const {
            roundType = 'mcq',
            blockCategory = 'verbal',
            calibrated = false,
            round = 1,
          } = opts;
          const skill =
            blockCategory === 'verbal' ? 'Verbal Ability'
              : blockCategory === 'oa' ? 'DBMS'
                : 'Python';
          const state = {
            sessionId: 'render-check',
            skill,
            allSkills: [skill],
            round_type: roundType,
            block_category: blockCategory,
            round,
            totalRounds: roundType === 'mcq' ? 1 : 2,
            question: 'Explain a generator.',
            question_context: {
              questions: [{
                id: 'q1',
                stem: 'Choose the synonym of concise.',
                options: [{ id: 'a', text: 'brief' }, { id: 'b', text: 'lengthy' }],
              }],
            },
            config_json: { duration_minutes: 20, count: 1, negative_marking: 0.25 },
            engagementBaseline: calibrated
              ? { label: 'Neutral', confidence: null, sample_count: 0 }
              : null,
          };
          return renderToStaticMarkup(
            <MemoryRouter initialEntries={[{ pathname: '/interview/render-check', state }]}>
              <Routes>
                <Route path="/interview/:sessionId" element={<Interview />} />
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
  renderInterview = createRequire(import.meta.url)(bundle).render;
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

function render(opts) {
  const previous = globalThis.window;
  globalThis.window = {};
  try {
    return renderInterview(opts);
  } finally {
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
  }
}

test('verbal MCQ opens directly without camera calibration or the technical timer', () => {
  const html = render({ roundType: 'mcq', blockCategory: 'verbal' });
  assert.match(html, /data-testid="mcq-round-container"/);
  assert.match(html, /Choose the synonym of concise/);
  assert.match(html, /20:00/);
  assert.doesNotMatch(html, /Calibration|<video|Time left in this round|02:00/);
});

test('OA MCQ also skips calibration (same mcq round_type, oa category)', () => {
  const html = render({ roundType: 'mcq', blockCategory: 'oa' });
  assert.match(html, /data-testid="mcq-round-container"/);
  assert.doesNotMatch(html, /Calibration|<video/);
});

test('technical interview retains its calibration and answer screen', () => {
  assert.match(
    render({ roundType: 'technical_short_answer', blockCategory: 'interview' }),
    /Calibration/,
  );
  const html = render({
    roundType: 'technical_short_answer',
    blockCategory: 'interview',
    calibrated: true,
  });
  assert.match(html, /Explain a generator/);
  assert.match(html, /<textarea/);
  assert.match(html, /Time left in this round/);
  assert.doesNotMatch(html, /data-testid="mcq-round-container"/);
});

test('mixed Verbal→Interview: interview block still presents calibration after round > 1', () => {
  // Per-block gate: entering an interview category with no baseline must show
  // calibration even when the session round number is already past 1.
  const html = render({
    roundType: 'technical_short_answer',
    blockCategory: 'interview',
    round: 2,
    calibrated: false,
  });
  assert.match(html, /Calibration/);
  assert.doesNotMatch(html, /data-testid="mcq-round-container"/);
});


test('ML primitives renders its ungraded editor without calibration or a score', () => {
  const html = render({ roundType: 'ml_primitives', blockCategory: 'ml_primitives' });
  assert.match(html, /data-testid="ml-primitives-round"/);
  assert.match(html, /Scoring is currently unavailable/);
  assert.match(html, /Submit solution \(ungraded\)/);
  assert.match(html, /aria-label="Python solution"/);
  assert.doesNotMatch(html, /Calibration|<video|Run Examples|Time left in this round/);
});
