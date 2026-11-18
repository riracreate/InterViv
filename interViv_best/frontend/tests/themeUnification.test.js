// Phase 6: one light theme — system sans, slate background, white surfaces.
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => readFileSync(path.join(root, rel), 'utf8');

test('shared tokens: system sans-serif, cream surfaces, and a dark theme', () => {
  const theme = read('src/styles/theme.css');
  assert.match(theme, /--font-sans: ui-sans-serif, system-ui/);
  assert.match(theme, /--font-display: var\(--font-sans\)/);
  assert.match(theme, /--font-body: var\(--font-sans\)/);
  assert.match(theme, /--color-surface: #f7f8f2/);
  assert.match(theme, /--color-card: #ffffff/);
  assert.match(theme, /:root\[data-theme="dark"\]/);
  assert.doesNotMatch(read('src/styles/fonts.css'), /--font-(display|body): "Instrument Serif|--font-(display|body): "Barlow/);
});

test('Tailwind colors point at the tokens (no second palette)', () => {
  const config = read('tailwind.config.js');
  const colors = config.slice(config.indexOf('colors:'), config.indexOf('boxShadow:'));
  assert.doesNotMatch(colors, /#[0-9a-f]{3,6}/i);
  assert.doesNotMatch(config, /ember|moss|ocean|sand|mist|halo/);
});

test('the session report no longer uses the dark neon palette', () => {
  const dir = path.join(root, 'src/components/dashboard');
  const files = readdirSync(dir).map((f) => path.join('src/components/dashboard', f)).concat('src/pages/Dashboard.tsx');
  for (const rel of files) {
    const src = read(rel);
    assert.doesNotMatch(src, /text-white\/\d|bg-black\/\d|border-white\/\d|#0a0a0a|session-bg|dashboard-session/, rel);
  }
  assert.doesNotMatch(read('src/index.css'), /rgba\(0, 0, 0, 0\.55\)/);
});

test('interview and upload use the tokens instead of hard-coded black and grey', () => {
  for (const rel of ['src/pages/Interview.jsx', 'src/pages/Upload.jsx', 'src/components/CompanySelector.jsx']) {
    const src = read(rel);
    assert.doesNotMatch(src, /#6F6F6F|'#000'|"#000"/i, rel);
  }
});
