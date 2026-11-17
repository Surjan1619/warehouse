// Run with: npm test   (Node built-in test runner, no extra packages)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  addCut,
  addGoods,
  allLinesValid,
  availableOf,
  commitRequest,
  isEmpty,
  loadDraft,
  newDraft,
  newKey,
  planRequest,
  planSignature,
  removeLine,
  saveDraft,
  totals,
  unplacedOf,
  updateLine,
} from './assemblyDraft.js';

const cut = (material_id, length_mm, quantity = 1, used = true) => ({ material_id, length_mm, quantity, used });

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

test('a new draft is empty and has a key long enough for the server', () => {
  const draft = newDraft();
  assert.ok(isEmpty(draft));
  assert.ok(draft.key.length >= 8 && draft.key.length <= 64);
  assert.notEqual(newKey(), newKey());
});

test('the same length of the same material is one line', () => {
  let draft = addCut(newDraft('k'.repeat(8)), cut(1, 3000, 1));
  draft = addCut(draft, cut(1, 3000, 2));
  draft = addCut(draft, cut(1, 3000, 1, false));
  draft = addCut(draft, cut(2, 3000, 1));
  assert.deepEqual(
    draft.cuts.map(({ material_id, length_mm, quantity, used }) => [material_id, length_mm, quantity, used]),
    [[1, 3000, 3, true], [1, 3000, 1, false], [2, 3000, 1, true]],
  );
  assert.equal(new Set(draft.cuts.map((l) => l.id)).size, 3);
});

test('the same product is one line with the quantities summed', () => {
  let draft = addGoods(newDraft('k'.repeat(8)), { product_id: 5, quantity: 1 });
  draft = addGoods(draft, { product_id: 5, quantity: 2 });
  assert.deepEqual(draft.goods.map((l) => [l.product_id, l.quantity]), [[5, 3]]);
});

test('lines can be edited and removed', () => {
  let draft = addCut(newDraft('k'.repeat(8)), cut(1, 3000));
  draft = addGoods(draft, { product_id: 5, quantity: 1 });
  const [line] = draft.cuts;
  draft = updateLine(draft, 'cuts', line.id, { length_mm: 2500, quantity: 4 });
  assert.deepEqual([draft.cuts[0].length_mm, draft.cuts[0].quantity], [2500, 4]);
  draft = removeLine(draft, 'goods', draft.goods[0].id);
  assert.equal(draft.goods.length, 0);
  assert.equal(draft.cuts.length, 1);
});

test('the plan request groups pieces by material and skips unfinished lines', () => {
  let draft = newDraft('k'.repeat(8));
  draft = addCut(draft, cut(1, 3000, 1));
  draft = addCut(draft, cut(2, 500, 4, false));
  draft = addCut(draft, cut(1, 1500, 2));
  draft = addGoods(draft, { product_id: 7, quantity: 2 });
  // A line the worker is still typing in
  draft = { ...draft, cuts: [...draft.cuts, { id: 99, material_id: 1, length_mm: 0, quantity: 1, used: true }] };

  assert.deepEqual(planRequest(draft), {
    materials: [
      { material_id: 1, pieces: [{ length_mm: 3000, quantity: 1, used: true }, { length_mm: 1500, quantity: 2, used: true }] },
      { material_id: 2, pieces: [{ length_mm: 500, quantity: 4, used: false }] },
    ],
    products: [{ product_id: 7, quantity: 2 }],
  });
  assert.equal(allLinesValid(draft), false);
});

test('the signature changes only when the question to the server changes', () => {
  const draft = addCut(newDraft('k'.repeat(8)), cut(1, 3000));
  assert.equal(planSignature({ ...draft, name: 'Ворота' }), planSignature(draft));
  assert.notEqual(planSignature(addCut(draft, cut(1, 3000))), planSignature(draft));
});

const plan = {
  materials: [
    {
      material: { id: 1 },
      cuts: [
        { item: { id: 10 }, pieces: [{ length_mm: 3000, used: true, note: null }, { length_mm: 1500, used: true }] },
        { item: { id: 11 }, pieces: [{ length_mm: 1500, used: true }] },
      ],
      unplaced: [{ length_mm: 6000, used: true }, { length_mm: 6000, used: true }],
    },
  ],
  products: [{ product: { id: 7 }, quantity: 2, available: 1 }],
  ok: false,
};

test('finishing sends exactly the cuts of the plan', () => {
  const draft = { ...newDraft('abcdefgh'), name: '  Ворота №3 ', note: '' };
  assert.deepEqual(commitRequest(draft, plan), {
    client_key: 'abcdefgh',
    name: 'Ворота №3',
    note: null,
    cuts: [
      { source_item_id: 10, pieces: [{ length_mm: 3000, used: true }, { length_mm: 1500, used: true }] },
      { source_item_id: 11, pieces: [{ length_mm: 1500, used: true }] },
    ],
    products: [{ product_id: 7, quantity: 2 }],
  });
});

test('shortages are found for the line they belong to', () => {
  assert.equal(unplacedOf(plan, { material_id: 1, length_mm: 6000, quantity: 3, used: true }), 2);
  assert.equal(unplacedOf(plan, { material_id: 1, length_mm: 6000, quantity: 1, used: true }), 1);
  assert.equal(unplacedOf(plan, { material_id: 1, length_mm: 6000, quantity: 3, used: false }), 0);
  assert.equal(unplacedOf(plan, { material_id: 2, length_mm: 6000, quantity: 1, used: true }), 0);
  assert.equal(unplacedOf(null, { material_id: 1, length_mm: 6000, quantity: 1, used: true }), 0);
  assert.equal(availableOf(plan, 7), 1);
  assert.equal(availableOf(plan, 8), null);
});

test('totals count pieces, millimetres and goods', () => {
  let draft = newDraft('k'.repeat(8));
  draft = addCut(draft, cut(1, 3000, 2));
  draft = addCut(draft, cut(1, 500, 1, false));
  draft = addGoods(draft, { product_id: 7, quantity: 2 });
  draft = addGoods(draft, { product_id: 8, quantity: 1 });
  const result = totals(draft);
  assert.deepEqual(result.materials.get(1), { pieces: 3, length_mm: 6500, used_mm: 6000 });
  assert.equal(result.goods, 3);
});

test('the draft survives a reload and broken storage gives a new one', () => {
  const storage = fakeStorage();
  const draft = addCut(newDraft('abcdefgh'), cut(1, 3000));
  saveDraft(draft, storage);
  assert.deepEqual(loadDraft(storage), draft);

  assert.ok(isEmpty(loadDraft(fakeStorage({ assembly_draft: '{broken' }))));
  assert.ok(isEmpty(loadDraft(fakeStorage({ assembly_draft: '{"key":"x"}' }))));
  const throwing = {
    getItem: () => {
      throw new Error('blocked');
    },
    setItem: () => {
      throw new Error('blocked');
    },
  };
  assert.ok(isEmpty(loadDraft(throwing)));
  assert.doesNotThrow(() => saveDraft(draft, throwing));
});
