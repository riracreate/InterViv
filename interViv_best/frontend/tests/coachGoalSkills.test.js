import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'src/pages/Coach.jsx'), 'utf8');

test('Coach sends recognised skills before it asks for a plan', () => {
  const submit = src.slice(src.indexOf('const submit = async'), src.indexOf('const sendChat'));
  const goals = submit.indexOf('planning_context_skills: mapped.recognizedSkills');
  const create = submit.indexOf("action: 'create_plan'");
  assert.ok(goals > 0);
  assert.ok(create > goals);
});
