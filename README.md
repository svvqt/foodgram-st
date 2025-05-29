### Локальный запуск проекта:

**_Склонировать репозиторий к себе_**
```
git@github.com:svvqt/foodgram-st.git
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
в нем соберется проект, выполнятся миграции и соберется статика

**_Затем нужно создать суперпользователя._**
```
docker-compose exec backend python manage.py createsuperuser
```
Вводим любые удобные данные и переходим в http://localhost/admin, логинимся, а затем переходим http://localhost/admin/recipes/ingredient/upload-json/, нажимаем на кнопку 'выберите файл', находим в директории проекта папку data, выбираем ingredients.json, затем нажимаем загрузить json. После нескольких секунд данные из json будут загружены в бд. Выходим из админки

**_После проект будет доступен по адресу: http://localhost/_**
