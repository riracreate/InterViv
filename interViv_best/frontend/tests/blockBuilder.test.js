import assert from 'node:assert/strict';
import test from 'node:test';

import {
  STANDALONE_MODES,
  addBlock,
  removeBlock,
  moveBlock,
  duplicateBlock,
  formatBlockLabel,
  totalTimeSummary,
  validateBuilderBlocks,
  mapBlocksToStartPayload,
  mapStandaloneToStartPayload,
  validatePresetPayload,
  validateDraftPayload,
} from '../src/lib/practiceBuilder.js';

test('standalone entries cover Verbal, OA, SQL, and interview', () => {
  const ids = STANDALONE_MODES.map((m) => m.id).sort();
  assert.deepEqual(ids, ['interview', 'oa', 'sql', 'verbal']);
  const verbal = STANDALONE_MODES.find((m) => m.id === 'verbal');
  assert.match(verbal.blurb, /English MCQ/i);
  assert.doesNotMatch(verbal.blurb, /speak|voice|HR question/i);
});

test('adding Verbal never erases the existing sequence', () => {
  let blocks = addBlock([], 'oa');
  assert.equal(blocks.length, 1);
  blocks = addBlock(blocks, 'verbal');
  assert.equal(blocks.length, 2);
  assert.deepEqual(blocks.map((b) => b.category), ['oa', 'verbal']);
});

test('builder reorder and repeat use button-friendly pure helpers', () => {
  let blocks = addBlock(addBlock([], 'oa'), 'sql');
  const firstId = blocks[0].id;
  blocks = moveBlock(blocks, blocks[1].id, 'up');
  assert.equal(blocks[0].category, 'sql');
  blocks = duplicateBlock(blocks, firstId);
  assert.equal(blocks.length, 3);
  blocks = removeBlock(blocks, firstId);
  assert.equal(blocks.length, 2);
});

test('block labels use human text, never raw round names', () => {
  assert.equal(formatBlockLabel({ category: 'oa', count: 12 }), 'OA · 12 questions');
  assert.equal(formatBlockLabel({ category: 'verbal', count: 1 }), 'Verbal · 1 question');
  assert.equal(formatBlockLabel({ category: 'sql', count: 2 }), 'SQL · 2 problems');
  assert.match(formatBlockLabel({ category: 'interview', count: 3 }), /Interview · 3 questions/);
});

test('total-time summary separates timed minutes and untimed blocks', () => {
  const summary = totalTimeSummary([
    { duration_minutes: 20 },
    { duration_minutes: 25 },
    {},
  ]);
  assert.equal(summary.timedMinutes, 45);
  assert.equal(summary.untimedBlocks, 1);
  assert.equal(summary.blockCount, 3);
});

test('builder validation keeps Verbal and OA distinct', () => {
  const mixed = validateBuilderBlocks([
    { round_type: 'mcq', category: 'oa', skills: ['Verbal Ability'], count: 5 },
  ]);
  assert.match(mixed, /must not include Verbal Ability/);
  const verbalOk = validateBuilderBlocks([
    { round_type: 'mcq', category: 'verbal', skills: ['Verbal Ability'], count: 5 },
  ]);
  assert.equal(verbalOk, null);
});

test('standalone OA rejects Verbal topics; standalone Verbal is fixed', () => {
  const bad = mapStandaloneToStartPayload('oa', { skills: ['Verbal Ability'], count: 5 });
  assert.match(bad.error, /must not include Verbal Ability/);
  const good = mapStandaloneToStartPayload('verbal', { count: 10, durationMinutes: 15 });
  assert.equal(good.error, undefined);
  assert.equal(good.payload.blocks[0].category, 'verbal');
  assert.deepEqual(good.payload.blocks[0].skills, ['Verbal Ability']);
});

test('blocks map to a server-validated plan with requested order', () => {
  const { error, payload } = mapBlocksToStartPayload([
    { id: 'a', round_type: 'mcq', category: 'verbal', skills: ['Verbal Ability'], count: 5, duration_minutes: 10 },
    { id: 'b', round_type: 'sql', category: 'sql', skills: ['SQL'], count: 1, duration_minutes: 15 },
  ]);
  assert.equal(error, undefined);
  assert.equal(payload.blocks.length, 2);
  assert.equal(payload.blocks[0].id, 'a');
  assert.equal(payload.blocks[1].id, 'b');
});

test('preset and draft payloads enforce versions', () => {
  const presetBad = validatePresetPayload({ version: 99, name: 'x', blocks: [] });
  assert.match(presetBad, /Unsupported preset version/);
  const draftBad = validateDraftPayload({ version: 99, blocks: [] });
  assert.match(draftBad, /Unsupported draft version/);
  const presetOk = validatePresetPayload({
    version: 1,
    name: 'DBMS sprint',
    blocks: [{ round_type: 'mcq', category: 'oa', skills: ['DBMS'], count: 5, duration_minutes: 10 }],
  });
  assert.equal(presetOk, null);
});
