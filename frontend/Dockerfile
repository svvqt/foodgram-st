FROM node:21.7.1-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . ./
RUN npm run build

# Сохраняем артефакт сборки
RUN mkdir /result_build && cp -r build/* /result_build/
