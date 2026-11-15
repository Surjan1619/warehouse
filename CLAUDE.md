# CLAUDE.md

WMS (Warehouse Management System): учёт товаров на складе. Бэкенд на FastAPI + async SQLAlchemy + PostgreSQL, фронтенд на React 19 + Vite. Интерфейс и общение с пользователем — на русском.

Подробности: [README.md](README.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/API.md](docs/API.md), [docs/DATABASE.md](docs/DATABASE.md), [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

## Команды

Все команды бэкенда запускаются из корня репозитория: `.env` читается по относительному пути.

```bash
# Бэкенд (http://localhost:8000, Swagger на /docs)
source venv/bin/activate
uvicorn app.main:app --reload

# Миграции
alembic upgrade head
alembic revision --autogenerate -m "описание"

# Администратор: создаёт его или меняет пароль по ADMIN_USERNAME / ADMIN_PASSWORD из .env
python scripts/create_admin.py

# Фронтенд (http://localhost:5173)
cd frontend
npm install
npm run dev
npm run lint     # oxlint
npm run build
```

Через Docker (PostgreSQL + бэкенд + фронтенд, код подключён томами, миграции при старте):

```bash
docker compose up --build
docker compose exec backend python scripts/create_admin.py
docker compose exec backend alembic revision --autogenerate -m "описание"
docker compose up -d db      # только база, остальное локально
```

Compose берёт `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` из `.env` (образец — `.env.example`) и сам подставляет бэкенду `DATABASE_URL` с хостом `db`.

Тестов в проекте нет. Проверять изменения нужно вручную: Swagger на `/docs` или фронтенд.

## Структура

```
app/
  main.py                  # FastAPI-приложение, CORS, подключение роутеров
  core/                    # config (pydantic-settings), db (async engine), jwt, security
  middleware/auth.py       # проверка Bearer-токена на всех путях, кроме публичных
  api/deps.py              # get_current_user (подключён ко всем роутерам), require_admin
  core/errors.py           # DomainError, NotFoundError — ошибки бизнес-правил
  api/routers/             # auth, users, products, locations, materials, orders, stock_items, cuts
  repo/crud.py             # запросы к БД: users, products, product_types, locations
  repo/stock.py            # материалы, заказы, заготовки (поштучный учёт)
  repo/cutting.py          # резка заготовки: plan_cut, cut_item
  repo/inventory.py        # sell_product для штучных товаров (без HTTP-эндпоинта)
  models/Alchemy_models.py # все ORM-модели и Base
  schemas/                 # Pydantic-схемы: user, product (+ location), stock, inventory
alembic/versions/          # миграции
scripts/create_admin.py
frontend/src/App.jsx       # маршруты, вход, главная, пользователи
frontend/src/api.js        # вызовы API, сессия (токен и пользователь в localStorage)
frontend/src/hooks.js      # useList, useAction — общая логика страниц
frontend/src/labels.js     # русские названия ролей и статусов
frontend/src/components/   # Layout (шапка), Messages (ошибка / успех)
frontend/src/pages/        # StockPage, CutPage, ProductsPage, CatalogPage
```

## Правила работы с кодом

- **Слои.** Роутер принимает и валидирует запрос, вызывает функцию из `app/repo/`, возвращает Pydantic-схему. SQL-запросы в роутерах не писать. Каталог `app/service/` пуст.
- **Два вида учёта.** Штучные товары — `products` с количеством. Всё, что режется, — `stock_items`: одна строка на физическую заготовку, длины в целых миллиметрах. Заготовки не удаляются, а меняют статус (`in_stock`, `reserved`, `used`, `cut`, `scrap`); на этом держится история происхождения.
- **Потери на рез по умолчанию не учитываются** (`kerf_mm = 0`, решение владельца от 15.11.2026): 7000 мм на 3000 + 3000 дают остаток ровно 1000. Учёт включается для отдельного материала полем «Ширина реза» в справочнике; логика `plan_cut` для ненулевого реза сохранена.
- **Инвариант резки:** длина исходной заготовки = сумма длин результатов + `kerf_loss_mm`. Любое изменение `app/repo/cutting.py` должно его сохранять. Фронтенд раскрой не считает: предпросмотр приходит от `POST /cuts/suggest`.
- **Подбор заготовки** (`suggest_sources`) ранжирует по правилу best fit: меньше остаток — выше. Это решение владельца от 15.11.2026 («сначала самые экономные»). Подбор ищет одну заготовку под все куски, раскладки по нескольким нет.
- **Ошибки в `repo`.** Бросать `DomainError` / `NotFoundError` из `app/core/errors.py`, а не `HTTPException`; обработчик в `main.py` превращает их в ответ.
- **Перечитывание после commit.** У сессии `expire_on_commit=False`, поэтому объект, уже лежащий в сессии, хранит старые значения связей. Запрос, который должен вернуть свежие связи, выполнять с `.execution_options(populate_existing=True)`, как в `stock.get_item`.
- **Только async.** Сессия — `AsyncSession` через `Depends(get_db)`; запросы в стиле SQLAlchemy 2.0 (`select(...)`, `await db.execute(...)`).
- **Связи загружать явно.** В async-режиме ленивая загрузка падает. Если схема ответа содержит вложенные объекты (`ProductRead.product_type`, `.location`), в запросе нужен `joinedload`, как в `get_all_products`.
- **Изменение моделей = миграция.** После правки `Alchemy_models.py` создать ревизию через `alembic revision --autogenerate` и просмотреть её вручную. Для внешних ключей задавать имя ограничения явно: в ревизии `79c14ac440ea` стоит `None`, из-за чего её `downgrade` не сработает.
- **Новый роутер** нужно подключить в `app/main.py` через `include_router` с `dependencies=authenticated`, иначе он примет токен отключённого пользователя. Если эндпоинт должен быть доступен без токена, добавить путь в список в `app/middleware/auth.py`.
- **Права.** Роли — `admin` и `worker`. Для действий только администратора использовать `Depends(require_admin)`. Скрытие кнопок во фронтенде защитой не считается.
- **Пользователей не удалять**, а отключать через `is_active`: на них ссылается `cut_operations.user_id`.
- **БД — только PostgreSQL**: используется `JSONB` и драйвер `asyncpg`.
- **Новая страница фронтенда** — отдельный файл в `frontend/src/pages/`, маршрут в `App.jsx`, ссылка в `components/Layout.jsx`. Списки загружать через `useList`, действия выполнять через `useAction`, как в `pages/ProductsPage.jsx`. Файл с компонентами не должен экспортировать ничего, кроме компонентов (правило oxlint), константы класть в `labels.js`.
- **Фронтенд.** Запросы делать через `api()` из `frontend/src/api.js`, а не через `fetch` напрямую: она добавляет токен и обрабатывает 401. Адрес API задаётся в `VITE_API_URL` (по умолчанию `http://localhost:8000`). CORS на бэкенде разрешает только `http://localhost:5173`.
- **Секреты.** `.env` в git не попадает. Значения из него не выводить и не коммитить.

## Что нужно знать заранее

Полный список с объяснениями — в [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md). Самое важное:

- Окружение собрано под Python 3.14. При обновлении зависимостей проверять совместимость с ним: `asyncpg` ниже 0.32 и `sqlalchemy` ниже 2.0.57 из прежнего `requirements.txt` на 3.14 не работали.
- PostgreSQL на машине разработчика не установлен, база работает только в Docker (`docker compose up -d db`).
- Во фронтенде есть приход заготовок, резка, товары и справочники. Заказов, резерва и истории заготовки там нет: для них есть только API. Привязку кусков к заказу при резке владелец отложил на потом (решение от 15.11.2026).
- `AuthMiddleware` должен добавляться в `main.py` раньше `CORSMiddleware` и возвращать `JSONResponse`, а не бросать `HTTPException`: исключение из middleware превращается в 500.
- Открытой регистрации нет: первого администратора создаёт `scripts/create_admin.py`, остальных — администратор.
- Работник (`worker`) пока может всё, кроме управления пользователями.
