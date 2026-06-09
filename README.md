# Telegram-бот учета расходов по автомобилям

MVP на Django 5, async DRF (`adrf`) и aiogram 3. Бот ведет автомобили/заказы, расходы, категории, фото чеков через Telegram `file_id`, а Django admin дает веб-панель и CSV-выгрузки.

## Локальный запуск без Docker

Нужен Python 3.12. На системном Python 3.14 часть зависимостей aiogram собирается из исходников и может не установиться.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
createdb auto_bot_db
python manage.py migrate
python manage.py seed_categories
python manage.py createsuperuser
uvicorn car_expense_bot.asgi:application --host 127.0.0.1 --port 8000
```

В другом терминале:

```bash
source .venv/bin/activate
python bot.py
```

Админка: `http://127.0.0.1:8000/admin/`

## Доступы в бот

Локально можно оставить `BOT_ACCESS_CONTROL=False` в `.env`, тогда бот пускает всех и удобно тестировать сценарии. Для проверки ограничений поставьте `BOT_ACCESS_CONTROL=True`, зайдите в Django admin и добавьте пользователя в `Пользователи Telegram`: `telegram_id`, роль `Сотрудник` или `Руководитель`, `is_active=True`.

Если пользователь не добавлен или выключен, бот ответит, что доступа нет, и покажет его Telegram ID для администратора.

## Docker

На сервере PostgreSQL запускается отдельным контейнером `postgres` внутри `docker-compose.yml`. Порт `5432` наружу не пробрасывается; `web` и `bot` подключаются к базе по Docker DNS имени `postgres`.

```bash
cp .env.docker.example .env
# заполните BOT_TOKEN, SECRET_KEY, INTERNAL_API_KEY, POSTGRES_PASSWORD и SERVER_IP
docker compose build
```

Запуск по отдельности:

```bash
# база поднимется автоматически как зависимость web
docker compose up -d web

# после создания суперпользователя и проверки админки запускаем bot
docker compose up -d bot
```

Остановить только бота, не трогая Django и PostgreSQL:

```bash
docker compose stop bot
```

Остановить только Django:

```bash
docker compose stop web
```

Логи отдельно:

```bash
docker compose logs -f web
docker compose logs -f bot
```

Для сервера без домена админка будет доступна по IP:

```text
http://SERVER_IP:8000/admin/
```

Создание администратора внутри контейнера:

```bash
docker compose exec web python manage.py createsuperuser
```

## Основные API

- `GET/POST /api/cars/`
- `GET/PATCH /api/cars/<id>/`
- `GET/POST /api/expenses/`
- `GET /api/categories/`
- `GET /api/reports/summary/`

Если `INTERNAL_API_KEY` заполнен, передавайте заголовок `X-API-Key`.
