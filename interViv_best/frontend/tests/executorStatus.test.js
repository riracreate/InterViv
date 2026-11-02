// Problems page executor pill: tells the candidate before they write code
// whether Run/Submit can work.
import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-executor-status-'));
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
        import { ExecutorStatus } from './src/pages/Problems.jsx';
        export function render(execution) {
          return renderToStaticMarkup(<ExecutorStatus execution={execution} />);
        }
      `,
    },
    bundle: true,
    platform: 'node',
    format: 'cjs',
    outfile: bundle,
    loader: { '.css': 'empty' },
    define: { 'process.env.NODE_ENV': '"production"' },
    logLevel: 'silent',
  });
  ({ render } = createRequire(import.meta.url)(bundle));
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

const languages = [
  { id: 'python', label: 'Python 3.12', available: true },
  { id: 'java', label: 'Java 15', available: false },
];

test('executor on lists only the available languages', () => {
  const html = render({ available: true, languages });
  assert.match(html, /Code execution on: Python 3\.12\./);
  assert.doesNotMatch(html, /Java 15/);
  assert.match(html, /color-success/);
});

test('executor off says drafts save but Run/Submit need the executor', () => {
  const html = render({ available: false, languages: languages.map((l) => ({ ...l, available: false })) });
  assert.match(html, /Code execution is off/);
  assert.match(html, /--with-executor/);
  assert.match(html, /color-warn/);
});

test('unknown status does not claim execution is off', () => {
  const html = render({ available: false, unknown: true });
  assert.match(html, /Could not check code execution/);
  assert.doesNotMatch(html, /Code execution is off/);
});
