// Phase 4: wizard steps, account-scoped storage, Back targets, error kinds,
// Practice prefill and nav prompts. Pure modules only.
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  EMPTY_WIZARD,
  previousStep,
  resolveWizardStep,
  restoreWizard,
  serializeWizard,
  stepFromSearch,
} from '../src/lib/uploadWizard.js';
import {
  clearSessionScopedState,
  readScoped,
  scopedKey,
  writeScoped,
} from '../src/lib/accountStorage.js';
import { backDestination, gapAnalysisPath, hasInAppHistory, roadmapPath } from '../src/lib/backNavigation.js';
import { accountLoadAction, errorFromFetchFailure, errorKind, isRetryable } from '../src/lib/requestErrors.js';
import { applyTargetPrefill, roleRequiredSkills } from '../src/lib/practiceBuilder.js';
import { isNavActive } from '../src/lib/appNav.js';

class MemoryStorage {
  constructor() { this.map = new Map(); }
  get length() { return this.map.size; }
  key(i) { return [...this.map.keys()][i] ?? null; }
  getItem(k) { return this.map.has(k) ? this.map.get(k) : null; }
  setItem(k, v) { this.map.set(k, String(v)); }
  removeItem(k) { this.map.delete(k); }
}

test('?step is authoritative but resolves to the nearest reachable step', () => {
  assert.equal(stepFromSearch('?step=skills'), 'skills');
  assert.equal(stepFromSearch('?step=bogus'), null);
  const empty = { ...EMPTY_WIZARD };
  assert.equal(resolveWizardStep('domains', empty), 'upload');
  const parsed = { ...EMPTY_WIZARD, candidateId: 'c1', extractedSkills: ['SQL'], selectedSkills: [] };
  assert.equal(resolveWizardStep('domains', parsed), 'skills');
  assert.equal(resolveWizardStep('skills', parsed), 'skills');
  const ready = { ...parsed, selectedSkills: ['SQL'] };
  assert.equal(resolveWizardStep('domains', ready), 'domains');
  // Domain presets reach skills without a resume.
  assert.equal(resolveWizardStep('skills', { ...EMPTY_WIZARD, extractedSkills: ['DSA'] }), 'skills');
  assert.equal(previousStep('domains'), 'skills');
  assert.equal(previousStep('upload'), null);
});

test('wizard storage keeps metadata only and rejects malformed values', () => {
  const saved = serializeWizard({
    candidateId: 'c1', fileName: 'resume.pdf', extractedSkills: ['SQL', '', 3],
    domainProfile: { SQL: 'joins', bad: 4 }, selectedSkills: ['SQL'],
    targetSelection: { companyId: 'amazon', roleId: 'amazon_sde_intern' },
    file: { bytes: 'never stored' },
  });
  assert.deepEqual(Object.keys(saved).sort(),
    ['candidateId', 'domainProfile', 'extractedSkills', 'fileName', 'selectedSkills', 'targetSelection']);
  assert.deepEqual(saved.extractedSkills, ['SQL', '3']);
  assert.deepEqual(saved.domainProfile, { SQL: 'joins' });
  assert.deepEqual(restoreWizard(null), { ...EMPTY_WIZARD });
  assert.deepEqual(restoreWizard('garbage'), { ...EMPTY_WIZARD });
});

test('scoped storage is per account, versioned, survives broken storage, and clears on account change', () => {
  globalThis.sessionStorage = new MemoryStorage();
  assert.equal(scopedKey('u1', 'upload-wizard'), 'interviv:v1:u1:upload-wizard');
  assert.equal(scopedKey(null, 'x'), null);
  writeScoped('session', 'u1', 'upload-wizard', { candidateId: 'c1' });
  assert.deepEqual(readScoped('session', 'u1', 'upload-wizard'), { candidateId: 'c1' });
  assert.equal(readScoped('session', 'u2', 'upload-wizard'), null); // other account
  assert.equal(readScoped('session', 'u1', 'upload-wizard', 2), null); // other version
  sessionStorage.setItem('interviv:v1:u1:broken', '{not json');
  assert.equal(readScoped('session', 'u1', 'broken'), null);
  sessionStorage.setItem('unrelated', 'kept');
  clearSessionScopedState();
  assert.equal(sessionStorage.getItem('interviv:v1:u1:upload-wizard'), null);
  assert.equal(sessionStorage.getItem('unrelated'), 'kept');
  globalThis.sessionStorage = {
    getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); },
  };
  assert.equal(writeScoped('session', 'u1', 'x', 1), false);
  assert.equal(readScoped('session', 'u1', 'x'), null);
  delete globalThis.sessionStorage;
});

test('Back goes one step only when the app owns that history entry', () => {
  assert.equal(hasInAppHistory({ key: 'default' }), false);
  assert.equal(backDestination({ key: 'default' }, '/dashboard'), '/dashboard');
  assert.equal(backDestination({ key: 'a1b2' }, '/dashboard'), -1);
  assert.equal(backDestination(undefined, '/home'), '/home');
  assert.equal(gapAnalysisPath('u/1', 'r 1'), '/gap-analysis/u%2F1/r%201');
  assert.equal(roadmapPath('u1', 'r1', 30), '/roadmap/u1/r1?days=30');
});

test('request errors are classified; only cancellations are silent', () => {
  const aborted = errorFromFetchFailure(Object.assign(new Error('x'), { name: 'AbortError' }));
  assert.equal(errorKind(aborted), 'cancelled');
  assert.equal(accountLoadAction(aborted), 'ignore');
  const offline = errorFromFetchFailure(new TypeError('Failed to fetch'));
  assert.equal(errorKind(offline), 'network');
  assert.equal(isRetryable(offline), true);
  assert.equal(accountLoadAction(offline), 'retry');
  assert.equal(accountLoadAction({ status: 500 }), 'retry');
  assert.equal(accountLoadAction({ status: 401 }), 'signin');
});

test('role requirements come from skill_requirements; weak-area prefill wins over target defaults', () => {
  const role = { title: 'SDE Intern', skill_requirements: [{ skill: 'DSA' }, { skill: 'OOP', display_name: 'Object-oriented' }] };
  assert.deepEqual(roleRequiredSkills(role), ['DSA', 'OOP']);
  assert.deepEqual(roleRequiredSkills({ required_skills: ['SQL'] }), ['SQL']);
  assert.deepEqual(roleRequiredSkills(null), []);
  // Hop prefill marks skills explicit, so the later target default is skipped.
  const hop = applyTargetPrefill(['DBMS'], ['Graphs', 'DP'], false);
  assert.deepEqual(hop, { skills: ['Graphs', 'DP'], applied: true });
  const later = applyTargetPrefill(hop.skills, roleRequiredSkills(role), true);
  assert.deepEqual(later, { skills: ['Graphs', 'DP'], applied: false });
});

test('"set target" prompts are never shown as the active page', () => {
  assert.equal(isNavActive('/home', '/home#target'), false);
  assert.equal(isNavActive('/home', '/home'), true);
  assert.equal(isNavActive('/gap-analysis/u1/r1', '/gap-analysis/u1/r1'), true);
});
