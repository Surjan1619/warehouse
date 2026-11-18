// Run with: npm test   (Node built-in test runner, no extra packages)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { describeEvent, lengthOf, productName, subjectOf } from './journalText.js';

const motor = { id: 5, name: 'Мотор 600', product_type: { id: 1, name: 'Моторы' } };
const event = (action, extra = {}) => ({
  action,
  quantity: 1,
  length_mm: 0,
  material: null,
  stock_item: null,
  product: null,
  details: null,
  ...extra,
});

test('an issue of goods names the product, its type and what is left', () => {
  const e = event('product_issue', { product: motor, quantity: 2, details: { quantity_after: 3 } });
  assert.equal(describeEvent(e), 'Выдано: Мотор 600 (Моторы) −2 шт., осталось 3 шт.');
  assert.equal(subjectOf(e), 'Мотор 600 (Моторы)');
  assert.equal(lengthOf(e), '—');
});

test('an issue made for an assembly refers to it', () => {
  const e = event('product_issue', { product: motor, details: { quantity_after: 0, assembly_id: 4 } });
  assert.equal(describeEvent(e), 'Выдано: Мотор 600 (Моторы) −1 шт., осталось 0 шт., сборка №4');
});

test('a restock and a new product are told apart', () => {
  assert.equal(
    describeEvent(event('product_receive', { product: motor, quantity: 5, details: { quantity_after: 8 } })),
    'Пополнение: Мотор 600 (Моторы) +5 шт., осталось 8 шт.',
  );
  assert.equal(
    describeEvent(event('product_receive', { product: motor, quantity: 3, details: { quantity_after: 3, new: true } })),
    'Новый товар: Мотор 600 (Моторы) +3 шт., осталось 3 шт.',
  );
});

test('a deleted product keeps the name stored in the entry', () => {
  const e = event('product_issue', { details: { product_name: 'Ручка', product_type: null, from_movements: true } });
  assert.equal(productName(e), 'Ручка');
  assert.equal(describeEvent(e), 'Выдано: Ручка −1 шт.');
});

test('an assembly lists its cuts and goods', () => {
  const e = event('assemble', {
    quantity: 0,
    details: {
      assembly_id: 7,
      name: 'Ворота',
      cut_operation_ids: [1, 2],
      products: [{ product_id: 5, name: 'Мотор 600', quantity: 1 }, { product_id: 9, quantity: 2, unit: 'пар' }],
    },
  });
  assert.equal(describeEvent(e), 'Сборка №7 «Ворота» — резок: 2; товары: Мотор 600 — 1 шт., товар №9 — 2 пар');
  assert.equal(subjectOf(e), '—');
});

test('entries about stock items keep their wording', () => {
  const material = { id: 1, name: 'Труба 40x20' };
  const cut = event('cut', {
    material,
    stock_item: { code: 'T-000012' },
    length_mm: 6000,
    details: { pieces_mm: [3000, 1500], remainder_mm: 1500 },
  });
  // Russian digit groups are separated by a no-break space
  const plain = (text) => text.replace(/\s/g, ' ');
  assert.equal(plain(describeEvent(cut)), 'Разрезана T-000012 (6 000 мм): 3 000 + 1 500, остаток 1 500 мм');
  assert.equal(subjectOf(cut), 'Труба 40x20');
  assert.equal(plain(lengthOf(cut)), '6 000');
});

test('a clearing of the database tells what was deleted', () => {
  const e = event('reset', { quantity: 0, details: { groups: ['stock', 'journal'], deleted: { stock_items: 4, activity_log: 9 } } });
  assert.equal(describeEvent(e), 'База очищена: склад, журнал; удалено строк: 13');
  assert.equal(subjectOf(e), '—');
});

test('goods counted in pairs or sets show their unit, the number stays as it came', () => {
  const roller = { id: 3, name: 'Ролик RGV/77', product_type: null };
  assert.equal(
    describeEvent(event('product_receive', { product: roller, quantity: 100, details: { quantity_after: 100, unit: 'пар', new: true } })),
    'Новый товар: Ролик RGV/77 +100 пар, осталось 100 пар',
  );
  assert.equal(
    describeEvent(event('product_issue', { product: roller, quantity: 5, details: { quantity_after: 95, unit: 'пар' } })),
    'Выдано: Ролик RGV/77 −5 пар, осталось 95 пар',
  );
});

test('an import of a supplier document tells what it brought', () => {
  const e = event('import', {
    quantity: 38,
    details: { number: '618E/7', supplier: 'ООО Поставщик', rows: 38, stock_pieces: 3075, new_materials: 12, new_products: 13 },
  });
  assert.equal(
    describeEvent(e).replace(/\s/g, ' '),
    'Приход по документу № 618E/7, ООО Поставщик — строк: 38, заготовок: 3 075, новых материалов: 12, новых товаров: 13',
  );
  assert.equal(subjectOf(e), '—');
});
