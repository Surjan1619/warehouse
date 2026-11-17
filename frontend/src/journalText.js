// Wording of activity journal entries: what was done and with what.
// Pure functions, tested in journalText.test.js.

const n = (value) => value.toLocaleString('ru-RU');
const mm = (value) => `${n(value)} мм`;

/** "Мотор 600 (Моторы)"; the name kept in the entry survives deleting the product. */
export const productName = (event) => {
  const name = event.product?.name ?? event.details?.product_name ?? 'товар';
  const type = event.product?.product_type?.name ?? event.details?.product_type;
  return type ? `${name} (${type})` : name;
};

const assemblyRef = (event) => (event.details?.assembly_id ? `, сборка №${event.details.assembly_id}` : '');

const remaining = (event) =>
  Number.isInteger(event.details?.quantity_after) ? `, осталось ${event.details.quantity_after} шт.` : '';

/** One line telling what the entry is about. */
export const describeEvent = (event) => {
  const code = event.stock_item?.code;
  const details = event.details ?? {};
  switch (event.action) {
    case 'receive':
      return event.quantity === 1
        ? `Принята заготовка ${code || ''} — ${mm(event.length_mm)}`
        : `Принято ${event.quantity} шт. по ${mm(details.piece_length_mm ?? 0)}`;
    case 'cut': {
      const pieces = (details.pieces_mm || []).map(n).join(' + ');
      return `Разрезана ${code || 'заготовка'} (${mm(event.length_mm)})${pieces ? `: ${pieces}` : ''}${
        details.remainder_mm ? `, остаток ${mm(details.remainder_mm)}` : ''
      }`;
    }
    case 'use':
      return `Израсходовано ${event.quantity} шт.${code ? ` (${code})` : ''}`;
    case 'scrap':
      return `В отходы ${code || 'заготовка'}`;
    case 'product_receive':
      return `${details.new ? 'Новый товар' : 'Пополнение'}: ${productName(event)} +${event.quantity} шт.${remaining(event)}`;
    case 'product_issue':
      return `Выдано: ${productName(event)} −${event.quantity} шт.${remaining(event)}${assemblyRef(event)}`;
    case 'assemble': {
      const parts = [];
      const cuts = details.cut_operation_ids?.length ?? 0;
      if (cuts) parts.push(`резок: ${cuts}`);
      const goods = (details.products || []).map((p) => `${p.name ?? `товар №${p.product_id}`} × ${p.quantity}`);
      if (goods.length) parts.push(`товары: ${goods.join(', ')}`);
      return `Сборка №${details.assembly_id ?? '?'}${details.name ? ` «${details.name}»` : ''}${
        parts.length ? ` — ${parts.join('; ')}` : ''
      }`;
    }
    default:
      return event.action;
  }
};

/** What the entry concerns, for the "Материал / товар" column. */
export const subjectOf = (event) => {
  if (event.action === 'product_receive' || event.action === 'product_issue') return productName(event);
  return event.material?.name || '—';
};

/** Lengths make sense only for cuttable stock. */
export const lengthOf = (event) => (event.material || event.stock_item ? n(event.length_mm) : '—');
