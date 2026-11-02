// System-design calibration panel: self-ratings vs what the notes mention (advisory).
import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-sd-calibration-'));
let render;
try {
  const bundle = path.join(scratch, 'render.cjs');
  await build({
    stdin: {
      resolveDir: root,
      loader: 'jsx',
      contents: `
        import React from 'react';
        import { renderToStaticMarkup } from 'react-dom/server';
        import { CalibrationPanel } from './src/components/SystemDesignRound.jsx';
        export function render(calibration) {
          return renderToStaticMarkup(<CalibrationPanel calibration={calibration} />);
        }
      `,
    },
    bundle: true, platform: 'node', format: 'cjs', outfile: bundle,
    loader: { '.css': 'empty' }, define: { 'process.env.NODE_ENV': '"production"' }, logLevel: 'silent',
  });
  ({ render } = createRequire(import.meta.url)(bundle));
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

test('overconfident criterion lists what the notes did not mention', () => {
  const html = render({
    available: true,
    note: 'Advisory; not part of the score.',
    criteria: [
      { id: 'scale', name: 'Scale and reliability', self_rating: 5, evidence_level: 2.3, overconfident: true, not_mentioned: ['race conditions', 'store outage'] },
      { id: 'requirements', name: 'Requirements clarity', self_rating: 4, evidence_level: 5, overconfident: false, not_mentioned: [] },
    ],
  });
  assert.match(html, /Scale and reliability/);
  assert.match(html, /you rated 5 · notes show 2\.3/);
  assert.match(html, /Not mentioned: race conditions, store outage/);
  assert.match(html, /not part of the score/);
});

test('unavailable calibration explains why, and absent calibration renders nothing', () => {
  assert.match(render({ available: false, reason: 'Design notes are too short to compare with your ratings.' }), /too short/);
  assert.equal(render(undefined), '');
});
