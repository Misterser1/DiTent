# Backend setup

Проект подключен к Django без переноса фронта на отдельный frontend-фреймворк. Текущая верстка перенесена в Django-шаблоны.

## Локальный запуск

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

## URL

- Сайт: `http://127.0.0.1:8000/`
- Кастомная админка проекта: `http://127.0.0.1:8000/ditent-cms/`
- Вход в админку: `http://127.0.0.1:8000/ditent-cms/login/`

## Доступ в админку

Для входа нужен пользователь Django с правами `is_staff=True`. Создать администратора можно командой:

```powershell
python manage.py createsuperuser
```

## Структура

- Страницы сайта: `templates/pages/`
- Общий каркас: `templates/base.html`
- Общие блоки: `templates/partials/`
- Статика: `assets/`
- Загружаемые файлы: `media/`
- Локальные настройки: `.env`
- Пример настроек: `.env.example`

## Безопасность и продакшен

- CSRF включен через стандартный `CsrfViewMiddleware`; страницы, которые работают с JS-запросами, выставляют CSRF-cookie через `ensure_csrf_cookie`.
- Все POST-запросы админки, корзины, конструктора, авторизации и оформления заказа проходят через Django CSRF.
- Кастомная админка доступна только авторизованным staff-пользователям.
- Кабинет и детали заказа фильтруются по `request.user`; пользователь не может открыть чужой заказ по номеру.
- Оформление заказа использует только серверную корзину из session, а не список товаров, присланный из браузера.
- Цены товаров, конструктора и доставки пересчитываются на backend.
- Загружаемые файлы ограничены по размеру, количеству, MIME-типу и расширению.
- Ошибки Django пишутся в `logs/django-errors.log`.

## Production checklist

Перед деплоем в `.env` нужно задать:

```env
DEBUG=False
SECRET_KEY=long-random-production-secret
ALLOWED_HOSTS=ditent.ru,www.ditent.ru
CSRF_TRUSTED_ORIGINS=https://ditent.ru,https://www.ditent.ru

SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

DB_ENGINE=postgresql
DB_NAME=ditent
DB_USER=ditent
DB_PASSWORD=strong-password
DB_HOST=127.0.0.1
DB_PORT=5432
```

Команды перед запуском:

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

## Production smoke после подключения ключей

После деплоя и настройки реальных SMTP, СДЭК и платежного провайдера нужно выполнить smoke-проверку внешних интеграций:

```powershell
python manage.py production_smoke --email-to=manager@company.ru --cdek-city-code=44 --alfa-order-id=<bank-order-id>
```

Что проверяет команда:

- `python manage.py check --deploy` и дополнительные DiTent production checks;
- отправку тестового письма через боевой SMTP;
- получение ПВЗ СДЭК по указанному `city_code`;
- чтение статуса существующего платежа в банке, если передан `--alfa-order-id`.

Платежка проверяется только по существующему `bank-order-id`, команда не создает новый платеж в боевом банке. Если платежный smoke нужно временно пропустить:

```powershell
python manage.py production_smoke --email-to=manager@company.ru --cdek-city-code=44 --skip-alfa
```

Для полной сдачи проекта smoke должен пройти без `--skip-*` флагов.

## СДЭК-трекинг заказов

Сайт не создает отправление в СДЭК автоматически: менеджер создает отправление в личном кабинете СДЭК и указывает в заказе `Трек-номер` или `UUID СДЭК`.

После этого статус можно обновить вручную в админке:

1. Открыть `/ditent-cms/` -> `Продажи` -> `Заказы`.
2. Открыть нужный заказ.
3. Заполнить `Трек-номер` СДЭК.
4. Нажать `Обновить СДЭК`.

Сайт сохранит последний статус СДЭК, дату проверки и обновит общий статус заказа:

- `DELIVERED` -> `Завершен`;
- промежуточные статусы СДЭК -> `Передан в доставку`, если заказ уже не ждет менеджера или оплату.

Для автоматической фоновой проверки можно поставить команду в cron/планировщик:

```powershell
python manage.py sync_cdek_tracking --limit=50
```

Для проверки одного заказа:

```powershell
python manage.py sync_cdek_tracking --order=DT-000123
```

На сервере нужно отдельно настроить отдачу `STATIC_ROOT` и `MEDIA_ROOT` через nginx или другой web-сервер. Django должен обслуживать медиа только в локальном `DEBUG=True` режиме.
