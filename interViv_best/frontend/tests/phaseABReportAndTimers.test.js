// Phase AB: Z-F01 fresh-round timers and Z-F02 session report, rendered from
// real API payloads emitted against a migrated SQLite store (the store the
// browser defects were observed on). Rounds are rendered through the
// deep-link path the browser takes: GET /session → interviewStateFromSession
// → Interview.
import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { mapRealDataToDashboard } from '../src/lib/dashboardMapping.js';

// Phase Z ran at +05:30, where an offset-less UTC deadline reads as 5.5h ago.
process.env.TZ = 'Asia/Kolkata';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(testDir, '..');
const appRoot = path.resolve(root, '..');
const localPython = path.join(appRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const payloads = JSON.parse(execFileSync(
  existsSync(localPython) ? localPython : 'python3',
  [path.join(testDir, 'helpers', 'emit_phase_ab_payloads.py')],
  {
    cwd: appRoot,
    encoding: 'utf8',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
    maxBuffer: 64 * 1024 * 1024,
  },
));

const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-phase-ab-render-'));
let renderRoundRaw;
let renderReport;
try {
  const bundle = path.join(scratch, 'render.cjs');
  await build({
    stdin: {
      resolveDir: root,
      loader: 'jsx',
      contents: `
        import React from 'react';
        import { renderToStaticMarkup } from 'react-dom/server';
        import { MemoryRouter, Routes, Route } from 'react-router-dom';
        import Interview from './src/pages/Interview.jsx';
        import { interviewStateFromSession } from './src/lib/accountOverview.js';
        import { ReviewSummary } from './src/components/dashboard/ReviewSummary.tsx';
        import { ScoreHero } from './src/components/dashboard/ScoreHero.tsx';
        export function renderRound(session, extra) {
          const state = { ...interviewStateFromSession(session), ...extra };
          return renderToStaticMarkup(
            <MemoryRouter initialEntries={['/interview/' + session.session_id]}>
              <Routes><Route path="/interview/:sessionId" element={<Interview sessionState={state} />} /></Routes>
            </MemoryRouter>
          );
        }
        export function renderReport(mapped) {
          return renderToStaticMarkup(
            <MemoryRouter>
              <ScoreHero accentRingClass="" accentTextClass="" overallScore={mapped.overall.score}
                gradeLabel={mapped.overall.gradeLabel} deltaLabel={mapped.overall.deltaLabel}
                sessionTitle="" role="" dateLabel="" durationLabel="" skillFocus="" />
              <ReviewSummary {...mapped.reviewSummary} />
            </MemoryRouter>
          );
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
    plugins: [{
      name: 'omit-camera-models-in-static-render',
      setup(builder) {
        builder.onLoad({ filter: /[/\\]lib[/\\]engagement\.js$/ }, () => ({
          contents: 'export const classifyFrame = async () => null; export const computeEngagementDelta = () => 0; export const loadModels = async () => false; export const modeOfLabels = () => null;',
          loader: 'js',
        }));
        // Unify-shell coding editor pulls monaco ESM that esbuild cannot resolve
        // in this node_modules layout; static timer/report tests do not need it.
        builder.onLoad({ filter: /[/\\]lib[/\\]codingEditor\.js$/ }, () => ({
          contents: 'export const monaco = { editor: { defineTheme() {} } };',
          loader: 'js',
        }));
      },
    }],
  });
  ({ renderRound: renderRoundRaw, renderReport } = createRequire(import.meta.url)(bundle));
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

function renderRound(session, extra = {}) {
  const previous = globalThis.window;
  globalThis.window = {};
  try {
    return renderRoundRaw(session, extra);
  } finally {
    if (previous === undefined) delete globalThis.window;
    else globalThis.window = previous;
  }
}

// Every mm:ss clock reading on the page, in seconds.
function readings(html) {
  return [...html.matchAll(/(?<![\d:])(\d{1,3}):([0-5]\d)(?![\d:])/g)]
    .map((m) => Number(m[1]) * 60 + Number(m[2]));
}

function buttonAttributes(html, label) {
  const match = html.match(new RegExp(`<button([^>]*)>(?:(?!</button>)[\\s\\S])*${label}`));
  assert.ok(match, `no button labelled ${label}`);
  return match[1];
}
const DISABLED = /(?:^|\s)disabled=""/; // the attribute, not the `disabled:` class variant

function assertCountingDown(html, category) {
  const budget = payloads.durations[category] * 60;
  const [seconds, ...others] = readings(html);
  assert.deepEqual(others, [], `one timer reading on the ${category} page`);
  assert.ok(seconds > budget - 120 && seconds <= budget, `${category}: ${seconds}s of ${budget}s`);
}

// Media categories open on calibration (Z-F07, unchanged); Skip is modelled
// the way the page records it.
const SKIPPED = { engagementCalibrationSkipped: true };

test('fresh verbal round counts down from its configured duration with Submit enabled', () => {
  const html = renderRound(payloads.fresh.verbal);
  assertCountingDown(html, 'verbal');
  assert.doesNotMatch(buttonAttributes(html, 'Submit Round'), DISABLED);
});

test('fresh oa round counts down from its configured duration with Submit enabled', () => {
  const html = renderRound(payloads.fresh.oa);
  assertCountingDown(html, 'oa');
  assert.doesNotMatch(buttonAttributes(html, 'Submit Round'), DISABLED);
});

test('fresh sql round counts down from its configured duration with Submit enabled', () => {
  const html = renderRound(payloads.fresh.sql, SKIPPED);
  assertCountingDown(html, 'sql');
  assert.doesNotMatch(buttonAttributes(html, 'Submit Final Solution'), DISABLED);
});

test('fresh coding round counts down from its configured duration with Submit enabled', () => {
  const html = renderRound(payloads.fresh.coding, SKIPPED);
  assertCountingDown(html, 'coding');
  // Unify CodingRound labels the action "Submit" and disables it until the
  // editor finishes loading. A static render never runs that effect; Z-F01
  // is the countdown, not the loaded-term.
  assert.doesNotMatch(html, /time window has ended/);
  assert.match(html, />Submit</);
});

test('fresh system_design round counts down from its configured duration with Submit enabled', () => {
  const html = renderRound(payloads.fresh.system_design, SKIPPED);
  assertCountingDown(html, 'system_design');
  // New rounds are content-evaluated (practice estimate); ratings are optional.
  assert.doesNotMatch(buttonAttributes(html, 'Submit design'), DISABLED);
});

test('fresh ml_primitives round counts down from its configured duration and Submit is not time-locked', () => {
  const html = renderRound(payloads.fresh.ml_primitives);
  assertCountingDown(html, 'ml_primitives');
  // Submit's time term is `seconds <= 0`, the same condition that prints
  // this copy. (A static render has not run draft recovery, so the separate
  // `loaded` term still disables the button here; the browser run covers it.)
  assert.doesNotMatch(html, /time window has ended/);
});

test('fresh interview round shows its per-question timer, not an ended state', () => {
  const html = renderRound(payloads.fresh.interview, SKIPPED);
  assert.match(html, /Time left in this round/);
  // The configured server deadline drives the clock (it used to be ignored
  // in favour of a fixed 02:00 that reset on every refresh).
  assertCountingDown(html, 'interview');
  // Submit waits for an answer (canSubmit needs a transcript), not for time.
});

test('genuinely expired ml_primitives round shows ended with Submit disabled', () => {
  const html = renderRound(payloads.expired.ml_primitives);
  assert.deepEqual(readings(html), [0]);
  assert.match(html, /time window has ended/);
  assert.match(buttonAttributes(html, 'Submit solution \\(ungraded\\)'), DISABLED);
});

test('genuinely expired coding round shows 00:00', () => {
  assert.deepEqual(readings(renderRound(payloads.expired.coding, SKIPPED)), [0]);
});

test('Coding header and round timer agree: one deadline reading, no technical 02:00', () => {
  // Unify-shell treats coding as non-camera, so there is no calibration
  // screen and no technical 02:00 header. The round clock is the only timer.
  const html = renderRound(payloads.fresh.coding);
  assert.doesNotMatch(html, /Calibration|Time left in this round|02:00/);
  assertCountingDown(html, 'coding');
});

test('expired unavailable round: report has no average, verdict, skill percentage or remedial plan', () => {
  const mapped = mapRealDataToDashboard(payloads.report_unscored);
  assert.equal(mapped.overall.score, null);
  assert.equal(mapped.overall.gradeLabel, 'Not measured');
  assert.equal(mapped.overall.deltaLabel, 'No scored rounds');
  assert.deepEqual(mapped.layers, []);
  assert.deepEqual(mapped.radar, []);
  assert.deepEqual(mapped.reviewSummary.prioritySkills, []);
  assert.deepEqual(mapped.highlights, { strengths: [], weaknesses: [] });
  assert.doesNotMatch(mapped.feedbackCards.map((c) => c.body).join(' '), /(?<!\d)0%/);
  const html = renderReport(mapped);
  assert.doesNotMatch(html, /Needs Work|avg score|Rebuild|Recommended action plan|Skill priority|completed all rounds|(?<!\d)0%/);
  assert.match(html, />—</);
});

test('expired unavailable round stays visible in the report as unscored', () => {
  const mapped = mapRealDataToDashboard(payloads.report_unscored);
  assert.deepEqual(mapped.reviewSummary.unscored, [{ round: 1, label: 'coding unavailable' }]);
  const html = renderReport(mapped);
  assert.match(html, /Round 1 · Unscored \(coding unavailable\)/);
  assert.match(html, /1 round not evaluated \(coding unavailable\); excluded from every average/);
});

test('a genuinely scored zero still renders as 0 and Needs Work', () => {
  const mapped = mapRealDataToDashboard(payloads.report_zero);
  assert.equal(mapped.overall.score, 0);
  assert.equal(mapped.overall.gradeLabel, 'Needs Work');
  assert.equal(mapped.overall.deltaLabel, '0% avg score');
  assert.deepEqual(mapped.reviewSummary.unscored, []);
  const html = renderReport(mapped);
  assert.match(html, /Needs Work/);
  assert.match(html, />0</);
  assert.doesNotMatch(html, /Unscored/);
});
