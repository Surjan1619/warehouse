// Run with: npm test   (Node built-in test runner, no extra packages)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { NO_TYPE, groupByType, productLabel } from './productOptions.js';

const product = (id, name, type, extra = {}) => ({
  id,
  name,
  quantity: 1,
  product_type: type ? { id: type.length, name: type } : null,
  location: null,
  ...extra,
});

test('the label shows the name, the type, the quantity and the place', () => {
  assert.equal(
    productLabel(product(1, 'Мотор 600', 'Моторы', { quantity: 5, location: { name: 'Стеллаж А' } })),
    'Мотор 600 · Моторы — 5 шт. (Стеллаж А)',
  );
});

test('without a type or quantity the label stays short', () => {
  assert.equal(productLabel(product(1, 'Ручка', null, { quantity: null })), 'Ручка — 0 шт.');
});

test('products are grouped by type, goods without a type last', () => {
  const groups = groupByType([
    product(1, 'Пульт 4 кнопки', 'Пульты'),
    product(2, 'Ручка', null),
    product(3, 'Мотор 800', 'Моторы'),
    product(4, 'Мотор 600', 'Моторы'),
  ]);
  assert.deepEqual(
    groups.map((g) => [g.title, g.items.map((p) => p.id)]),
    [['Моторы', [4, 3]], ['Пульты', [1]], [NO_TYPE, [2]]],
  );
});

test('an empty list gives no groups', () => {
  assert.deepEqual(groupByType([]), []);
});
