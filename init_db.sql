-- Запускать от имени суперпользователя postgres:
-- psql -U postgres -f init_db.sql

-- 1. Создаём пользователя для приложения (ограниченные права)
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'jewelry_app') THEN
      CREATE ROLE jewelry_app LOGIN PASSWORD 'jewelry_pass';
   END IF;
END $$;

-- 2. Создаём базу данных
SELECT 'CREATE DATABASE jewelry_db OWNER jewelry_app'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'jewelry_db')\gexec

-- 3. Подключаемся к новой базе и выдаём права
\c jewelry_db

GRANT CONNECT ON DATABASE jewelry_db TO jewelry_app;
GRANT USAGE ON SCHEMA public TO jewelry_app;

-- Таблицы создаст сам бэкенд (init_db в app.py), но права на последовательности и таблицы выдадим заранее:
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO jewelry_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO jewelry_app;

-- 4. Пароль пользователя postgres (если нужно сбросить):
-- ALTER USER postgres WITH PASSWORD 'ваш_новый_пароль';
