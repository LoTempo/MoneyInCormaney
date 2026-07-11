# Семейный бюджет

Веб-приложение для совместного учёта семейных доходов и расходов.

Логотип сайта хранится в `app/static/images/logo.png`. Имя файла важно писать
строчными буквами: Linux-сервер различает `logo.png` и `Logo.png`.

## Возможности

- регистрация и вход с безопасным хэшированием паролей;
- полностью самостоятельный личный бюджет без обязательной семьи;
- отдельные семейные пространства и приглашения по коду;
- личные и семейные доходы, расходы и сбережения;
- ручной месячный лимит расходов с отображением отрицательного остатка;
- категории и подкатегории доходов и расходов;
- понятная аналитика по месяцам и годам с отдельной историей сбережений;
- сравнение личной и семейной статистики;
- защита чужих семейных операций от редактирования;
- выход из семьи, удаление участников и передача прав владельца;
- профиль с электронной почтой, телефоном и валютой;
- CSRF-защита форм и базовые HTTP-заголовки безопасности.

## Требования

- Python 3.12 или новее;
- PostgreSQL 15 или новее;
- виртуальное окружение Python.

## Локальная установка в Windows PowerShell

1. Установите зависимости:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Создайте в PostgreSQL базу `family_budget`.

3. Скопируйте настройки из `.env.example` в `.env` и замените:

   - `SECRET_KEY` на длинную случайную строку;
   - `DATABASE_HOST`, `DATABASE_PORT` и `DATABASE_NAME` на параметры базы;
   - `DATABASE_USER` и `DATABASE_PASSWORD` на данные пользователя PostgreSQL.

   Если задан `DATABASE_URL`, приложение использует его вместо отдельных параметров.

4. Создайте таблицы:

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app run init-db
   ```

   Для пустой базы команда создаёт структуру из `sql/schema.sql`. Проект пока не
   использует миграции, поэтому при будущих изменениях схемы действуйте отдельно.

5. Запустите приложение:

   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```

6. Откройте `http://127.0.0.1:5000`.

## Пустая база в Neon

1. В Neon откройте проект и нажмите **Connect**.
2. Выберите нужные branch, database и role.
3. Скопируйте две строки подключения:

   - pooled connection — адрес содержит `-pooler`;
   - direct connection — адрес не содержит `-pooler`.

4. Запишите их только в локальный `.env`:

   ```text
   DATABASE_URL="postgresql://USER:PASSWORD@ENDPOINT-pooler/DB?sslmode=require&channel_binding=require"
   DATABASE_ADMIN_URL="postgresql://USER:PASSWORD@ENDPOINT/DB?sslmode=require&channel_binding=require"
   ```

5. Один раз создайте пустые таблицы Neon:

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app run init-db
   ```

6. После сообщения `Database tables have been created.` приложение будет работать
   с Neon через `DATABASE_URL`. Локальные данные при этом никуда не копируются.

Для обычных запросов используется pooled-подключение. Для создания структуры
`init-db` предпочитает прямой `DATABASE_ADMIN_URL`. На хостинге добавьте
`DATABASE_URL`, `SECRET_KEY`, `APP_ENV=production` и `FLASK_DEBUG=false` в раздел
секретных переменных окружения; файл `.env` на сервер загружать в Git не нужно.

## Тесты

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Полная проверка с реальной PostgreSQL выполняется в транзакции и откатывает
созданные тестовые данные:

```powershell
$env:RUN_DATABASE_TESTS="1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:RUN_DATABASE_TESTS
```

## Публикация

Для рабочего сервера установите в `.env` значения:

```text
APP_ENV=production
FLASK_DEBUG=false
SERVER_HOST=0.0.0.0
```

При таком запуске `run.py` использует Waitress. Перед публикацией также нужны HTTPS,
обратный прокси, резервное копирование PostgreSQL и хранение секретов вне Git.

## Docker и Northflank

Проект собирается из корневого `Dockerfile` и слушает HTTP-порт `8080`.
Для Northflank создайте combined service из GitHub-репозитория, выберите сборку
через Dockerfile и ветку `main`. Включите CI для сборки новых commit и CD для
автоматического развёртывания успешной сборки.

Добавьте runtime secrets:

```text
APP_ENV=production
FLASK_DEBUG=false
PORT=8080
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=postgresql://pooled-neon-connection
```

Создайте публичный HTTP-порт `8080`, а для health check используйте `/health`.
`DATABASE_ADMIN_URL` рабочему контейнеру не требуется: таблицы Neon создаются
отдельно однократной командой `init-db`.

## Обновление существующей базы Neon

Проект не запускает SQL-миграции автоматически вместе с GitHub-деплоем. Если в
`sql/migrations` появился новый файл, сначала выполните его в Neon SQL Editor и
только после успешного выполнения отправляйте новый код в рабочую ветку.

Для переключателей личного и семейного бюджета используется миграция:

```text
sql/migrations/20260712_budget_visibility.sql
```

Она не удаляет данные, может быть выполнена повторно и оставляет оба бюджета
включёнными у всех существующих пользователей.
