#!/bin/sh
set -e

python manage.py migrate
python manage.py seed_categories
exec uvicorn car_expense_bot.asgi:application --host 0.0.0.0 --port 8000
