// Wording of a supplier's document import: what each row becomes, what is wrong with it.
// Pure functions, tested in importText.test.js.
import { amount } from './productOptions.js';

const n = (value) => (value ?? 0).toLocaleString('ru-RU');

/** Russian plural: plural(5, ['заготовка', 'заготовки', 'заготовок']) -> 'заготовок'. */
export const plural = (count, [one, few, many]) => {
  const tens = Math.abs(count) % 100;
  const last = tens % 10;
  if (tens > 10 && tens < 20) return many;
  if (last === 1) return one;
  if (last >= 2 && last <= 4) return few;
  return many;
};

const PIECES = ['заготовка', 'заготовки', 'заготовок'];

/** Why a row cannot go into stock. */
export const PROBLEM_TEXT = {
  no_name: 'Нет наименования',
  no_quantity: 'Нет количества',
  bad_length: 'Длина записана непонятно',
  unknown_unit: 'Незнакомая единица измерения',
  metres_without_length: 'Количество в метрах, но длина не указана',
  not_whole_pieces: 'Метры не делятся на длину без остатка',
  fractional_quantity: 'Дробное количество штучного товара',
  unit_differs: 'Товар с этим кодом уже есть, но считается в других единицах',
};

/** Server messages about the whole file, in Russian. */
export const IMPORT_ERRORS = {
  'Not an Excel file': 'Это не файл Excel (.xlsx или .xlsm)',
  'The file is too large': 'Файл слишком большой',
  'The file has no sheets': 'В файле нет листов',
  'No table of goods in the file': 'В файле не найдена таблица с колонками «Наименование», «Ед. изм.», «Кол-во»',
  'No goods in the file': 'В таблице нет ни одной строки с товаром',
  'This document is already in stock': 'Этот документ уже добавлен на склад',
  'The document has rows that cannot be put into stock': 'В документе есть строки с ошибками, сначала исправьте файл',
  'Location not found': 'Место хранения не найдено',
  'Product type not found': 'Тип товара не найден',
};

/** What the document says: "3 045 м по 7 м" or "100 пар". */
export const rowSource = (row) => {
  if (row.quantity == null) return '—';
  const quantity = n(Number(row.quantity));
  if (row.length_mm) return `${quantity} ${row.unit} по ${n(row.length_mm / 1000)} м`;
  return `${quantity} ${row.unit}`;
};

/** What goes into stock: "435 заготовок × 7 000 мм" or "+100 пар". */
export const rowOutcome = (row) => {
  if (row.kind === 'stock') return `${n(row.pieces)} ${plural(row.pieces, PIECES)} × ${n(row.length_mm)} мм`;
  if (row.kind === 'goods') return `+${amount(row.count, row.unit)}`;
  return PROBLEM_TEXT[row.problem] ?? row.problem ?? '—';
};

/** The material or product the row matched by its code, or null when it will be created. */
export const rowTarget = (row) => row.material?.name ?? row.product?.name ?? null;

/** Rows that will create a new product: a type can be chosen for them. */
export const newGoodsRows = (rows) => rows.filter((r) => r.kind === 'goods' && !r.product);

/** {line: typeId} without the rows left without a type, as the server takes it. */
export const typesPayload = (choices) =>
  JSON.stringify(Object.fromEntries(Object.entries(choices).filter(([, id]) => id).map(([line, id]) => [line, Number(id)])));

export const summaryText = (s) => {
  const parts = [];
  if (s.stock_rows) {
    parts.push(`${n(s.stock_pieces)} ${plural(s.stock_pieces, PIECES)} (новых материалов: ${s.new_materials})`);
  }
  if (s.goods_rows) {
    parts.push(`товаров: ${s.goods_rows} ${plural(s.goods_rows, ['строка', 'строки', 'строк'])} (новых: ${s.new_products})`);
  }
  return parts.join('; ');
};

const code = (id) => `T-${String(id).padStart(6, '0')}`;

/** Numbers to write on the pieces of a row: "T-000101 … T-000535". */
export const codeRange = (first, last) => (first === last ? code(first) : `${code(first)} … ${code(last)}`);
