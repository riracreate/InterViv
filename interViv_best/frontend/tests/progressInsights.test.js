import test from 'node:test';
import assert from 'node:assert/strict';
import { buildProgressInsights } from '../src/lib/progressInsights.js';

test('insights use only dated, completed single-type scores and count real sessions by day', () => {
  const rows = [
    { session_id: 'one', created_at: '2026-11-14T12:00:00Z', status: 'completed', round_types: ['mcq'], average_score: 0 },
    { session_id: 'mixed', created_at: '2026-11-14T15:00:00Z', status: 'completed', round_types: ['mcq', 'sql'], average_score: 80 },
    { session_id: 'unscored', created_at: '2026-11-15T01:00:00Z', status: 'active', round_types: ['coding'], average_score: null },
    { session_id: 'bad', created_at: 'invalid', status: 'completed', round_types: ['sql'], average_score: 100 },
    { session_id: 'missing', created_at: null, status: 'completed', round_types: ['sql'], average_score: 100 },
  ];
  const result = buildProgressInsights(rows, new Date('2026-11-15T10:00:00Z'));
  assert.deepEqual(result.trend.map(item => item.session_id), ['one']);
  assert.equal(result.trend[0].average_score, 0);
  assert.equal(result.calendar.length, 84);
  assert.deepEqual(result.calendar.slice(-2), [{ date: '2026-11-14', count: 2 }, { date: '2026-11-15', count: 1 }]);
});
