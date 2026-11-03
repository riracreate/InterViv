import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { MAX_RESUME_BYTES, resumeFileError } from '../src/lib/resumeUpload.js';
import { validateLoginFields, validateSignupFields } from '../src/lib/authForm.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(join(root, rel), 'utf8');

test('resume limit matches the 5 MiB server limit and rejects before sending', () => {
  assert.equal(MAX_RESUME_BYTES, 5 * 1024 * 1024);
  assert.equal(resumeFileError({ type: 'application/pdf', size: MAX_RESUME_BYTES }), '');
  assert.match(resumeFileError({ type: 'application/pdf', size: MAX_RESUME_BYTES + 1 }), /too large/);
  assert.match(resumeFileError({ type: 'text/plain', size: 10 }), /PDF/);
  const upload = read('src/pages/Upload.jsx');
  assert.match(upload, /Maximum file size \{MAX_RESUME_LABEL\}/);
  assert.doesNotMatch(upload, /10MB|10 MB/);
  assert.match(upload, /resumeFileError\(file\)/);
});

test('login and signup validation reports the failing field', () => {
  assert.deepEqual(validateLoginFields({ email: '', password: '' }), {
    email: 'Email is required.',
    password: 'Password is required.',
  });
  assert.deepEqual(validateLoginFields({ email: 'a@b.co', password: 'x' }), {});
  const signup = validateSignupFields({
    name: 'A',
    email: 'a@b.co',
    password: 'abcdefgh',
    confirmPassword: 'abcdefg1',
  });
  assert.match(signup.password, /letter and one number/);
  assert.match(signup.confirmPassword, /do not match/);
});

test('auth forms connect errors to fields and announce them', () => {
  for (const page of ['src/pages/Login.jsx', 'src/pages/Signup.jsx']) {
    const src = read(page);
    assert.match(src, /aria-invalid=/, page);
    assert.match(src, /aria-describedby=/, page);
    assert.match(src, /app-field/, page);
    assert.match(src, /role="alert"/, page);
  }
});

test('report renames share to copy-link with retry and sign-in note', () => {
  const src = read('src/pages/Dashboard.tsx');
  assert.match(src, /Copy report link/);
  assert.doesNotMatch(src, /Share Results/);
  assert.match(src, /Try again/);
  assert.match(src, /Reports require sign-in/);
  assert.match(src, /Copying failed/);
});

test('shared styles cover global focus, print and mobile history without sideways scroll', () => {
  const theme = read('src/styles/theme.css');
  assert.match(theme, /:focus-visible/);
  assert.match(theme, /@media print/);
  assert.match(theme, /prefers-reduced-motion/);
  assert.match(theme, /\.app-container/);
  const hub = read('src/styles/hub.css');
  assert.doesNotMatch(hub, /min-width: 620px/);
  assert.match(hub, /data-label/);
  const progress = read('src/pages/Progress.jsx');
  assert.match(progress, /data-label="Date"/);
});

test('navigation keeps a small-screen menu and a desktop More menu', () => {
  const nav = read('src/components/AppNav.jsx');
  assert.match(nav, /app-nav-desktop/);
  assert.match(nav, /app-nav-more-button/);
  assert.match(nav, /app-nav-menu-button/);
  assert.match(nav, /More/);
});

test('landing shows one way back in when signed in, login and sign up otherwise', () => {
  const src = read('src/pages/Landing.jsx');
  assert.match(src, /hasAuthToken\(\)/);
  assert.match(src, /signedIn \?/);
  assert.match(src, /navigate\('\/home'\)[^\n]*\n\s*Go to Home/);
  assert.match(src, /navigate\('\/login'\)/);
  assert.match(src, /navigate\('\/signup'\)/);
  assert.doesNotMatch(src, /backgroundColor: '#000000'/);
});

test('the final round keeps its own result and offers View report; exit saves', () => {
  const src = read('src/pages/Interview.jsx');
  // No separate summary screen replaces the last round's result.
  assert.doesNotMatch(src, /if \(sessionComplete && roundType !== 'coding'\)/);
  assert.match(src, /'View report →'/);
  assert.match(src, /navigate\(`\/dashboard\/\$\{sessionId\}`\)/);
  assert.match(src, /Save &amp; Exit/);
  assert.doesNotMatch(src, /Progress will be lost/);
  assert.match(src, /const saveAndExit = async/);
  assert.match(src, /navigate\('\/home'\)/);
  for (const component of ['MCQRound', 'SQLRound', 'SystemDesignRound', 'CodingRound']) {
    assert.match(read(`src/components/${component}.jsx`), /'View report'/);
  }
});

test('upload actions use shared buttons and the danger status style', () => {
  const src = read('src/pages/Upload.jsx');
  assert.doesNotMatch(src, /backgroundColor: '#000', fontFamily/);
  assert.doesNotMatch(src, /text-red-600/);
  assert.match(src, /app-form-error/);
  assert.equal((src.match(/app-button app-button-primary w-full/g) || []).length, 3);
});

test('progress and dashboard show the observed average beside the conservative readiness', async () => {
  const { observedReadinessNote } = await import('../src/lib/accountOverview.js');
  const overview = {
    readiness: 66.7, readiness_observed: 100, readiness_provisional_skill_count: 1,
    target: { established_min_attempts: 3 },
  };
  assert.equal(observedReadinessNote(overview), 'Observed average 100% · 1 skill still provisional (fewer than 3 measured attempts)');
  assert.equal(observedReadinessNote({ readiness: 80, readiness_observed: 80, readiness_provisional_skill_count: 0 }), '');
  assert.equal(observedReadinessNote({ readiness: null, readiness_observed: null }), '');
  assert.match(read('src/pages/Progress.jsx'), /observedReadinessNote\(data\)/);
  assert.match(read('src/pages/Dashboard.tsx'), /observedReadinessNote\(overview\)/);
});
