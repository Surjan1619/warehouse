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
  import: 'Приход по документу',
  reset: 'Очистка базы',
};

// What a database clearing deleted, per table
export const TABLE_LABELS = {
  activity_log: 'записей журнала',
  cut_operations: 'резок',
  stock_items: 'заготовок и кусков',
  orders: 'заказов',
  movements: 'движений товаров',
  products: 'товаров',
  assemblies: 'сборок',
  document_imports: 'документов поставщика',
  materials: 'материалов',
  locations: 'мест хранения',
  product_types: 'типов товаров',
};

// Groups of data a clearing can delete
export const CLEAR_GROUP_LABELS = { stock: 'склад', journal: 'журнал', catalog: 'справочники' };
