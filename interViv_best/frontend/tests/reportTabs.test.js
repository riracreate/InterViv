// Phase 6: the session report is an executive summary plus three tabs.
import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { mapRealDataToDashboard } from '../src/lib/dashboardMapping.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-report-tabs-'));
const bundle = path.join(scratch, 'render.cjs');
let mod;
try {
  await build({
    stdin: {
      resolveDir: root,
      loader: 'tsx',
      contents: `
        import React from 'react';
        import { renderToStaticMarkup } from 'react-dom/server';
        import { REPORT_TABS, ExecutiveSummary } from './src/pages/Dashboard.tsx';
        export { REPORT_TABS };
        export const renderSummary = (data) => renderToStaticMarkup(<ExecutiveSummary data={data} onPractice={() => {}} />);
      `,
    },
    outfile: bundle, bundle: true, platform: 'node', format: 'cjs',
    define: { 'process.env.NODE_ENV': '"production"' }, logLevel: 'silent',
  });
  mod = createRequire(import.meta.url)(bundle);
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

const SESSION = {
  session_id: 's1', status: 'completed', skill: 'DBMS', skills: ['DBMS', 'Python'], total_rounds: 2,
  averages: { final_score: 62 }, topic_scores: { DBMS: 48, Python: 76 },
  breakdown: { Good: 1, Average: 0, Poor: 1 },
  rounds: [
    { round: 1, skill: 'DBMS', final_score: 48, round_type: 'technical_short_answer', question: 'ACID?', feedback: { next_step: 'Define isolation.' } },
    { round: 2, skill: 'Python', final_score: 76, round_type: 'technical_short_answer', question: 'GIL?', feedback: { next_step: 'Good.' } },
  ],
  next_step: 'Review isolation levels.',
};

test('three report tabs in the planned order', () => {
  assert.deepEqual(mod.REPORT_TABS.map((t) => t.label), ['Overview & readiness', 'Round review', 'Skills & next steps']);
});

test('executive summary shows one strength, one weakness and a practice action for the weakest skill', () => {
  const html = mod.renderSummary(mapRealDataToDashboard(SESSION));
  assert.match(html, /data-testid="report-summary"/);
  assert.match(html, /Strong Round/);
  assert.match(html, /Round to Revisit/);
  assert.match(html, /Review isolation levels\./);
  assert.match(html, /Practice DBMS, Python →/); // weakest measured skill first
});

test('report page uses tabs, keeps scoring internals collapsed, and has no C4 jargon', () => {
  const src = readFileSync(path.join(root, 'src/pages/Dashboard.tsx'), 'utf8');
  assert.match(src, /role="tablist"/);
  assert.match(src, /searchParams\.get\("tab"\)/);
  assert.match(src, /<details className="glass-panel rounded-3xl p-5" data-testid="report-scoring-details">/);
  const cards = readFileSync(path.join(root, 'src/components/dashboard/FeedbackCards.tsx'), 'utf8');
  assert.doesNotMatch(cards, /C4/);
});
