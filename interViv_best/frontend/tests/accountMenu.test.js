// Phase 4 follow-ups found in manual testing (2026-11-04):
// 1. Upload had no account menu, so Sign out was unreachable there.
// 2. Skills → Review → Back reset the company/role: the selector remounted
//    from a page-load snapshot and reported it back on mount.
import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scratch = mkdtempSync(path.join(tmpdir(), 'interviv-account-menu-'));
const bundle = path.join(scratch, 'render.cjs');
let renderUpload;
let renderNav;
try {
  await build({
    stdin: {
      resolveDir: root,
      loader: 'jsx',
      contents: `
        import React from 'react';
        import { renderToStaticMarkup } from 'react-dom/server';
        import { MemoryRouter } from 'react-router-dom';
        import Upload from './src/pages/Upload.jsx';
        import AppNav from './src/components/AppNav.jsx';
        export const renderUpload = () => renderToStaticMarkup(
          <MemoryRouter initialEntries={['/upload?step=upload']}><Upload /></MemoryRouter>);
        export const renderNav = () => renderToStaticMarkup(
          <MemoryRouter initialEntries={['/home']}><AppNav userId="u1" userName="Asha" userEmail="a@example.com" /></MemoryRouter>);
      `,
    },
    outfile: bundle,
    bundle: true,
    platform: 'node',
    format: 'cjs',
    define: { 'process.env.NODE_ENV': '"production"' },
    logLevel: 'silent',
  });
  ({ renderUpload, renderNav } = createRequire(import.meta.url)(bundle));
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

test('Upload shows the account menu with Sign out', () => {
  const html = renderUpload();
  assert.match(html, /data-testid="app-nav-account-button"/);
  assert.match(html, /data-testid="app-nav-sign-out"[^>]*>Sign out/);
});

test('the shared nav renders the same account menu', () => {
  const html = renderNav();
  assert.match(html, /aria-label="Account menu"/);
  assert.match(html, /Asha/);
  assert.match(html, />Sign out</);
});

test('the company selector remounts from the live selection and never reports on mount', () => {
  const upload = readFileSync(path.join(root, 'src/pages/Upload.jsx'), 'utf8');
  assert.match(upload, /initialCompanyId=\{targetSelection\.companyId\}/);
  assert.match(upload, /initialRoleId=\{targetSelection\.roleId\}/);
  assert.doesNotMatch(upload, /initialTarget/);
  const selector = readFileSync(path.join(root, 'src/components/CompanySelector.jsx'), 'utf8');
  // Reports only when the selection differs from what it last reported
  // (starting from its initial props), so a remount cannot clear the parent.
  assert.match(selector, /const lastNotified = useRef\(\{ companyId: initialCompanyId \|\| '', roleId: initialRoleId \|\| '' \}\)/);
  assert.match(selector, /next\.companyId === lastNotified\.current\.companyId && next\.roleId === lastNotified\.current\.roleId/);
});
