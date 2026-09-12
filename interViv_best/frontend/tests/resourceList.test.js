import assert from 'node:assert/strict';
import test from 'node:test';

import { buildResourceListModel, groupResourcesByLevel } from '../src/lib/resourceList.js';
import { fetchResources } from '../src/lib/api.js';

test('resource list model renders titles and urls from mock payload', () => {
  const mock = {
    by_level: {
      beginner: [
        {
          title: 'PostgreSQL official tutorial',
          url: 'https://www.postgresql.org/docs/current/tutorial.html',
          source: 'docs',
        },
      ],
      intermediate: [
        {
          title: 'Use The Index, Luke',
          url: 'https://use-the-index-luke.com/',
          source: 'docs',
        },
      ],
      advanced: [],
    },
  };
  const items = buildResourceListModel(mock);
  assert.equal(items.length, 2);
  assert.equal(items[0].title, 'PostgreSQL official tutorial');
  assert.equal(items[0].url, 'https://www.postgresql.org/docs/current/tutorial.html');
  assert.equal(items[1].title, 'Use The Index, Luke');
  assert.match(items[1].url, /^https:\/\//);

  const groups = groupResourcesByLevel(items);
  assert.equal(groups.beginner.length, 1);
  assert.equal(groups.intermediate.length, 1);
  assert.equal(groups.advanced.length, 0);
});

test('full resource page keeps entries beyond the compact widget limit', () => {
  const payload = { by_level: { beginner: Array.from({ length: 8 }, (_, i) => ({ title: `Lesson ${i}`, url: `https://example.com/${i}`, source: 'docs' })) } };
  assert.equal(buildResourceListModel(payload).length, 3);
  assert.equal(buildResourceListModel(payload, { limitPerLevel: 100 }).length, 8);
});

test('resource API client forwards the expanded limit and encodes category names', async () => {
  const previousFetch = globalThis.fetch;
  const previousStorage = globalThis.localStorage;
  const paths = [];
  globalThis.localStorage = { getItem: () => null };
  globalThis.fetch = async path => {
    paths.push(new URL(path, 'http://127.0.0.1'));
    return { ok: true, json: async () => ({ resources: [] }) };
  };
  try {
    await fetchResources({ skillId: 'Resume / ATS', limitPerLevel: 100 });
    await fetchResources({ questionId: 'sql_prob_001' });
    assert.equal(paths[0].searchParams.get('skill_id'), 'Resume / ATS');
    assert.equal(paths[0].searchParams.get('limit_per_level'), '100');
    assert.equal(paths[1].searchParams.get('question_id'), 'sql_prob_001');
    assert.equal(paths[1].searchParams.has('limit_per_level'), false);
  } finally {
    globalThis.fetch = previousFetch;
    if (previousStorage === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = previousStorage;
  }
});
