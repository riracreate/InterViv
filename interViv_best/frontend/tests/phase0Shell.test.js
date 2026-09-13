import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

test('page title is interViv and index.html has no Velorah branding', () => {
  const html = readFileSync(join(root, 'index.html'), 'utf8');
  assert.match(html, /<title>interViv<\/title>/);
  assert.equal(/velorah/i.test(html), false);
});

test('session report Back to Home goes to /home', () => {
  const src = readFileSync(join(root, 'src/pages/Dashboard.tsx'), 'utf8');
  assert.match(src, /navigate\('\/home'\)/);
  assert.doesNotMatch(src, /navigate\('\/'\)/);
  assert.match(src, /fetchAccountOverview/);
});

test('interview camera uses one callback ref on both video elements', () => {
  const src = readFileSync(join(root, 'src/pages/Interview.jsx'), 'utf8');
  const attaches = [...src.matchAll(/ref=\{attachVideoEl\}/g)];
  assert.equal(attaches.length, 2);
  assert.match(src, /node\.srcObject = stream/);
});

test('resource links always have an empty-state message', () => {
  const src = readFileSync(join(root, 'src/components/ResourceLinks.jsx'), 'utf8');
  assert.match(src, /emptyMessage = "No curated resources for this skill yet\."/);
  assert.doesNotMatch(src, /emptyMessage \? <p role="status">/);
});

test('tailwind font tokens use loaded CSS variables', () => {
  const src = readFileSync(join(root, 'tailwind.config.js'), 'utf8');
  assert.match(src, /var\(--font-display\)/);
  assert.match(src, /var\(--font-body\)/);
  assert.equal(/velorah/i.test(src), false);
});
