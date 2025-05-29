#!/bin/sh

# Ожидаем, пока БД станет доступной
echo "Waiting for PostgreSQL..."

while ! nc -z db 5432; do
  sleep 1
done

echo "PostgreSQL started"

# Применяем миграции
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Собираем статику
python manage.py collectstatic --noinput

# Запускаем gunicorn
exec gunicorn foodgram.wsgi:application --bind 0.0.0.0:8000
