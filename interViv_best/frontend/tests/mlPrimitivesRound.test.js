// ML primitives round: graded review keeps its result on screen until Next.
import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-ml-round-'));
const bundle = path.join(scratch, 'render.cjs');
let render;
try {
  await build({
    stdin: {
      resolveDir: root,
      loader: 'jsx',
      contents: `
        import React from 'react';
        import { renderToStaticMarkup } from 'react-dom/server';
        import MLPrimitivesRound from './src/components/MLPrimitivesRound.jsx';
        export function render(props) {
          return renderToStaticMarkup(<MLPrimitivesRound sessionId="s" round={1}
            questionContext={{ title: 'Min-max', statement: 'Scale rows.', constraints: [], difficulty: 'easy' }}
            {...props} />);
        }
      `,
    },
    outfile: bundle,
    bundle: true,
    platform: 'node',
    format: 'cjs',
    define: { 'process.env.NODE_ENV': '"production"' },
    logLevel: 'silent',
  });
  ({ render } = createRequire(import.meta.url)(bundle));
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

const artifact = {
  evaluation: 'ml_primitives', cases_passed: 3, cases_total: 4,
  cases: [
    { case_id: 'typical', passed: true, error: null },
    { case_id: 'constant_rows', passed: false, error: 'mismatch' },
  ],
  properties: [{ name: 'no NaN on constant rows', passed: false }],
  static_findings: [{ name: 'batch axis loop', line: 3 }],
};

test('graded review shows score, cases, checks and unscored code signals', () => {
  const html = render({
    configJson: { scoring_available: true }, submitted: true, currentScore: 75,
    currentArtifact: artifact, onNextRound: () => {},
  });
  assert.match(html, /data-testid="ml-review-summary"/);
  assert.match(html, /75\.0%/);
  assert.match(html, /3\/4 cases passed every check/);
  assert.match(html, /constant_rows/);
  assert.match(html, /Wrong values/);
  assert.match(html, /Code signals \(not scored\): batch axis loop/);
  assert.match(html, /Next round/);
  assert.doesNotMatch(html, /Scoring is currently unavailable/);
});

test('final graded round offers View report', () => {
  const html = render({
    configJson: { scoring_available: true }, submitted: true, currentScore: 100,
    currentArtifact: { ...artifact, cases_passed: 4 }, onNextRound: () => {}, sessionComplete: true,
  });
  assert.match(html, /View report/);
});

test('scoring available: submit is graded, not "ungraded"', () => {
  const html = render({ configJson: { scoring_available: true } });
  assert.match(html, /Submit solution/);
  assert.doesNotMatch(html, /ungraded|Scoring is currently unavailable/);
});

test('without an executor the ungraded storage path stays explicit', () => {
  const html = render({ configJson: {} });
  assert.match(html, /Scoring is currently unavailable/);
  assert.match(html, /Submit solution \(ungraded\)/);
});
