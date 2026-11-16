// Run with: npm test   (Node built-in test runner, no extra packages)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { PAGE_SIZE, clampPage, metres, pageCount, pageQuery, pageRange } from './pagination.js';

test('page count rounds up and never drops below one', () => {
  assert.equal(pageCount(0), 1);
  assert.equal(pageCount(1), 1);
  assert.equal(pageCount(PAGE_SIZE), 1);
  assert.equal(pageCount(PAGE_SIZE + 1), 2);
  assert.equal(pageCount(230, 50), 5);
});

test('a page index stays inside the list', () => {
  assert.equal(clampPage(-1, 100, 50), 0);
  assert.equal(clampPage(1, 100, 50), 1);
  assert.equal(clampPage(5, 100, 50), 1); // the list got shorter
  assert.equal(clampPage(3, 0, 50), 0);
});

test('range shows which items are on the page', () => {
  assert.equal(pageRange(0, 230, 50), '1–50 из 230');
  assert.equal(pageRange(4, 230, 50), '201–230 из 230');
  assert.equal(pageRange(0, 7, 50), '1–7 из 7');
  assert.equal(pageRange(0, 0, 50), '0 из 0');
});

test('query carries the filters and the offset of the page', () => {
  assert.equal(
    pageQuery({ status: 'in_stock', materialId: 3, page: 2, size: 50 }),
    'status=in_stock&material_id=3&limit=50&offset=100',
  );
});

test('empty filters are left out of the query', () => {
  assert.equal(pageQuery({ status: '', materialId: null, page: 0 }), `limit=${PAGE_SIZE}&offset=0`);
});

test('millimetres are shown as metres', () => {
  // ru-RU uses a comma for decimals and a no-break space between thousands
  assert.equal(metres(22500), '22,5 м');
  assert.equal(metres(7000), '7 м');
  assert.equal(metres(1234), '1,23 м');
  assert.equal(metres(1500000).replace(/\s/g, ' '), '1 500 м');
});
