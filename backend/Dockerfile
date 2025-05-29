FROM python:3.8-slim

RUN apt-get update && apt-get install -y netcat-openbsd && apt-get clean

RUN mkdir /app

COPY requirements.txt /app

RUN python -m pip install --upgrade pip && pip3 install -r app/requirements.txt --no-cache-dir

COPY . /app

WORKDIR /app

# Копируем entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Используем его как точку входа
ENTRYPOINT ["/app/entrypoint.sh"]
