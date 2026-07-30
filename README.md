# Моя почта

Полноценный адаптивный почтовый клиент: FastAPI REST API, PostgreSQL, асинхронные IMAP/SMTP, React и Material UI. Пароли аккаунтов шифруются Fernet перед сохранением. Синхронизация запускается APScheduler каждые две минуты и использует уникальную комбинацию аккаунта, папки и IMAP UID для защиты от дублей.

## Быстрый запуск

1. Скопируйте и настройте окружение: `cp .env.example .env`. Обязательно замените `POSTGRES_PASSWORD` и `SECRET_KEY`.
2. Запустите сервис: `docker compose up -d --build`.
3. Откройте `http://SERVER:8080/mail/` (путь определяется `BASE_PATH`).
4. В «Настройки IMAP» добавьте аккаунт и нажмите «Проверить подключение».

> При изменении `SECRET_KEY` ранее сохранённые пароли невозможно расшифровать. Храните ключ в менеджере секретов и не публикуйте production-файл `.env`.

## Компоненты

- **db** — PostgreSQL 17 с постоянным volume и healthcheck.
- **backend** — Python 3.13, FastAPI, SQLAlchemy Async, Alembic, aioimaplib, aiosmtplib и APScheduler.
- **frontend** — React 19, TypeScript, Vite и Material UI; встроенный nginx обслуживает SPA и маршрутизирует `${BASE_PATH}/api/` в backend.

Отдельный контейнер reverse proxy не используется: nginx из frontend-контейнера уже является единой точкой входа на порту `8080`. На VPS внешний системный nginx может проксировать HTTPS-трафик на этот порт. Внутренний nginx использует Docker DNS `127.0.0.11` и разрешает имя `backend` во время запроса, поэтому перезапуск backend не требует перезапуска frontend.

API доступен внутри proxy по `${BASE_PATH}/api`; OpenAPI backend — `/docs` при прямом доступе к контейнеру. Ограничение загрузки — 50 МБ.

## Разработка

```bash
cd frontend && npm install && npm run dev
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```

Для локального backend задайте `DATABASE_URL` на PostgreSQL. SQLite намеренно не поддерживается. Миграции применяются автоматически при старте контейнера; вручную: `alembic upgrade head`.

## Безопасность и эксплуатация

- В production ограничьте CORS доверенными origin, включите HTTPS на внешнем reverse proxy и не публикуйте порт PostgreSQL.
- Делайте резервные копии PostgreSQL volume и храните `SECRET_KEY` отдельно.
- HTML писем отображается в изолированном приложении, но перед публичным многопользовательским запуском рекомендуется добавить строгую HTML-санитизацию и аутентификацию.
- Архитектура разделяет модели, Pydantic-схемы, репозитории и сервис работы с почтой. Это оставляет точки расширения для OAuth-провайдеров, правил, подписей, шаблонов, цепочек и адресной книги.
