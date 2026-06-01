# Frontend structure

Фронт больше не лежит рабочими HTML-файлами в корне репозитория. Страницы перенесены в Django-шаблоны, но визуальная верстка, CSS и JS сохранены без переписывания.

## Templates

- `templates/base.html` - общий HTML-каркас: `head`, блоки стилей, header, content, footer, скрипты.
- `templates/partials/header.html` - основной публичный header.
- `templates/partials/footer.html` - основной публичный footer.
- `templates/partials/header_home.html` и `footer_home.html` - вариант для главной страницы.
- `templates/partials/header_constructor.html` - вариант для конструктора и карточки товара.
- `templates/partials/header_drawing.html` и `footer_drawing.html` - вариант для заказа по чертежу.
- `templates/pages/*.html` - страницы сайта.

## Canonical routes

- `/` и `/index.html` - главная
- `/about.html` - о фабрике
- `/catalog.html` - каталог готовых изделий
- `/category.html` - страница раздела/категории
- `/delivery.html` - доставка и оплата
- `/review.html` - галерея и отзывы
- `/contacts.html` - контакты
- `/constructor.html` - конструктор чехла
- `/drawing-order.html` - заказ по чертежу
- `/form.html` - карточка готового товара
- `/card.html` - корзина
- `/cabinet.html` - личный кабинет
- `/ditent-cms/` - кастомная админка
- `/legal.html` - юридическая информация
- `/privacy.html` - политика конфиденциальности

## Static files

CSS, JS и изображения остаются в `assets/` и подключаются по прежним URL `/assets/...`.
