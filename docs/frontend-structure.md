# Frontend Structure

Проект пока остается статической HTML-версткой. Header и footer физически продублированы в каждой странице, но должны считаться общими блоками для будущего переноса в backend-шаблоны.

## Canonical Routes

- `index.html` - главная
- `about.html` - о фабрике
- `catalog.html` - каталог готовых изделий
- `delivery.html` - доставка и оплата
- `review.html` - галерея и отзывы
- `contacts.html` - контакты
- `constructor.html` - конструктор чехла
- `form.html` - карточка/форма заказа готового изделия из каталога
- `card.html` - корзина
- `cabinet.html` - личный кабинет
- `legal.html` - юридическая информация
- `privacy.html` - политика конфиденциальности

## Shared Blocks

Header:
- логотип ведет на `index.html`
- основное меню ведет на страницы из `Canonical Routes`
- иконка корзины ведет на `card.html`
- иконка профиля ведет на `cabinet.html`
- CTA `Создать чехол` ведет на `constructor.html`

Footer:
- логотип ведет на `index.html`
- контакты используют `tel:`, `mailto:` и `contacts.html`
- социальные ссылки сейчас заполнены техническими placeholder-URL
- юридические ссылки ведут на `legal.html` и `privacy.html`
