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
