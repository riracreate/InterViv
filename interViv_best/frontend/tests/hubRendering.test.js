import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { safeNext } from '../src/lib/authRedirect.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-hub-render-'));
let render;
try {
  const bundle = path.join(scratch, 'render.cjs');
  await build({
    stdin: { resolveDir: root, loader: 'jsx', contents: `
      import React from 'react';
      import { renderToStaticMarkup } from 'react-dom/server';
      import { MemoryRouter } from 'react-router-dom';
      import { HomeContent } from './src/pages/Home.jsx';
      import { ProgressContent } from './src/pages/Progress.jsx';
      import AppNav from './src/components/AppNav.jsx';
      export function render(page, data) {
        return renderToStaticMarkup(<MemoryRouter initialEntries={['/'+page]}><AppNav />{page === 'home' ? <HomeContent data={data} /> : <ProgressContent data={data} />}</MemoryRouter>);
      }
    ` },
    bundle: true, platform: 'node', format: 'cjs', outfile: bundle,
    loader: { '.css': 'empty' }, define: { 'process.env.NODE_ENV': '"production"' }, logLevel: 'silent',
  });
  render = createRequire(import.meta.url)(bundle).render;
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
const fresh = { user: { id: 'u1', name: 'Test User' }, skills: [], history: [], scored_session_count: 0, readiness: null, resumable_session: null, target: null, learning_signals: { elo_deltas: [], revisit_rates: [], roadmap_completion: {} } };

test('new-user Home renders connected actions without a false continue button or sample statistics', () => {
  const html = render('home', fresh);
  for (const phrase of ['Hello,', 'Test.', 'Start practicing', 'Help me choose a path', 'Prepare', 'Target', 'Apply', 'Guide']) assert.ok(html.includes(phrase), phrase);
  assert.doesNotMatch(html, /Continue practice|Aditya|64%|round_plan|POST \/|Try next/);
  for (const match of html.matchAll(/href="([^"]+)"/g)) {
    const href = match[1].replaceAll('&amp;', '&');
    if (href.startsWith('#')) continue;
    assert.equal(safeNext(href, 'http://127.0.0.1:5173'), href, `Unconnected link: ${href}`);
  }
});
test('Continue practice appears only for a server-confirmed session', () => {
  const html = render('home', { ...fresh, resumable_session: { session_id: 'owned-123' } });
  assert.match(html, /Continue practice/);
  assert.match(html, /href="\/interview\/owned-123"/);
});
test('empty Progress states remain unmeasured with no fabricated session history', () => {
  const html = render('dashboard', fresh);
  assert.match(html, /Not measured/);
  assert.match(html, /No scored sessions yet/);
  assert.doesNotMatch(html, /View report|64%|41%/);
});
test('Progress renders measured zeros and real report links independently of untested skills', () => {
  const html = render('dashboard', { ...fresh, readiness: 0, target: { company_name: 'Test Company', role_title: 'Test Role', tested_skill_count: 1, required_skill_count: 2 }, scored_session_count: 1, skills: [{ name: 'DBMS', attempts: 1, current_score: 0, current_elo: 1000 }, { name: 'Python', attempts: 0, current_score: 0 }], history: [{ session_id: 'scored-123', status: 'completed', skills: ['DBMS'], round_types: ['mcq'], completed_rounds: 1, total_rounds: 1, average_score: 0 }] });
  assert.match(html, /0%/);
  assert.match(html, /Not measured/);
  assert.match(html, /href="\/dashboard\/scored-123"/);
  assert.doesNotMatch(html, /technical_short_answer|round_plan/);
});
