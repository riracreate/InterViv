import assert from 'node:assert/strict';
import test from 'node:test';

import { addSkills, canonicalSkill, matchSuggestions, removeSkill } from '../src/lib/skillChips.js';
import { PRACTICE_MODES, PRACTICE_TRACKS, STANDALONE_MODES, modeById } from '../src/lib/practiceBuilder.js';

test('chips accept multi-word skills, pasted lists and dedupe case-insensitively', () => {
  const suggestions = ['System Design', 'DBMS', 'Python'];
  assert.deepEqual(addSkills([], 'system design', suggestions), ['System Design']);
  assert.deepEqual(addSkills(['DBMS'], 'Python, dbms,  Graphs \n Trees', suggestions), ['DBMS', 'Python', 'Graphs', 'Trees']);
  assert.deepEqual(addSkills(['A'], '   ', suggestions), ['A']);
  assert.equal(addSkills([], 'a,b,c,d', [], 2).length, 2);
  assert.equal(canonicalSkill('  python ', suggestions), 'Python');
  assert.deepEqual(removeSkill(['DBMS', 'Python'], 'dbms'), ['Python']);
});

test('suggestions put prefix matches first and hide chosen skills', () => {
  const list = ['SQL', 'System Design', 'DBMS', 'Operating Systems'];
  assert.deepEqual(matchSuggestions(list, 'sy', [], 5), ['System Design', 'Operating Systems']);
  assert.deepEqual(matchSuggestions(list, '', ['SQL'], 2), ['System Design', 'DBMS']);
});

test('every practice mode appears in exactly one of the four tracks', () => {
  assert.equal(PRACTICE_TRACKS.length, 4);
  const placed = PRACTICE_TRACKS.flatMap((t) => t.modes);
  const all = [...STANDALONE_MODES, ...PRACTICE_MODES].map((m) => m.id);
  assert.deepEqual([...placed].sort(), [...all].sort());
  assert.equal(new Set(placed).size, placed.length);
  assert.ok(placed.every((id) => modeById(id)));
});

import { dedupeDomainSkills, filterDomains, selectedCount } from '../src/lib/skillDomains.js';

test('upload domains list each skill once and search narrows them', () => {
  const domains = dedupeDomainSkills([
    { name: 'Backend', short: 'BE', skills: ['Python', 'SQL', 'Go'] },
    { name: 'Databases', short: 'DB', skills: ['SQL', 'Redis'] },
    { name: 'Languages', short: 'Lang', skills: ['Go', 'Rust'] },
  ]);
  assert.deepEqual(domains.map((d) => d.skills), [['Python', 'SQL', 'Go'], ['Redis'], ['Rust']]);
  assert.deepEqual(filterDomains(domains, 're').map((d) => [d.name, d.skills]), [['Databases', ['Redis']]]);
  assert.deepEqual(filterDomains(domains, 'data').map((d) => d.name), ['Databases']);
  assert.equal(filterDomains(domains, '').length, 3);
  assert.equal(selectedCount(domains[0], ['sql', 'Go', 'Rust']), 2);
});
