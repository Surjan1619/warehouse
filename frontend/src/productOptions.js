// Product choices in select lists: the name together with the type, grouped by
// type, so that equal or similar names of different types are told apart.
// Pure functions, tested in productOptions.test.js.

export const NO_TYPE = 'Без типа';

/** What one unit of quantity is. 100 pairs stay 100: the unit tells they are pairs. */
export const UNITS = ['шт', 'пар', 'кмт'];
export const UNIT_NAMES = { шт: 'штуки', пар: 'пары', кмт: 'комплекты' };

/** The unit of a product; goods added before units existed are pieces. */
export const unitOf = (p) => p?.unit || 'шт';

/** "5 шт.", "100 пар", "60 кмт". */
export const amount = (n, unit = 'шт') => `${n ?? 0} ${unit === 'шт' ? 'шт.' : unit}`;

/** "Ролик · Ролики — 100 пар (Стеллаж А)"; the type is left out when there is none. */
export const productLabel = (p) =>
  `${p.name}${p.product_type ? ` · ${p.product_type.name}` : ''} — ${amount(p.quantity, unitOf(p))}` +
  (p.location ? ` (${p.location.name})` : '');

/**
 * Products grouped by type for <optgroup>: groups sorted by type name, goods
 * without a type last, products inside a group sorted by name.
 */
export const groupByType = (products) => {
  const groups = new Map();
  for (const p of products) {
    const title = p.product_type?.name ?? NO_TYPE;
    if (!groups.has(title)) groups.set(title, []);
    groups.get(title).push(p);
  }
  const byName = (a, b) => (a.name ?? '').localeCompare(b.name ?? '', 'ru');
  return [...groups]
    .sort(([a], [b]) => (a === NO_TYPE) - (b === NO_TYPE) || a.localeCompare(b, 'ru'))
    .map(([title, items]) => ({ title, items: [...items].sort(byName) }));
};
