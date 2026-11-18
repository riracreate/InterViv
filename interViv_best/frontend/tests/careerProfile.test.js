import test from 'node:test';
import assert from 'node:assert/strict';
import { emptyCareerProfile, mergeCareerProfile, parseCareerImport, parseCsv } from '../src/lib/careerProfile.js';

test('LinkedIn position CSV preserves quoted commas and line breaks', () => {
  const csv = 'Company Name,Title,Started On,Finished On,Description\r\n"Acme, Inc.",Engineer,Jan 2022,Feb 2024,"Built a service\nfor customers"';
  assert.equal(parseCsv(csv)[0].description, 'Built a service\nfor customers');
  assert.deepEqual(parseCareerImport(csv, 'Positions.csv').roles, [{ title: 'Engineer', company: 'Acme, Inc.', start: 'Jan 2022', end: 'Feb 2024' }]);
});

test('text suggests whole skills and JSON imports are reviewed before merging', () => {
  const text = parseCareerImport('Built JavaScript and SQL services using React.', 'resume.txt');
  assert.ok(text.skills.includes('JavaScript'));
  assert.ok(!text.skills.includes('Java'));
  const incoming = parseCareerImport(JSON.stringify({ name: 'Asha', skills: ['SQL', 'Python', 'sql'], positions: [{ title: 'Engineer', companyName: 'Acme' }] }), 'profile.json');
  const old = { ...emptyCareerProfile('Existing'), skills: ['SQL'] };
  const merged = mergeCareerProfile(old, incoming);
  assert.equal(old.name, 'Existing');
  assert.equal(merged.name, 'Asha');
  assert.deepEqual(merged.skills, ['SQL', 'Python']);
  assert.equal(merged.roles[0].company, 'Acme');
  assert.equal(mergeCareerProfile(merged, incoming).roles.length, 1);
});

test('invalid imports fail with an actionable error', () => {
  assert.throws(() => parseCareerImport('{broken', 'profile.json'), /could not be read/);
  assert.throws(() => parseCareerImport('Name\n"unfinished', 'skills.csv'), /unfinished quoted/);
  assert.throws(() => parseCareerImport('No recognizable technical skills here', 'resume.txt'), /No supported profile details/);
});
