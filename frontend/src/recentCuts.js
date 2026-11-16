// Recently made cuts, kept in the browser so a frequent job can be repeated
// with one click. Everything except load/save is a pure function.

export const MAX_RECENT = 5;
const STORAGE_KEY = 'recent_cuts';

/** Bring a request to the stored form: numbers and booleans only. */
export const makeEntry = (materialId, pieces) => ({
  material_id: Number(materialId),
  pieces: pieces.map((p) => ({ length_mm: Number(p.length_mm), used: Boolean(p.used) })),
});

/** Two requests are the same job if they ask for the same pieces of the same material, in any order. */
export const signature = (entry) =>
  `${entry.material_id}:${entry.pieces
    .map((p) => `${p.length_mm}${p.used ? 'u' : 's'}`)
    .sort()
    .join(',')}`;

export const isValidEntry = (entry) =>
  Boolean(entry) &&
  Number.isInteger(entry.material_id) &&
  entry.material_id > 0 &&
  Array.isArray(entry.pieces) &&
  entry.pieces.length > 0 &&
  entry.pieces.every((p) => p && Number.isInteger(p.length_mm) && p.length_mm > 0 && typeof p.used === 'boolean');

/** Put a job first in the list. A repeated job moves up instead of appearing twice. */
export const addRecent = (list, entry) =>
  [entry, ...list.filter((other) => signature(other) !== signature(entry))].slice(0, MAX_RECENT);

/** "3 000 × 2 + 1 000": equal lengths are collapsed, in order of first appearance. */
export const describePieces = (pieces) => {
  const counts = new Map();
  for (const piece of pieces) counts.set(piece.length_mm, (counts.get(piece.length_mm) || 0) + 1);
  return [...counts]
    .map(([length, count]) => `${length.toLocaleString('ru-RU')}${count > 1 ? ` × ${count}` : ''}`)
    .join(' + ');
};

/** Rows for the form on the cut page. */
export const toFormPieces = (entry) =>
  entry.pieces.map((p) => ({ length_mm: String(p.length_mm), used: p.used, times: '2' }));

// Storage can be missing or blocked (private window); the page must work without it.
export const loadRecent = (storage = globalThis.localStorage) => {
  try {
    const list = JSON.parse(storage.getItem(STORAGE_KEY));
    return Array.isArray(list) ? list.filter(isValidEntry).slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
};

export const saveRecent = (list, storage = globalThis.localStorage) => {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // Nothing to do: the list simply will not survive a reload
  }
};
