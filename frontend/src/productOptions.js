// Product choices in select lists: the name together with the type, grouped by
// type, so that equal or similar names of different types are told apart.
// Pure functions, tested in productOptions.test.js.

export const NO_TYPE = 'Без типа';

/** "Мотор 600 · Моторы — 5 шт. (Стеллаж А)"; the type is left out when there is none. */
export const productLabel = (p) =>
  `${p.name}${p.product_type ? ` · ${p.product_type.name}` : ''} — ${p.quantity ?? 0} шт.` +
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
