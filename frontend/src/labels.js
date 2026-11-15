// Display names for values stored by the backend

export const ROLE_LABELS = { admin: 'Администратор', worker: 'Работник склада' };

export const STATUS_LABELS = {
  in_stock: 'На складе',
  reserved: 'В резерве',
  used: 'Использована',
  cut: 'Разрезана',
  scrap: 'Отходы',
};

// Actions recorded in the activity journal
export const ACTION_LABELS = {
  receive: 'Приход',
  cut: 'Резка',
  use: 'Израсходовано',
  scrap: 'Отходы',
};
