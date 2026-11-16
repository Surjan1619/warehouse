// Run with: npm test   (Node built-in test runner, no extra packages)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  MAX_RECENT,
  addRecent,
  describePieces,
  isValidEntry,
  loadRecent,
  makeEntry,
  saveRecent,
  signature,
  toFormPieces,
} from './recentCuts.js';

const used = (length_mm) => ({ length_mm, used: true });
const kept = (length_mm) => ({ length_mm, used: false });
const job = (material_id, ...pieces) => ({ material_id, pieces });

// A stand-in for localStorage
const fakeStorage = (initial = {}) => {
  const data = { ...initial };
  return {
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = String(value);
    },
    data,
  };
};

test('makeEntry turns form values into numbers and booleans', () => {
  const entry = makeEntry('7', [{ length_mm: '3000', used: true, times: '2' }, { length_mm: '1000', used: false }]);
  assert.deepEqual(entry, job(7, used(3000), kept(1000)));
  assert.ok(isValidEntry(entry));
});

test('the same pieces in another order are the same job', () => {
  assert.equal(signature(job(1, used(3000), used(1000))), signature(job(1, used(1000), used(3000))));
});

test('a different material, length, count or purpose is a different job', () => {
  const base = signature(job(1, used(3000), used(3000)));
  assert.notEqual(base, signature(job(2, used(3000), used(3000))));
  assert.notEqual(base, signature(job(1, used(3000), used(3001))));
  assert.notEqual(base, signature(job(1, used(3000))));
  assert.notEqual(base, signature(job(1, used(3000), kept(3000))));
});

test('a new job goes first', () => {
  const list = addRecent([job(1, used(1000))], job(1, used(3000)));
  assert.deepEqual(list, [job(1, used(3000)), job(1, used(1000))]);
});

test('a repeated job moves to the top instead of being listed twice', () => {
  const a = job(1, used(1000));
  const b = job(1, used(2000));
  const c = job(1, used(3000));
  assert.deepEqual(addRecent([c, b, a], a), [a, c, b]);
});

test('the list keeps only the latest jobs', () => {
  let list = [];
  for (let length = 1; length <= MAX_RECENT + 3; length += 1) list = addRecent(list, job(1, used(length)));
  assert.equal(list.length, MAX_RECENT);
  assert.equal(list[0].pieces[0].length_mm, MAX_RECENT + 3);
  assert.equal(list.at(-1).pieces[0].length_mm, 4);
});

test('addRecent does not change the list it was given', () => {
  const original = [job(1, used(1000))];
  addRecent(original, job(1, used(2000)));
  assert.deepEqual(original, [job(1, used(1000))]);
});

test('describePieces collapses equal lengths', () => {
  const nbsp = ' '; // the thousands separator used by ru-RU
  assert.equal(describePieces([used(3000), used(3000)]), `3${nbsp}000 × 2`);
  assert.equal(describePieces([used(3000), used(1000), used(3000)]), `3${nbsp}000 × 2 + 1${nbsp}000`);
  assert.equal(describePieces([used(500)]), '500');
});

test('toFormPieces gives rows the cut page can edit', () => {
  assert.deepEqual(toFormPieces(job(1, used(3000), kept(1000))), [
    { length_mm: '3000', used: true, times: '2' },
    { length_mm: '1000', used: false, times: '2' },
  ]);
});

test('saved jobs come back after a reload', () => {
  const storage = fakeStorage();
  const list = [job(1, used(3000), used(3000)), job(2, kept(1000))];
  saveRecent(list, storage);
  assert.deepEqual(loadRecent(storage), list);
});

test('an empty or missing storage gives an empty list', () => {
  assert.deepEqual(loadRecent(fakeStorage()), []);
  assert.deepEqual(loadRecent(undefined), []);
});

test('damaged data in storage is ignored, not shown', () => {
  const stored = (value) => fakeStorage({ recent_cuts: value });
  assert.deepEqual(loadRecent(stored('not json')), []);
  assert.deepEqual(loadRecent(stored('{"a":1}')), []);
  assert.deepEqual(loadRecent(stored('null')), []);

  const mixed = JSON.stringify([
    job(1, used(3000)),
    { material_id: 'x', pieces: [used(1)] },
    job(1),
    job(1, { length_mm: -5, used: true }),
    job(1, { length_mm: 5 }),
    null,
    job(2, kept(700)),
  ]);
  assert.deepEqual(loadRecent(stored(mixed)), [job(1, used(3000)), job(2, kept(700))]);
});

test('a storage that refuses to work does not break anything', () => {
  const broken = {
    getItem: () => {
      throw new Error('blocked');
    },
    setItem: () => {
      throw new Error('blocked');
    },
  };
  assert.deepEqual(loadRecent(broken), []);
  assert.doesNotThrow(() => saveRecent([job(1, used(1))], broken));
});

test('more stored jobs than the limit are cut down on load', () => {
  const many = Array.from({ length: MAX_RECENT + 4 }, (_, i) => job(1, used(i + 1)));
  const storage = fakeStorage({ recent_cuts: JSON.stringify(many) });
  assert.equal(loadRecent(storage).length, MAX_RECENT);
});
