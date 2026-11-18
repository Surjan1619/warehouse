// Run with: npm test   (Node built-in test runner, no extra packages)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { codeRange, newGoodsRows, plural, rowOutcome, rowSource, rowTarget, summaryText, typesPayload } from './importText.js';

// Russian digit groups are separated by a no-break space
const plain = (text) => text.replace(/\s/g, ' ');

const profile = { line: 19, kind: 'stock', unit: 'м', quantity: '3045', length_mm: 7000, pieces: 435, material: null };
const roller = { line: 10, kind: 'goods', unit: 'пар', quantity: '100', count: 100, product: null };

test('a row of cuttable stock becomes pieces of its length', () => {
  assert.equal(plain(rowSource(profile)), '3 045 м по 7 м');
  assert.equal(plain(rowOutcome(profile)), '435 заготовок × 7 000 мм');
  assert.equal(plain(rowSource({ ...profile, quantity: '448.5', length_mm: 6500 })), '448,5 м по 6,5 м');
  assert.equal(rowOutcome({ ...profile, pieces: 1 }).startsWith('1 заготовка'), true);
});

test('pairs stay pairs', () => {
  assert.equal(rowSource(roller), '100 пар');
  assert.equal(rowOutcome(roller), '+100 пар');
  assert.equal(rowOutcome({ ...roller, unit: 'шт', count: 3 }), '+3 шт.');
});

test('a row with a problem tells what is wrong', () => {
  assert.equal(rowOutcome({ kind: null, problem: 'not_whole_pieces' }), 'Метры не делятся на длину без остатка');
  assert.equal(rowOutcome({ kind: null, problem: 'something_new' }), 'something_new');
});

test('matched rows name what they go to, new goods can get a type', () => {
  assert.equal(rowTarget(profile), null);
  assert.equal(rowTarget({ ...roller, product: { name: 'Ролик (наш)' } }), 'Ролик (наш)');
  assert.deepEqual(newGoodsRows([profile, roller, { ...roller, line: 11, product: { name: 'x' } }]), [roller]);
  assert.equal(typesPayload({ 10: '3', 11: '', 12: null }), '{"10":3}');
});

test('the summary and the numbers to write on the pieces', () => {
  const summary = { stock_rows: 21, stock_pieces: 3075, new_materials: 12, goods_rows: 17, new_products: 13, problems: 0 };
  assert.equal(plain(summaryText(summary)), '3 075 заготовок (новых материалов: 12); товаров: 17 строк (новых: 13)');
  assert.equal(summaryText({ ...summary, stock_rows: 0 }), 'товаров: 17 строк (новых: 13)');
  assert.equal(summaryText({ ...summary, stock_rows: 0, goods_rows: 2 }), 'товаров: 2 строки (новых: 13)');
  assert.equal(codeRange(101, 535), 'T-000101 … T-000535');
  assert.equal(codeRange(7, 7), 'T-000007');
});

test('Russian plurals', () => {
  const forms = ['заготовка', 'заготовки', 'заготовок'];
  assert.deepEqual([1, 2, 5, 11, 21, 22, 112].map((k) => plural(k, forms)), [
    'заготовка', 'заготовки', 'заготовок', 'заготовок', 'заготовка', 'заготовки', 'заготовок',
  ]);
});
