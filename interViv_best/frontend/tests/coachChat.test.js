import assert from 'node:assert/strict';
import test from 'node:test';

import {
  assembleStream,
  buildSuggestionChips,
  confirmRequest,
  dismissRequest,
  parseSseText,
  toolCardView,
} from '../src/lib/coachChat.js';

test('chips keep only validated actions and add Why this task when a plan exists', () => {
  const reply = {
    actions: [
      { type: 'create_plan', label: 'Build starter plan' },
      { type: 'evil', label: 'Nope' },
      { type: 'update_hours', label: 'Update study time' },
    ],
  };
  assert.deepEqual(buildSuggestionChips(reply, false).map((c) => c.type), ['create_plan', 'update_hours']);
  assert.equal(buildSuggestionChips(reply, true).at(-1).label, 'Why this task?');
});

test('tool cards show confirm copy and the 24-hour note only on explain', () => {
  const practice = toolCardView({ tool: 'start_practice', args: { skills: ['Python'] } });
  assert.match(practice.lines.join(' '), /Python/);
  assert.equal(practice.note, null);
  const explain = toolCardView({ tool: 'explain_last_interview', args: { session_id: 'sess-1' } });
  assert.match(explain.note, /24 hours/);
  assert.match(explain.note, /teaching exposure/);
  assert.equal(toolCardView({ tool: 'unknown', args: {} }), null);
});

test('confirm is required: dismiss builds no request', () => {
  assert.deepEqual(
    confirmRequest({ tool: 'update_plan', args: { goal: 'Backend' } }),
    { tool: 'update_plan', args: { goal: 'Backend' } }
  );
  assert.equal(dismissRequest(), null);
});

test('stream assembly uses only token events the server sent after validation', () => {
  const events = parseSseText(
    'event: token\ndata: {"text":"Hello "}\n\nevent: token\ndata: {"text":"there"}\n\nevent: done\ndata: {"mode":"provider"}\n\n'
  );
  const out = assembleStream(events);
  assert.equal(out.text, 'Hello there');
  assert.equal(out.done.mode, 'provider');
});
