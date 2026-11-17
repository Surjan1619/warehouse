// Draft of an assembly: the pieces to cut and the goods to take, kept in the
// browser until the worker finishes the assembly. Stock does not change while
// it is a draft. Everything except load/save is a pure function.

const STORAGE_KEY = 'assembly_draft';

/** A random key for the draft; the server saves an assembly with the same key only once. */
export const newKey = () =>
  globalThis.crypto?.randomUUID?.().replaceAll('-', '') ??
  `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;

export const newDraft = (key = newKey()) => ({ key, name: '', note: '', cuts: [], goods: [], nextId: 1 });

export const isEmpty = (draft) => draft.cuts.length === 0 && draft.goods.length === 0;

const positiveInt = (value) => Number.isInteger(value) && value > 0;

export const isValidCut = (line) =>
  positiveInt(line.material_id) && positiveInt(line.length_mm) && positiveInt(line.quantity) && typeof line.used === 'boolean';

export const isValidGoods = (line) => positiveInt(line.product_id) && positiveInt(line.quantity);

/**
 * Add pieces. The same length of the same material with the same destination
 * is one line: its quantity grows instead of a second line appearing.
 */
export const addCut = (draft, { material_id, length_mm, quantity, used }) => {
  const same = draft.cuts.find(
    (l) => l.material_id === material_id && l.length_mm === length_mm && l.used === used,
  );
  if (same) {
    return { ...draft, cuts: draft.cuts.map((l) => (l === same ? { ...l, quantity: l.quantity + quantity } : l)) };
  }
  const line = { id: draft.nextId, material_id, length_mm, quantity, used };
  return { ...draft, cuts: [...draft.cuts, line], nextId: draft.nextId + 1 };
};

/** Add goods; the same product is one line with the quantities summed. */
export const addGoods = (draft, { product_id, quantity }) => {
  const same = draft.goods.find((l) => l.product_id === product_id);
  if (same) {
    return { ...draft, goods: draft.goods.map((l) => (l === same ? { ...l, quantity: l.quantity + quantity } : l)) };
  }
  const line = { id: draft.nextId, product_id, quantity };
  return { ...draft, goods: [...draft.goods, line], nextId: draft.nextId + 1 };
};

/** `kind` is "cuts" or "goods". */
export const updateLine = (draft, kind, id, changes) => ({
  ...draft,
  [kind]: draft[kind].map((l) => (l.id === id ? { ...l, ...changes } : l)),
});

export const removeLine = (draft, kind, id) => ({ ...draft, [kind]: draft[kind].filter((l) => l.id !== id) });

/** Body of POST /assemblies/plan. Lines being edited (not valid yet) are left out. */
export const planRequest = (draft) => {
  const byMaterial = new Map();
  for (const line of draft.cuts.filter(isValidCut)) {
    if (!byMaterial.has(line.material_id)) byMaterial.set(line.material_id, []);
    byMaterial.get(line.material_id).push({ length_mm: line.length_mm, quantity: line.quantity, used: line.used });
  }
  return {
    materials: [...byMaterial].map(([material_id, pieces]) => ({ material_id, pieces })),
    products: draft.goods.filter(isValidGoods).map(({ product_id, quantity }) => ({ product_id, quantity })),
  };
};

/** Same string for drafts that ask the server the same question. */
export const planSignature = (draft) => JSON.stringify(planRequest(draft));

/** Every line is filled in correctly, so the plan covers the whole draft. */
export const allLinesValid = (draft) => draft.cuts.every(isValidCut) && draft.goods.every(isValidGoods);

/** Body of POST /assemblies: exactly the cuts of the plan the worker saw. */
export const commitRequest = (draft, plan) => ({
  client_key: draft.key,
  name: draft.name.trim() || null,
  note: draft.note.trim() || null,
  cuts: plan.materials.flatMap((m) =>
    m.cuts.map((cut) => ({
      source_item_id: cut.item.id,
      pieces: cut.pieces.map((p) => ({ length_mm: p.length_mm, used: p.used })),
    })),
  ),
  products: plan.products.map((p) => ({ product_id: p.product.id, quantity: p.quantity })),
});

/** How many pieces of a line found no stock item, in the plan. */
export const unplacedOf = (plan, line) => {
  const material = plan?.materials.find((m) => m.material.id === line.material_id);
  if (!material) return 0;
  const missing = material.unplaced.filter((p) => p.length_mm === line.length_mm && p.used === line.used).length;
  return Math.min(missing, line.quantity);
};

/** What is in stock of a product, per the plan; null when the plan does not know it yet. */
export const availableOf = (plan, productId) =>
  plan?.products.find((p) => p.product.id === productId)?.available ?? null;

/** Totals for the summary: pieces and millimetres per material, pieces of goods. */
export const totals = (draft) => {
  const materials = new Map();
  for (const line of draft.cuts.filter(isValidCut)) {
    const total = materials.get(line.material_id) ?? { pieces: 0, length_mm: 0, used_mm: 0 };
    total.pieces += line.quantity;
    total.length_mm += line.length_mm * line.quantity;
    if (line.used) total.used_mm += line.length_mm * line.quantity;
    materials.set(line.material_id, total);
  }
  const goods = draft.goods.filter(isValidGoods).reduce((sum, l) => sum + l.quantity, 0);
  return { materials, goods };
};

const isValidDraft = (draft) =>
  Boolean(draft) &&
  typeof draft.key === 'string' &&
  draft.key.length >= 8 &&
  typeof draft.name === 'string' &&
  typeof draft.note === 'string' &&
  Array.isArray(draft.cuts) &&
  Array.isArray(draft.goods) &&
  Number.isInteger(draft.nextId);

// Storage can be missing or blocked (private window); the page must work without it.
export const loadDraft = (storage = globalThis.localStorage) => {
  try {
    const draft = JSON.parse(storage.getItem(STORAGE_KEY));
    return isValidDraft(draft) ? draft : newDraft();
  } catch {
    return newDraft();
  }
};

export const saveDraft = (draft, storage = globalThis.localStorage) => {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // Nothing to do: the draft simply will not survive a reload
  }
};
