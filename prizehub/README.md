# PrizeHub — Telegram-бот для розыгрышей призов

## Быстрый старт

### 1. Подготовка

```bash
cp .env.example .env
```

Заполните `.env`:
- `BOT_TOKEN` — токен основного бота (получить у @BotFather)
- `CHECKER_BOT_TOKEN` — токен @Invest_reinvest_bot (или любого второго бота)
- `ADMIN_IDS` — ваш Telegram ID (можно узнать через @userinfobot)
- Пароли для PostgreSQL

### 2. Запуск

```bash
docker compose up -d --build
```

### 3. Создание первого сезона

1. Откройте бота в Telegram
2. Напишите `/admin`
3. Нажмите **Сезоны** → **Создать сезон**
4. Заполните: название, приз, фото, @канал спонсора
5. Добавьте `@Invest_reinvest_bot` администратором в канал спонсора
6. Нажмите **Активировать сезон**

## Структура проекта

```
prizehub/
├── bot/
│   ├── main.py              # Точка входа
│   ├── config.py            # Настройки из .env
│   ├── constants.py         # Константы (диапазоны билетов и т.д.)
│   ├── database/
│   │   ├── models.py        # SQLAlchemy модели
│   │   ├── engine.py        # Подключение к БД
│   │   └── repositories/    # Слой доступа к данным
│   ├── handlers/            # Telegram-хендлеры
│   │   └── admin/           # Панель администратора
│   ├── keyboards/           # Инлайн и Reply-клавиатуры
│   ├── middlewares/         # БД-сессия, антиспам
│   ├── services/            # Бизнес-логика
│   ├── states/              # FSM состояния
│   └── scheduler/           # Планировщик (APScheduler)
├── migrations/              # Alembic миграции
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начало работы / онбординг |
| `/admin` | Панель администратора (только для ADMIN_IDS) |

## Управление через /admin

- **Статистика** — DAU, новые пользователи, конверсия
- **Сезоны** — создание и активация сезонов
- **Розыгрыши** — просмотр расписания мини-розыгрышей
- **Победители** — публикация победителей с фото
- **Пуши** — массовая рассылка

## Технологии

- Python 3.12 + Aiogram 3.x
- PostgreSQL + SQLAlchemy (asyncio)
- Redis (FSM хранилище)
- APScheduler (планировщик задач)
- Docker + Docker Compose

## Переменные окружения

| Переменная | Описание |
|-----------|----------|
| `BOT_TOKEN` | Токен основного бота |
| `CHECKER_BOT_TOKEN` | Токен проверочного бота |
| `ADMIN_IDS` | ID администраторов через запятую |
| `POSTGRES_*` | Данные PostgreSQL |
| `REDIS_*` | Данные Redis |
| `TIMEZONE` | Часовой пояс (по умолчанию Europe/Moscow) |
