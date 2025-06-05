### Foodgram - «Продуктовый помощник»
Foodgram — это онлайн-сервис для публикации рецептов. Пользователи могут создавать свои рецепты, подписываться на других авторов, добавлять рецепты в избранное и в список покупок, а также скачивать сводный список ингредиентов.

### Список технологий

**Backend:**
- Python 3.9+
- Django 3.2+ (веб-фреймворк)
- Django REST Framework (DRF) (API)
- PostgreSQL (база данных)
- Gunicorn (WSGI-сервер)
- Nginx (веб-сервер и прокси)

**Frontend:**
- React.js (интерфейс)
- JavaScript (ES6+)
- HTML5 / CSS3

**Инфраструктура:**
- Docker (контейнеризация)
- Docker Compose (оркестрация)
- GitHub (хостинг кода)

### Локальный запуск проекта:

**_Склонировать репозиторий к себе_**
```
git clone https://github.com/svvqt/foodgram-st.git
```

**_В корневой папке файл myenv.env переименовать в .env и заполнить данными:_**
```
SECRET_KEY = '=0n9n=!mk()uf7e-rble)3*&8sj79b309sl3%(__7j*cnp$e)q'
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,web,51.250.98.54,*

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

**_Затем нужно создать суперпользователя._**
```
docker-compose exec backend python manage.py createsuperuser
```

**_После проект будет доступен по адресу: http://localhost/_**, а backend проекта **_http://localhost:8000/api_**, админка по адресу **_http://localhost/admin_**

### Пример API-запросов
**_Регистрация пользователя_**

```
POST /api/users/
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "user123",
  "first_name": "Иван",
  "last_name": "Иванов",
  "password": "securepassword123"
}
```

### Автор
**_Витковский К.Е._**