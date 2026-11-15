# Warehouse Management System (WMS)

Система складского учёта для производства роллетных и секционных ворот. Главная задача — поштучный учёт длинномерных заготовок (профили, направляющие, валы): каждая труба хранится отдельной записью, при резке превращается в несколько новых, и по любому куску видно, от какой трубы он отрезан и в какой заказ ушёл.

Проект в ранней стадии. На сайте можно вести справочники, принимать заготовки на склад, резать их и добавлять штучные товары. Заказы работают в API, но страниц для них ещё нет — пока ими можно пользоваться через Swagger на `/docs`.

## Стек

| Часть | Технологии |
|---|---|
| Бэкенд | Python, FastAPI, SQLAlchemy 2.0 (async), asyncpg, Alembic, Pydantic v2 |
| База данных | PostgreSQL |
| Авторизация | JWT (HS256), пароли через passlib (`sha256_crypt`) |
| Фронтенд | React 19, React Router 7, Vite 8, oxlint |

## Запуск через Docker

Нужны Docker и плагин Compose.

Скопируйте [.env.example](.env.example) в `.env` и задайте `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `JWT_SECRET` и `ADMIN_PASSWORD`. Затем:

```bash
docker compose up --build
```

Поднимутся три контейнера: PostgreSQL, бэкенд (`http://localhost:8000`, миграции применяются при старте) и фронтенд (`http://localhost:5173`). Каталоги `app/`, `alembic/`, `scripts/` и `frontend/src/` подключены как тома, поэтому правки кода подхватываются без пересборки. После изменения `requirements.txt` или `frontend/package.json` нужна пересборка с `--build`.

Создать администратора (или сменить ему пароль) по значениям `ADMIN_USERNAME` и `ADMIN_PASSWORD` из `.env`. После правки `.env` сначала выполните `docker compose up -d`, чтобы контейнер получил новые значения:

```bash
docker compose exec backend python scripts/create_admin.py
```

Остановить (данные БД сохраняются в томе `pgdata`):

```bash
docker compose down
```

Запустить только базу, а бэкенд и фронтенд — локально:

```bash
docker compose up -d db
```

## Запуск без Docker

### 1. База данных и окружение

Нужен запущенный PostgreSQL с созданной базой. В корне проекта создайте файл `.env`:

```
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/DBNAME
JWT_SECRET=длинная-случайная-строка
ADMIN_PASSWORD=пароль-администратора
```

Необязательные переменные: `ALGORITHM` (по умолчанию `HS256`) и `ACCESS_TOKEN_EXPIRE_MINUTES` (по умолчанию `30`).

### 2. Бэкенд

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

На Debian/Ubuntu для первой команды нужен пакет `python3-venv` (для Python 3.14 — `python3.14-venv`). Зависимости проверены на Python 3.14.

```bash
alembic upgrade head
```

```bash
python scripts/create_admin.py
```

Скрипт берёт имя и пароль из `ADMIN_USERNAME` и `ADMIN_PASSWORD` в `.env`. Если такой пользователь уже есть, скрипт заменит ему пароль.

```bash
uvicorn app.main:app --reload
```

API поднимется на `http://localhost:8000`, документация Swagger — на `http://localhost:8000/docs`.

### 3. Фронтенд

```bash
cd frontend
```

```bash
npm install
```

```bash
npm run dev
```

Приложение откроется на `http://localhost:5173`. Этот адрес — единственный, разрешённый в CORS бэкенда.

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — устройство бэкенда и фронтенда, путь запроса, авторизация
- [docs/API.md](docs/API.md) — все эндпоинты с форматами запросов и ответов
- [docs/DATABASE.md](docs/DATABASE.md) — таблицы, связи, история миграций
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) — найденные ошибки и недоделки, по приоритету
- [CLAUDE.md](CLAUDE.md) — инструкции для Claude Code

## Состояние функций

| Функция | Состояние |
|---|---|
| Вход, роли «администратор» и «работник склада» | Работает |
| Создание и отключение пользователей администратором | Работает |
| Штучные товары: список, добавление, удаление | Работает |
| Справочники: материалы, типы товаров, места хранения | Работает |
| Приход заготовок и список с фильтром по статусу | Работает |
| Заказы, резерв заготовок за заказом | API работает, страниц во фронтенде нет |
| Резка с учётом остатков и отходов | Работает (без привязки к заказу на сайте) |
| Подбор самой экономной заготовки под нужные куски | Работает |
| История происхождения заготовки | API работает, страниц во фронтенде нет |
| Редактирование товара | Есть только схема `ProductUpdate`, эндпоинта нет |
| Продажа штучного товара | Логика в `app/repo/inventory.py`, эндпоинта нет |
| Тесты | Нет |
