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

test('technical interview opens straight to the answer screen with the camera off', () => {
  // No blocking calibration; the camera is optional and starts off.
  const html = render({ roundType: 'technical_short_answer', blockCategory: 'interview' });
  assert.doesNotMatch(html, /Calibration|<video/);
  assert.match(html, /Explain a generator/);
  assert.match(html, /<textarea/);
  assert.doesNotMatch(html, /<textarea[^>]*disabled=""/);
  assert.match(html, /Time left in this round/);
  assert.match(html, /Camera Off/);
  assert.match(html, /Save &amp; Exit/);
  // No "unavailable" warning before the candidate asks for the microphone.
  assert.doesNotMatch(html, /permission|unavailable/i);
  assert.doesNotMatch(html, /data-testid="mcq-round-container"/);
});

test('mixed Verbal→Interview: a later interview round is answerable at once', () => {
  const html = render({
    roundType: 'technical_short_answer',
    blockCategory: 'interview',
    round: 2,
  });
  assert.doesNotMatch(html, /Calibration/);
  assert.match(html, /<textarea/);
  assert.doesNotMatch(html, /<textarea[^>]*disabled=""/);
  assert.doesNotMatch(html, /data-testid="mcq-round-container"/);
});


test('SQL round skips camera calibration (media gate)', () => {
  const html = render({ roundType: 'sql', blockCategory: 'sql' });
  assert.match(html, /data-testid="sql-round-container"/);
  assert.doesNotMatch(html, /Calibration|<video|Time left in this round/);
});

test('MCQ round_type alone skips camera even without verbal/oa category', () => {
  const html = render({ roundType: 'mcq', blockCategory: null });
  assert.match(html, /data-testid="mcq-round-container"/);
  assert.doesNotMatch(html, /Calibration|<video/);
});

test('ML primitives renders its ungraded editor without calibration or a score', () => {
  const html = render({ roundType: 'ml_primitives', blockCategory: 'ml_primitives' });
  assert.match(html, /data-testid="ml-primitives-round"/);
  assert.match(html, /Scoring is currently unavailable/);
  assert.match(html, /Submit solution \(ungraded\)/);
  assert.match(html, /aria-label="Python solution"/);
  assert.doesNotMatch(html, /Calibration|<video|Run Examples|Time left in this round/);
});
