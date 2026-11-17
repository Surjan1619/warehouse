// Display names for values stored by the backend

export const ROLE_LABELS = { admin: 'Администратор', worker: 'Работник склада' };

export const STATUS_LABELS = {
  in_stock: 'На складе',
  reserved: 'В резерве',
  used: 'Использована',
  cut: 'Разрезана',
  scrap: 'Отходы',
  cancelled: 'Резка отменена',
};

// Actions recorded in the activity journal
export const ACTION_LABELS = {
  receive: 'Приход заготовок',
  cut: 'Резка',
  use: 'Израсходовано',
  scrap: 'Отходы',
  product_receive: 'Приход товара',
  product_issue: 'Расход товара',
  assemble: 'Сборка',
};
