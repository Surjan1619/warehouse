# База данных

PostgreSQL, драйвер `asyncpg`. Все модели описаны в `app/models/Alchemy_models.py`.

## Связи

Штучные товары (учёт по количеству):

```
product_types 1 ──── * products * ──── 1 locations
                         │
                         1
                         │
                         *
                     movements
```

Поштучный учёт того, что режется:

```
materials 1 ──── * stock_items * ──── 1 orders
                     │  ▲   │
     parent_id ──────┘  │   └──── * ──── 1 locations
     (сама на себя)     │
                        │ cut_operation_id (кто её создал)
                        │
                  cut_operations ──── source_item_id ───▶ stock_items
                        │
                        * ──── 1 users
```

`users` связана с `cut_operations` (кто резал) и `stock_items` (кто создал запись).

## Таблицы

### `users`

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `username` | varchar(50) | уникальный, индекс |
| `password_hash` | varchar(255) | passlib `sha256_crypt` |
| `role` | varchar(50) | `admin` или `worker` |
| `is_active` | boolean | по умолчанию `true`; отключённый пользователь не может войти |

### `product_types`

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `name` | varchar(100) | уникальный |
| `required_attributes` | JSONB | nullable; какие характеристики обязательны для товаров этого типа. При создании товара не проверяется |

### `locations`

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `name` | varchar(50) | уникальный |
| `capacity` | integer | nullable; заполненность не проверяется |

### `products`

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `name` | varchar(100) | nullable в БД, но обязателен в схеме `ProductRead` |
| `length`, `width`, `thickness`, `weight` | float | nullable |
| `shape` | varchar(50) | nullable |
| `quantity` | integer | nullable |
| `product_type_id` | integer | FK → `product_types.id`, nullable |
| `location_id` | integer | FK → `locations.id`, nullable |

### `movements`

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `product_id` | integer | FK → `products.id`, обязателен |
| `change_type` | varchar(50) | `cut_source`, `cut_result`, `sale`, `purchase` |
| `quantity_changed` | integer | со знаком: расход отрицательный |
| `created_at` | timestamp | `now()` на стороне БД |

У внешнего ключа `movements.product_id` нет каскада, поэтому товар с историей движений удалить не получится: БД вернёт ошибку целостности.

### `materials`

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `name` | varchar(100) | |
| `kind` | varchar(50) | nullable; вид материала |
| `sku` | varchar(50) | nullable, уникальный |
| `color` | varchar(50) | nullable |
| `kerf_mm` | integer | ширина реза, по умолчанию 0 (потери на рез не учитываются) |
| `min_usable_length_mm` | integer | порог отходов, по умолчанию 300 |

### `orders`

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `number` | varchar(50) | уникальный; автоматически `ORD-00001` |
| `customer_name` | varchar(150) | |
| `customer_phone`, `address`, `gate_type`, `note` | varchar | nullable |
| `width_mm`, `height_mm` | integer | nullable; размеры ворот |
| `status` | varchar(20) | `new`, `in_progress`, `done`, `cancelled` |
| `created_at` | timestamp | `now()` |

### `stock_items`

Одна строка — одна физическая заготовка. Строки не удаляются: разрезанная заготовка получает статус `cut`.

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK; из него строится номер `T-000123` |
| `material_id` | integer | FK → `materials.id` |
| `length_mm` | integer | больше 0 (check-ограничение) |
| `status` | varchar(20) | `in_stock`, `reserved`, `used`, `cut`, `scrap` |
| `location_id` | integer | FK → `locations.id`, nullable |
| `parent_id` | integer | FK → `stock_items.id`, nullable; от какой заготовки отрезана |
| `cut_operation_id` | integer | FK → `cut_operations.id`, nullable; какой резкой создана |
| `order_id` | integer | FK → `orders.id`, nullable |
| `note` | varchar(500) | nullable |
| `created_by_id` | integer | FK → `users.id`, nullable; кто принял заготовку или сделал резку, из которой она получилась. Пусто у заготовок, принятых до 15.11.2026 |
| `created_at` | timestamp | `now()` |

### `cut_operations`

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `source_item_id` | integer | FK → `stock_items.id`; что резали |
| `user_id` | integer | FK → `users.id`, nullable; кто резал |
| `kerf_mm` | integer | ширина реза в этой операции |
| `kerf_loss_mm` | integer | сколько длины ушло в пропил |
| `note` | varchar(500) | nullable |
| `created_at` | timestamp | `now()` |

### `activity_log`

Журнал действий. Только дополняется: записи не меняются и не удаляются.

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | integer | PK |
| `created_at` | timestamp | `now()`, индекс |
| `user_id` | integer | FK → `users.id`, nullable; кто сделал |
| `action` | varchar(30) | `receive` (приход), `cut` (резка), `use` (израсходовано), `scrap` (отходы) |
| `material_id` | integer | FK → `materials.id`, nullable |
| `stock_item_id` | integer | FK → `stock_items.id`, nullable; заготовка, если действие касается одной |
| `cut_operation_id` | integer | FK → `cut_operations.id`, nullable |
| `quantity` | integer | сколько штук, по умолчанию 1 |
| `length_mm` | integer | их суммарная длина, по умолчанию 0 |
| `details` | JSONB | nullable; дополнительные сведения |

Что записывается:

| Действие | Когда | `quantity` | `length_mm` | Прочее |
|---|---|---|---|---|
| `receive` | приход; одна запись на всю поставку | число заготовок | их суммарная длина | `details`: длина одной и список id; `stock_item_id` только при одной заготовке |
| `cut` | резка | 1 | длина разрезанной заготовки | `stock_item_id` — что резали; `details`: длины кусков и остаток |
| `use` | куски помечены использованными: при резке, кнопкой `use`, при закрытии заказа | число кусков | их суммарная длина | при резке одна запись на все использованные куски |
| `scrap` | остаток ушёл в отходы при резке или заготовка списана вручную | 1 | длина | `stock_item_id` — что списано |

Записи резки (`cut`, `use`, `scrap`) связаны общим `cut_operation_id`. Отчёты строятся как суммы `quantity` и `length_mm` по этой таблице.

Не записываются: резерв и снятие резерва, перемещение, удаление справочников и товаров, действия со штучными товарами. Журнал ведётся с 15.11.2026; более ранние действия в нём отсутствуют.

Для любой резки выполняется равенство: длина исходной заготовки = сумма длин результатов + `kerf_loss_mm`.

`stock_items` и `cut_operations` ссылаются друг на друга, поэтому внешний ключ `stock_items.cut_operation_id` создаётся в миграции отдельной командой после обеих таблиц, а в модели помечен `use_alter=True`.

## Миграции

Alembic, асинхронный режим. Адрес БД берётся из `DATABASE_URL` в `.env`, а значение `sqlalchemy.url` в `alembic.ini` — заглушка и не используется.

| Ревизия | Что делает |
|---|---|
| `7e28001292ae` | Начальная схема: `product_types`, `users`, `products`, `movements` |
| `509bd94a01e2` | `products.name` |
| `0e2250094d67` | `product_types.required_attributes` (JSONB) |
| `79c14ac440ea` | Таблица `locations` и `products.location_id` |
| `a1c3f5e7b902` | Поштучный учёт: `materials`, `orders`, `stock_items`, `cut_operations` |
| `b2d4a6c8e013` | `users.is_active` |
| `c3e5b7d9f124` | Ширина реза по умолчанию 0; у существующих материалов сброшена в 0 |
| `d4f6c8e0a235` | `stock_items.created_by_id`; кускам от прежних резок автор проставлен по автору резки |
| `e5a7d9f1b346` | Таблица `activity_log` |

Ревизия `b2d4a6c8e013` пока не добавлена в git. Ревизия `a1c3f5e7b902` написана вручную с именованными ограничениями; её `upgrade` и `downgrade` проверены на живой базе.

```bash
alembic upgrade head
```

```bash
alembic current
```

```bash
alembic revision --autogenerate -m "описание"
```

```bash
alembic downgrade -1
```

В ревизии `79c14ac440ea` внешний ключ создан без имени (`create_foreign_key(None, ...)`), и `downgrade` пытается удалить ограничение тоже с именем `None`. Откат этой ревизии упадёт, пока в неё не вписать реальное имя ограничения (PostgreSQL по умолчанию назовёт его `products_location_id_fkey`).
