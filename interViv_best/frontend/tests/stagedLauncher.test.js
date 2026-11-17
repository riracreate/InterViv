import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import ts from 'typescript';
import { createStagedLauncherController, LAUNCHER_SKILLS, recentLauncherSkills } from '../src/lib/stagedLauncher.js';
import { writeScoped } from '../src/lib/accountStorage.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
class MemoryStorage {
  data = new Map();
  getItem(key) { return this.data.get(key) ?? null; }
  setItem(key, value) { this.data.set(key, value); }
}
test.beforeEach(() => { globalThis.localStorage = new MemoryStorage(); });
test.afterEach(() => { delete globalThis.localStorage; });

const bundled = await build({ stdin: { resolveDir: root, loader: 'jsx', contents: `
  import React from 'react';
  import { renderToStaticMarkup } from 'react-dom/server';
  import StagedLauncherCard from './src/components/staged/StagedLauncherCard.jsx';
  import StagedInterviewLauncher from './src/components/staged/StagedInterviewLauncher.jsx';
  export const card = state => renderToStaticMarkup(<StagedLauncherCard {...state} />);
  export const launcher = userId => renderToStaticMarkup(<StagedInterviewLauncher userId={userId} />);
` }, bundle: true, platform: 'node', format: 'cjs', write: false, logLevel: 'silent',
  define: { 'process.env.NODE_ENV': '"production"' } });
const module = { exports: {} };
new Function('require', 'module', 'exports', bundled.outputFiles[0].text)(createRequire(path.join(root, 'package.json')), module, module.exports);
const { card, launcher } = module.exports;

test('Practice mounts one launcher at the top level without mode or completion gates', () => {
  const source = ts.createSourceFile('Practice.jsx', readFileSync(path.join(root, 'src/pages/Practice.jsx'), 'utf8'),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
  const launchers = [];
  const visit = node => {
    if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(source) === 'StagedInterviewLauncher') launchers.push(node);
    ts.forEachChild(node, visit);
  };
  visit(source);
  assert.equal(launchers.length, 1);
  const node = launchers[0];
  assert.match(node.parent.openingElement.getText(source), /data-testid="staged-launchers"/);
  for (let ancestor = node.parent; ancestor && !ts.isReturnStatement(ancestor); ancestor = ancestor.parent) {
    assert.equal(ts.isConditionalExpression(ancestor) || ts.isBinaryExpression(ancestor), false,
      'Launcher must not be nested in a mode/history condition');
  }
  const tracks = source.text.indexOf('data-testid="practice-tracks"');
  assert.ok(tracks > node.pos, 'Top-level launcher sits above the existing practice options');
});

test('first Practice load always shows a usable Quick button and the first available skill', () => {
  const html = launcher('new-user');
  assert.match(html, /Quick interview/);
  assert.match(html, /Start Quick interview/);
  assert.match(html, /data-testid="quick-interview-skills"/);
  assert.match(html, new RegExp(`Remove ${LAUNCHER_SKILLS[0]}`));
  assert.doesNotMatch(html, /disabled=""|Session mode|Rounds per skill/);
});

test('returning after a completed staged session keeps Quick visible and defaults to its skills', async () => {
  const controller = createStagedLauncherController({ userId: 'returning', api: {
    fetchAccountOverview: async () => ({ history: [{ session_id: 'done', status: 'completed',
      flow_version: 'staged_v1', skills: ['Python', 'HR'], created_at: '2026-11-16T09:00:00Z' }] }),
  } });
  await controller.restoreSkills();
  assert.deepEqual(controller.snapshot().skills, ['Python']);
  assert.match(card(controller.snapshot()), /Start Quick interview/);
  assert.doesNotMatch(card(controller.snapshot()), /disabled=""/);
});

test('successful launch persists skills across refresh without leaking them to another account', async () => {
  const controller = createStagedLauncherController({ userId: 'owner', api: {
    fetchAvailability: async () => ({ available: true }), startSession: async () => ({ session_id: 'new' }),
  } });
  controller.selectSkills(['Python', 'SQL']);
  assert.equal(await controller.start(), true);
  const refreshed = createStagedLauncherController({ userId: 'owner' });
  assert.deepEqual(refreshed.snapshot().skills, ['Python', 'SQL']);
  assert.match(launcher('owner'), /Start Quick interview/);
  assert.match(launcher('owner'), /Remove Python/);
  assert.doesNotMatch(launcher('owner'), /disabled=""/);
  assert.deepEqual(recentLauncherSkills('another-user'), [LAUNCHER_SKILLS[0]]);
});

test('a newer server session wins over an older saved launcher choice', () => {
  writeScoped('local', 'owner', 'staged-interview-skills', { skills: ['Python'], startedAt: '2026-11-15T09:00:00Z' });
  assert.deepEqual(recentLauncherSkills('owner', { history: [{ skills: ['SQL'], created_at: '2026-11-16T09:00:00Z' }] }), ['SQL']);
});

test('late history cannot replace skills the candidate has already selected', async () => {
  let release;
  const overview = new Promise(resolve => { release = resolve; });
  const controller = createStagedLauncherController({ userId: 'owner', api: { fetchAccountOverview: () => overview } });
  const restoring = controller.restoreSkills();
  controller.selectSkills(['Python']);
  release({ history: [{ skills: ['SQL'], created_at: '2026-11-16T09:00:00Z' }] });
  await restoring;
  assert.deepEqual(controller.snapshot().skills, ['Python']);
});

test('card sends exactly the fixed coached Quick payload, independent of legacy settings', async () => {
  const calls = [];
  const navigated = [];
  const controller = createStagedLauncherController({ userId: 'owner',
    practiceMode: 'assessment', targetRoleId: 'legacy-role', candidateId: 'legacy-resume',
    onStarted: value => navigated.push(value.session_id), api: {
      fetchAvailability: async body => { calls.push(['availability', body]); return { available: true }; },
      startSession: async body => { calls.push(['start', body]); return { session_id: 'created' }; },
    } });
  controller.selectSkills(['python', 'SQL', 'Python']);
  assert.equal(await controller.start(), true);
  const expected = { flow_version: 'staged_v1', preset: 'quick', skills: ['Python', 'SQL'],
    target_role_id: null, target_company_id: null, practice_mode: 'coached_practice', allow_optional_follow_ups: true };
  assert.deepEqual(calls, [['availability', expected], ['start', expected]]);
  assert.deepEqual(navigated, ['created']);
});

test('unavailable server reason appears on the card and Start remains available for retry', async () => {
  let starts = 0;
  const controller = createStagedLauncherController({ userId: 'owner', api: {
    fetchAvailability: async () => ({ available: false, blocks: [{ available: false, reason: 'No reviewed bundle for Python.' }] }),
    startSession: async () => { starts++; },
  } });
  assert.equal(await controller.start(), false);
  assert.equal(starts, 0);
  const html = card(controller.snapshot());
  assert.match(html, /role="alert"/);
  assert.match(html, /No reviewed bundle for Python\./);
  assert.match(html, /Start Quick interview/);
  assert.doesNotMatch(html, /disabled=""/);
});

test('start-time rejection and top-level availability reasons are preserved verbatim', async () => {
  let rejectAtStart = false;
  const controller = createStagedLauncherController({ userId: 'owner', api: {
    fetchAvailability: async () => rejectAtStart ? { available: true } : { available: false, reason: 'Inventory is unavailable now.' },
    startSession: async () => { throw Object.assign(new Error('No content for these skills.'), { status: 422 }); },
  } });
  await controller.start();
  assert.equal(controller.snapshot().error, 'Inventory is unavailable now.');
  rejectAtStart = true;
  await controller.start();
  assert.equal(controller.snapshot().error, 'No content for these skills.');
});

test('missing history and empty skills explain problems without hiding or silently disabling Start', async () => {
  let probes = 0;
  const controller = createStagedLauncherController({ userId: 'owner', api: {
    fetchAccountOverview: async () => { throw new Error('History offline'); },
    fetchAvailability: async () => { probes++; },
  } });
  await controller.restoreSkills();
  assert.match(card(controller.snapshot()), /Recent skills could not be loaded/);
  assert.doesNotMatch(card(controller.snapshot()), /disabled=""/);
  controller.selectSkills([]);
  await controller.start();
  assert.equal(controller.snapshot().error, 'Select at least one skill.');
  assert.equal(probes, 0);
});

test('double clicks issue one start and late responses cannot navigate after leaving the card', async () => {
  let release;
  const response = new Promise(resolve => { release = resolve; });
  let posts = 0;
  const navigated = [];
  const controller = createStagedLauncherController({ userId: 'owner', onStarted: value => navigated.push(value), api: {
    fetchAvailability: async () => ({ available: true }),
    startSession: async () => { posts++; return response; },
  } });
  const pending = controller.start();
  assert.equal(await controller.start(), false);
  assert.match(card(controller.snapshot()), /Starting…/);
  controller.dispose();
  release({ session_id: 'created' });
  assert.equal(await pending, false);
  assert.equal(posts, 1);
  assert.deepEqual(navigated, []);
});
