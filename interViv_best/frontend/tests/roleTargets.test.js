import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import {
  ROLE_ONLY_TARGETS,
  coreCompetencies,
  roleInterviewPayload,
  rolePlanRequest,
  roleTargetFromContext,
  roleTargetLabel,
  roleTargetUpdate,
  slotLabel,
  slotNote,
  stagedTurnNote,
} from '../src/lib/roleTargets.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const COMPANY_NAMES = ['TCS', 'Infosys', 'Wipro', 'Amazon', 'Microsoft', 'Accenture', 'Google', 'Meta'];

async function bundleHome(flag) {
  const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-role-targets-'));
  try {
    const outfile = path.join(scratch, 'render.cjs');
    await build({
      stdin: { resolveDir: root, loader: 'jsx', contents: `
        import React from 'react';
        import { renderToStaticMarkup } from 'react-dom/server';
        import { MemoryRouter } from 'react-router-dom';
        import { HomeContent } from './src/pages/Home.jsx';
        export function render(data) {
          return renderToStaticMarkup(<MemoryRouter initialEntries={['/home']}><HomeContent data={data} /></MemoryRouter>);
        }
      ` },
      bundle: true, platform: 'node', format: 'cjs', outfile, logLevel: 'silent',
      loader: { '.css': 'empty' },
      define: {
        'process.env.NODE_ENV': '"production"',
        ...(flag ? { 'import.meta.env': '{"VITE_ROLE_ONLY_TARGETS":"1"}' } : {}),
      },
    });
    return createRequire(import.meta.url)(outfile).render;
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
}

const withCompanyTarget = {
  user: { id: 'u1', name: 'Test User', target_company_id: 'amazon', target_role_id: 'amazon_sde1' },
  skills: [], history: [], scored_session_count: 0, readiness: null, resumable_session: null,
  target: { role_id: 'amazon_sde1', role_title: 'SDE-1', company_name: 'Amazon' },
  learning_signals: { elo_deltas: [], revisit_rates: [], roadmap_completion: {} },
};

test('the flag is off unless VITE_ROLE_ONLY_TARGETS is 1', () => {
  assert.equal(ROLE_ONLY_TARGETS, false);
});

test('flag off: Home keeps the company target exactly as before', async () => {
  const html = (await bundleHome(false))(withCompanyTarget);
  assert.match(html, /Choose company &amp; role/);
  assert.match(html, /Amazon · SDE-1/);
  assert.doesNotMatch(html, /data-testid="role-selector"/);
});

test('flag on: Home shows the role picker and no company names', async () => {
  const html = (await bundleHome(true))(withCompanyTarget);
  assert.match(html, /Choose your role/);
  assert.match(html, /Choose a role &amp; level/);
  assert.match(html, /data-testid="role-selector"/);
  assert.doesNotMatch(html, /data-testid="company-selector"/);
  assert.doesNotMatch(html, /Choose company/);
  for (const name of COMPANY_NAMES) assert.doesNotMatch(html, new RegExp(`\\b${name}\\b`), name);
});

function companySelectorGuards(rel) {
  const text = readFileSync(path.join(root, rel), 'utf8');
  const source = ts.createSourceFile(rel, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
  const results = [];
  const visit = node => {
    if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node))
        && node.tagName.getText(source) === 'CompanySelector') {
      let guarded = false;
      for (let up = node.parent; up; up = up.parent) {
        if ((ts.isConditionalExpression(up) || ts.isBinaryExpression(up))
            && up.getText(source).includes('ROLE_ONLY_TARGETS')
            && !up.getText(source).startsWith('<')) {
          guarded = true;
          break;
        }
      }
      results.push(guarded);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return results;
}

test('flag on: every company picker on Practice, Home and Upload sits behind ROLE_ONLY_TARGETS', () => {
  for (const rel of ['src/pages/Practice.jsx', 'src/pages/Home.jsx', 'src/pages/Upload.jsx']) {
    const guards = companySelectorGuards(rel);
    assert.ok(guards.length > 0, `${rel} still renders the company picker when the flag is off`);
    assert.ok(guards.every(Boolean), `${rel}: a CompanySelector is not behind ROLE_ONLY_TARGETS`);
    assert.match(readFileSync(path.join(root, rel), 'utf8'), /<RoleSelector/);
  }
});

test('role target helpers read and write the role-only target', () => {
  assert.deepEqual(roleTargetUpdate('data-analyst', 'mid'), { role_target: { role_id: 'data-analyst', level: 'mid' } });
  const target = { role_id: 'data-analyst', level: 'intern', title: 'Data Analyst' };
  assert.deepEqual(roleTargetFromContext({ target: { company_id: null, role_target: target } }), target);
  assert.equal(roleTargetFromContext({ target: { company_id: 'amazon', role_id: 'amazon_sde1' } }), null);
  assert.equal(roleTargetLabel(target), 'Data Analyst · Intern');
  assert.equal(roleTargetLabel(null), '');
});

test('the start payload is a staged role interview with no company fields', () => {
  const payload = roleInterviewPayload({
    roleId: 'backend-engineer', level: 'junior', length: 'full', candidateId: 'cand-1', useResume: true,
    core: ['database-management-systems-dbms', 'backend-programming-python-java'],
  });
  assert.deepEqual(payload, {
    flow_version: 'staged_v1', preset: 'full', skills: [], practice_mode: 'coached_practice',
    allow_optional_follow_ups: true, candidate_id: 'cand-1',
    role_interview: {
      role_id: 'backend-engineer', level: 'junior', use_resume: true,
      core_competencies: ['database-management-systems-dbms', 'backend-programming-python-java'],
    },
  });
  assert.equal('target_company_id' in payload, false);
  assert.equal(roleInterviewPayload({ roleId: 'ui-ux-designer', useResume: true }).role_interview.use_resume, false);
  assert.throws(() => roleInterviewPayload({ roleId: '' }), /Choose a role/);
  assert.deepEqual(rolePlanRequest({ roleId: 'qa-test-engineer', level: 'mid', length: 'quick', candidateId: 'c', useResume: false }),
    { role_id: 'qa-test-engineer', level: 'mid', length: 'quick' });
});

test('plan slots say why they do or do not count toward the score', () => {
  const opener = { kind: 'opener', stage: 'warm_up', reason: 'Tell me a little about yourself.', scored: false, practice_only: false };
  const banked = { kind: 'core', stage: 'core', competency_id: 'sql', reason: 'SQL: core skill', scored: true, content: 'bank' };
  const pending = { kind: 'core', stage: 'core', competency_id: 'docker', reason: 'Docker: core skill', scored: false, content: 'auto_checked_bundle' };
  const empty = { kind: 'core', stage: 'practice', competency_id: 'stats', reason: 'Statistics: no question bank', scored: false, practice_only: true, content: 'none' };
  const scenario = { kind: 'scenario', stage: 'practice', reason: 'Scenario', scored: false, practice_only: true };
  assert.equal(slotNote(opener), 'not scored');
  assert.equal(slotNote(banked), '');
  assert.equal(slotNote(pending), 'feedback only · question awaiting review');
  assert.equal(slotNote(empty), 'practice only · no question bank for this skill yet');
  assert.equal(slotNote(scenario), 'practice only · not scored');
  assert.deepEqual(slotLabel(opener), { stage: 'Opener', text: 'Tell me a little about yourself.', note: 'not scored' });
  assert.deepEqual(coreCompetencies([opener, banked, pending, empty, scenario]), ['sql', 'docker', 'stats']);
});

test('staged role turns are labelled when unscored', () => {
  assert.equal(stagedTurnNote('practice'), 'Practice only · not scored');
  assert.equal(stagedTurnNote('warm_up'), 'Not scored');
  assert.equal(stagedTurnNote('behavioural'), 'Not scored');
  assert.equal(stagedTurnNote('core'), '');
});
