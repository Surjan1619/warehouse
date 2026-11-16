// Splitting a long list into pages. Pure functions, tested in pagination.test.js.

export const PAGE_SIZE = 50;

/** Number of pages for `total` items; an empty list still has one (empty) page. */
export const pageCount = (total, size = PAGE_SIZE) => Math.max(1, Math.ceil(total / size));

/** Keep a page index inside the list, e.g. after items were cut and the list got shorter. */
export const clampPage = (page, total, size = PAGE_SIZE) => Math.min(Math.max(0, page), pageCount(total, size) - 1);

/** "51–100 из 230": which items the page shows. */
export const pageRange = (page, total, size = PAGE_SIZE) => {
  if (total === 0) return '0 из 0';
  const first = page * size + 1;
  const last = Math.min(total, (page + 1) * size);
  return `${first}–${last} из ${total}`;
};

/** Query string for a page of /stock-items/page; empty filters are left out. */
export const pageQuery = ({ status, materialId, page, size = PAGE_SIZE }) => {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (materialId) params.set('material_id', String(materialId));
  params.set('limit', String(size));
  params.set('offset', String(page * size));
  return params.toString();
};

/** Millimetres as metres for people: 22500 → "22,5 м". */
export const metres = (mm) => `${(mm / 1000).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} м`;
