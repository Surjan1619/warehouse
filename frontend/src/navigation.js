// Sections of the site and the pages inside each. The top bar shows the
// sections, the row under it shows the pages of the current one, and the home
// page shows them all as tiles. Pure data and functions, tested in navigation.test.js.

export const SECTIONS = [
  {
    key: 'stock',
    title: 'Остатки',
    hint: 'Что есть на складе',
    pages: [
      { path: '/stock', title: 'Заготовки', hint: 'Трубы и профили по материалам, поиск по номеру' },
      { path: '/products', title: 'Товары', hint: 'Штучные товары и их количество' },
    ],
  },
  {
    key: 'receive',
    title: 'Приход',
    hint: 'Добавить на склад',
    pages: [
      { path: '/receive', title: 'Заготовки', hint: 'Принять трубы и профили, получить номера' },
      { path: '/receive/products', title: 'Товары', hint: 'Пополнить товар или завести новый' },
    ],
  },
  {
    key: 'issue',
    title: 'Расход',
    hint: 'Сборка, резка и выдача со склада',
    pages: [
      { path: '/assembly', title: 'Сборка', hint: 'Отрезки и товары для одного изделия в одном окне' },
      { path: '/cut', title: 'Резка', hint: 'Разрезать заготовку, записать куски и остаток' },
      { path: '/issue', title: 'Товары', hint: 'Выдать штучный товар со склада' },
    ],
  },
  {
    key: 'catalog',
    title: 'Справочники',
    hint: 'Материалы и места хранения',
    pages: [{ path: '/catalog', title: 'Материалы и места', hint: 'Что режется и где лежит' }],
  },
  {
    key: 'admin',
    title: 'Администрирование',
    hint: 'Только для администратора',
    adminOnly: true,
    pages: [
      { path: '/admin', title: 'Пользователи', hint: 'Учётные записи работников' },
      { path: '/admin/types', title: 'Типы товаров', hint: 'Группы штучных товаров' },
      { path: '/journal', title: 'Журнал', hint: 'Кто, что и когда делал на складе' },
    ],
  },
];

/** Sections the user may open: the admin one only for an administrator. */
export const visibleSections = (admin) => SECTIONS.filter((section) => admin || !section.adminOnly);

/** The section a page belongs to, or null for pages outside the sections (home). */
export const sectionOf = (path) =>
  SECTIONS.find((section) => section.pages.some((page) => page.path === path)) ?? null;

/** Where a click on the section in the top bar leads: its first page. */
export const sectionHome = (section) => section.pages[0].path;
