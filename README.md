### Локальный запуск проекта:

**_Склонировать репозиторий к себе_**
```
git clone https://github.com/svvqt/foodgram-st.git
```

**_В корневой папке файл myenv.env переименовать в .env и заполнить данными:_**
```
POSTGRES_DB=foodgram_db
POSTGRES_USER=foodgram_user
POSTGRES_PASSWORD=foodgram_pass

DB_ENGINE=django.db.backends.postgresql
DB_NAME=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432
```

**_Перейти в папку infra и запустить docker-compose._**
```
docker-compose up --build
```
в нем соберется проект, выполнятся миграции и соберется статика, затем в этой же папке выполняем команду

```
docker-compose exec backend python manage.py loaddata ingredients_converted
```

**_После проект будет доступен по адресу: http://localhost/_**, а backend проекта **_http://localhost:8000/api_**

**_Затем нужно создать суперпользователя._**
```
docker-compose exec backend python manage.py createsuperuser
```