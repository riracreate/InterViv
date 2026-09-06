import assert from 'node:assert/strict';
import test from 'node:test';

import { buildResourceListModel, groupResourcesByLevel } from '../src/lib/resourceList.js';

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
