const BLANK_IMAGE_SRC = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';

if ('scrollRestoration' in window.history) {
    window.history.scrollRestoration = 'manual';
}

const entityLabels = {
    categories: ['Новая категория', 'Редактирование категории', 'Создать категорию'],
    products: ['Новый товар', 'Редактирование товара', 'Создать товар'],
    fabrics: ['Новая ткань', 'Редактирование ткани', 'Создать ткань'],
    colors: ['Новый цвет', 'Редактирование цвета', 'Создать цвет'],
    fasteners: ['Новое крепление', 'Редактирование крепления', 'Создать крепление'],
    formulas: ['Новая формула', 'Редактирование формулы', 'Создать формулу'],
    orders: ['Карточка заказа', 'Карточка заказа', 'Обновить заказ'],
    'drawing-orders': ['Заявка по чертежу', 'Заявка по чертежу', 'Обновить заявку'],
    'constructor-images': ['Новое изображение конструктора', 'Редактирование изображения конструктора', 'Создать изображение'],
    reviews: ['Новый отзыв', 'Редактирование отзыва', 'Создать отзыв'],
    'site-settings': ['Настройки сайта', 'Настройки сайта', 'Сохранить настройки'],
};

function apiBase() {
    return document.querySelector('.admin-page')?.dataset.adminApiBase || '/custom-admin/api/';
}

function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

function sectionEntity(section) {
    return section.dataset.entity || section.id;
}

function formFields(form) {
    return [...form.querySelectorAll('input[name], textarea[name], select[name]')];
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function optionLabel(option) {
    return option?.textContent.trim() || 'Не выбрано';
}

function syncCustomSelect(select) {
    const custom = select?._customSelect;
    const buttonText = custom?.querySelector('.admin-custom-select__value');
    const selectedText = optionLabel(select?.selectedOptions[0]);

    if (!select || !custom || !buttonText) {
        return;
    }

    buttonText.textContent = selectedText;
    custom.querySelector('.admin-custom-select__button')?.setAttribute('title', selectedText);
    custom.querySelectorAll('[data-select-option]').forEach((button) => {
        button.classList.toggle('is-selected', button.dataset.value === select.value);
    });
}

function positionCustomSelectMenu(custom) {
    const menu = custom?._menu;
    const toggle = custom?.querySelector('.admin-custom-select__button');

    if (!menu || !toggle || !custom.classList.contains('is-open')) {
        return;
    }

    const rect = toggle.getBoundingClientRect();
    const viewportGap = 12;
    const menuWidth = Math.max(rect.width, 180);
    const availableBelow = window.innerHeight - rect.bottom - viewportGap;
    const availableAbove = rect.top - viewportGap;
    const openUp = availableBelow < 180 && availableAbove > availableBelow;
    const maxHeight = Math.max(160, Math.min(320, openUp ? availableAbove - 6 : availableBelow - 6));
    const left = Math.min(Math.max(viewportGap, rect.left), window.innerWidth - menuWidth - viewportGap);
    const top = openUp ? rect.top - 6 : rect.bottom + 6;

    menu.style.width = `${menuWidth}px`;
    menu.style.left = `${left}px`;
    menu.style.top = openUp ? 'auto' : `${top}px`;
    menu.style.bottom = openUp ? `${window.innerHeight - top}px` : 'auto';
    menu.style.maxHeight = `${maxHeight}px`;
}

function closeCustomSelects(except = null) {
    document.querySelectorAll('.admin-custom-select.is-open').forEach((custom) => {
        if (custom !== except) {
            custom.classList.remove('is-open');
            custom.querySelector('.admin-custom-select__button')?.setAttribute('aria-expanded', 'false');
            custom._menu?.classList.remove('is-open');
        }
    });
}

function setAdminScrollTop(value) {
    const main = document.querySelector('.admin-main');

    if (main) {
        main.scrollTop = value;
    }

    window.scrollTo(0, value);
}

function clearAdminHash() {
    if (window.location.hash) {
        window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
    }
}

function restoreAdminScroll() {
    const shouldRestore = sessionStorage.getItem('ditentAdminRestoreScroll') === '1';
    const value = shouldRestore ? Number(sessionStorage.getItem('ditentAdminScrollTop') || 0) : 0;

    sessionStorage.removeItem('ditentAdminRestoreScroll');
    sessionStorage.removeItem('ditentAdminScrollTop');

    const applyScroll = () => {
        clearAdminHash();
        setAdminScrollTop(value);
    };

    applyScroll();
    requestAnimationFrame(applyScroll);
    window.addEventListener('load', () => {
        applyScroll();
        setTimeout(applyScroll, 0);
        setTimeout(applyScroll, 80);
    }, { once: true });
}

function rememberAdminScroll() {
    const main = document.querySelector('.admin-main');
    const value = main ? main.scrollTop : window.scrollY;

    sessionStorage.setItem('ditentAdminScrollTop', String(value));
    sessionStorage.setItem('ditentAdminRestoreScroll', '1');
}

function updateCategoryPosition(form, force = false) {
    const parent = form?.elements.namedItem('parent');
    const position = form?.elements.namedItem('position');
    const nextPosition = parent?.selectedOptions[0]?.dataset.nextPosition;

    if (!parent || !position || !nextPosition) {
        return;
    }

    if (force || form.dataset.mode === 'create') {
        position.value = nextPosition;
    }
}

function initAdminNavigation() {
    document.querySelectorAll('.admin-nav a[href^="#"]').forEach((link) => {
        link.addEventListener('click', (event) => {
            const target = document.querySelector(link.getAttribute('href'));

            if (!target) {
                return;
            }

            event.preventDefault();
            clearAdminHash();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });
}

function initCustomSelects(scope = document) {
    scope.querySelectorAll('.admin-form select, .admin-table-filter select').forEach((select) => {
        if (select._customSelect || select.multiple) {
            return;
        }

        select.classList.add('admin-select-native');

        const custom = document.createElement('div');
        custom.className = 'admin-custom-select';
        custom.innerHTML = `
            <button class="admin-custom-select__button" type="button" aria-haspopup="listbox" aria-expanded="false">
                <span class="admin-custom-select__value"></span>
                <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M4.5 6.5L8 10l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
            <div class="admin-custom-select__menu" role="listbox"></div>
        `;

        const menu = custom.querySelector('.admin-custom-select__menu');
        document.body.append(menu);
        custom._menu = menu;
        [...select.options].forEach((option) => {
            const label = optionLabel(option);
            const button = document.createElement('button');
            button.type = 'button';
            button.dataset.value = option.value;
            button.dataset.selectOption = '';
            button.textContent = label;
            button.title = label;
            button.setAttribute('role', 'option');
            button.disabled = option.disabled;
            menu.append(button);
        });

        const toggle = custom.querySelector('.admin-custom-select__button');
        toggle.addEventListener('click', () => {
            const isOpen = custom.classList.contains('is-open');
            closeCustomSelects(custom);
            custom.classList.toggle('is-open', !isOpen);
            menu.classList.toggle('is-open', !isOpen);
            toggle.setAttribute('aria-expanded', String(!isOpen));
            positionCustomSelectMenu(custom);
        });

        menu.addEventListener('click', (event) => {
            const optionButton = event.target.closest('[data-select-option]');

            if (!optionButton || optionButton.disabled) {
                return;
            }

            select.value = optionButton.dataset.value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
            closeCustomSelects();
        });

        select.addEventListener('change', () => syncCustomSelect(select));
        select.after(custom);
        select._customSelect = custom;
        syncCustomSelect(select);
    });
}

function syncCustomSelects(scope = document) {
    scope.querySelectorAll('.admin-form select, .admin-table-filter select').forEach(syncCustomSelect);
}

function normalizeFilterText(value) {
    return String(value || '').trim().toLowerCase();
}

function initTableFilter({ filterSelector, searchSelector, groupSelector, paginationSelector, rowSelector, haystack, matchesGroup }) {
    const filter = document.querySelector(filterSelector);
    const search = filter?.querySelector(searchSelector);
    const group = filter?.querySelector(groupSelector);
    const pagination = document.querySelector(paginationSelector);
    const rows = [...document.querySelectorAll(rowSelector)];
    const perPage = 5;
    let currentPage = 1;

    if (!filter || !search || !group || rows.length === 0) {
        return;
    }

    const renderPagination = (totalPages, totalRows) => {
        if (!pagination) {
            return;
        }

        pagination.innerHTML = '';
        pagination.hidden = totalRows === 0;

        if (totalRows === 0) {
            return;
        }

        const createButton = (label, page, options = {}) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = label;
            button.disabled = Boolean(options.disabled);
            button.classList.toggle('is-active', Boolean(options.active));
            button.addEventListener('click', () => {
                if (button.disabled || currentPage === page) {
                    return;
                }

                currentPage = page;
                applyFilter();
            });
            return button;
        };

        pagination.append(createButton('‹', Math.max(1, currentPage - 1), { disabled: currentPage === 1 }));

        for (let page = 1; page <= totalPages; page += 1) {
            pagination.append(createButton(String(page), page, { active: page === currentPage }));
        }

        pagination.append(createButton('›', Math.min(totalPages, currentPage + 1), { disabled: currentPage === totalPages }));
    };

    const applyFilter = () => {
        const query = normalizeFilterText(search.value);
        const groupId = group.value;
        const matchedRows = [];

        rows.forEach((row) => {
            const searchableText = haystack(row);
            const matchesQuery = !query || searchableText.includes(query);
            const groupMatched = !groupId || matchesGroup(row, groupId);

            const isMatched = matchesQuery && groupMatched;
            row.hidden = true;

            if (isMatched) {
                matchedRows.push(row);
            }
        });

        const totalPages = Math.max(1, Math.ceil(matchedRows.length / perPage));
        currentPage = Math.min(currentPage, totalPages);

        matchedRows.forEach((row, index) => {
            const rowPage = Math.floor(index / perPage) + 1;
            row.hidden = rowPage !== currentPage;
        });

        renderPagination(totalPages, matchedRows.length);
    };

    search.addEventListener('input', () => {
        currentPage = 1;
        applyFilter();
    });
    group.addEventListener('change', () => {
        currentPage = 1;
        applyFilter();
    });
    applyFilter();
}

function initCategoryFilters() {
    initTableFilter({
        filterSelector: '[data-category-filter]',
        searchSelector: '[data-category-search]',
        groupSelector: '[data-category-group]',
        paginationSelector: '[data-category-pagination]',
        rowSelector: '[data-category-row]',
        haystack: row => [
            row.dataset.categoryTitle,
            row.dataset.categorySlug,
            row.dataset.categoryParent,
        ].map(normalizeFilterText).join(' '),
        matchesGroup: (row, groupId) => row.dataset.categoryGroup === groupId,
    });
}

function initProductFilters() {
    initTableFilter({
        filterSelector: '[data-product-filter]',
        searchSelector: '[data-table-search]',
        groupSelector: '[data-table-group]',
        paginationSelector: '[data-product-pagination]',
        rowSelector: '[data-product-row]',
        haystack: row => [
            row.dataset.productTitle,
            row.dataset.productSku,
            row.dataset.productCategory,
        ].map(normalizeFilterText).join(' '),
        matchesGroup: (row, groupId) => row.dataset.productCategoryId === groupId,
    });
}

function initSimpleAdminTableFilter(name) {
    initTableFilter({
        filterSelector: `[data-${name}-filter]`,
        searchSelector: '[data-table-search]',
        groupSelector: '[data-table-group]',
        paginationSelector: `[data-${name}-pagination]`,
        rowSelector: `[data-${name}-row]`,
        haystack: row => normalizeFilterText(row.dataset.search),
        matchesGroup: (row, groupId) => row.dataset.group === groupId,
    });
}

function initSecondaryTableFilters() {
    [
        'fabric',
        'color',
        'fastener',
        'formula',
        'order',
        'drawing-order',
        'constructor-image',
        'review',
    ].forEach(initSimpleAdminTableFilter);
}

function entityUrl(entity, id = '') {
    return `${apiBase()}${entity}/${id ? `${id}/` : ''}`;
}

function createSlug(value) {
    const map = {
        а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z',
        и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r',
        с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'c', ч: 'ch', ш: 'sh',
        щ: 'sch', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
    };

    return value
        .toLowerCase()
        .split('')
        .map((letter) => map[letter] ?? letter)
        .join('')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function getForm(section) {
    return section.querySelector('[data-admin-form]');
}

function setMode(section, mode, id = '') {
    const form = getForm(section);
    const entity = sectionEntity(section);
    const [newTitle, editTitle, createButton] = entityLabels[entity] || ['Новая запись', 'Редактирование записи', 'Создать'];
    const title = form?.querySelector('h3');
    const submit = form?.querySelector('[type="submit"]');

    if (!form) {
        return;
    }

    form.dataset.mode = mode;
    form.dataset.id = id;
    if (title) {
        title.textContent = mode === 'edit' ? editTitle : newTitle;
    }
    if (submit) {
        submit.textContent = mode === 'edit' ? 'Сохранить изменения' : createButton;
    }
}

function resetUpload(upload) {
    const image = upload?.querySelector('img');
    const input = upload?.querySelector('input[type="file"]');

    if (input) {
        input.value = '';
    }
    if (image) {
        image.src = image.dataset.defaultSrc || image.getAttribute('src') || BLANK_IMAGE_SRC;
    }
    upload?.querySelector('.admin-upload__dropzone')?.classList.add('is-empty');
}

function resetForm(section) {
    const form = getForm(section);

    if (!form) {
        return;
    }

    form.reset();
    formFields(form).forEach((field) => {
        if (field.type === 'checkbox') {
            field.checked = false;
            return;
        }
        if (field.type !== 'hidden' && field.type !== 'file' && field.tagName !== 'SELECT') {
            field.value = '';
        }
    });
    form.querySelectorAll('.admin-upload').forEach(resetUpload);
    updateGalleryPreview(form.querySelector('[data-gallery-upload]'), []);
    renderOrderItems(form.querySelector('[data-order-items]'), '');
    renderDrawingFiles(form.querySelector('[data-drawing-files]'), []);
    syncCustomSelects(form);
    setMode(section, 'create');
    if (sectionEntity(section) === 'categories') {
        updateCategoryPosition(form, true);
    }
}

function fillForm(section, item) {
    const form = getForm(section);

    if (!form) {
        return;
    }

    formFields(form).forEach((field) => {
        if (field.type === 'file') {
            field.value = '';
            return;
        }

        const value = item[field.name];

        if (field.type === 'checkbox') {
            field.checked = Boolean(value);
            return;
        }

        if (value === null || value === undefined) {
            field.value = '';
            return;
        }

        if (typeof value === 'object') {
            field.value = JSON.stringify(value);
            return;
        }

        field.value = value;
    });

    updateImagePreview(form.querySelector('[data-preview-field="image"]'), item.image);
    updateImagePreview(form.querySelector('[data-preview-field="main_image"]'), item.main_image);
    updateImagePreview(form.querySelector('[data-preview-field="map_image"]'), item.map_image);
    updateGalleryPreview(form.querySelector('[data-gallery-upload]'), item.gallery_items || item.gallery_images || []);
    renderOrderItems(form.querySelector('[data-order-items]'), item.items || item.items_summary || '');
    renderDrawingFiles(form.querySelector('[data-drawing-files]'), item.files || []);
    syncCustomSelects(form);
}

function updateImagePreview(image, src) {
    const dropzone = image?.closest('.admin-upload__dropzone');

    if (!image || !dropzone) {
        return;
    }

    if (src) {
        image.src = src;
        dropzone.classList.remove('is-empty');
        return;
    }

    image.src = image.dataset.defaultSrc || BLANK_IMAGE_SRC;
    dropzone.classList.add('is-empty');
}

function renderOrderItems(container, value) {
    if (!container) {
        return;
    }

    if (Array.isArray(value)) {
        container.innerHTML = value.length
            ? value.map((item) => {
                const details = Array.isArray(item.details) ? item.details : [];
                const detailsHtml = details.length
                    ? `<dl>${details.map((detail) => `<div><dt>${escapeHtml(detail.label)}</dt><dd>${escapeHtml(detail.value)}</dd></div>`).join('')}</dl>`
                    : '<span>Параметры не указаны.</span>';
                const sku = item.sku ? `<small>Артикул: ${escapeHtml(item.sku)}</small>` : '';

                return `
                    <div class="admin-order-item">
                        <b>${escapeHtml(item.title)}</b>
                        ${sku}
                        ${detailsHtml}
                        <strong>${escapeHtml(item.quantity)} шт. · ${escapeHtml(item.total_price)} ₽</strong>
                    </div>
                `;
            }).join('')
            : '<div><span>Состав заказа появится после выбора строки.</span></div>';
        return;
    }

    const items = String(value || '')
        .split('||')
        .map((item) => item.split('|').map((part) => part.trim()))
        .filter(([title]) => title);

    container.innerHTML = items.length
        ? items.map(([title, description = '', price = '']) => `<div class="admin-order-item"><b>${escapeHtml(title)}</b><span>${escapeHtml(description)}</span><strong>${escapeHtml(price)}</strong></div>`).join('')
        : '<div><span>Состав заказа появится после выбора строки.</span></div>';
}

function renderDrawingFiles(container, files) {
    if (!container) {
        return;
    }

    container.innerHTML = files.length
        ? files.map((file) => `<div><b>${file.name}</b><a href="${file.url}" target="_blank" rel="noopener">Открыть файл</a></div>`).join('')
        : '<div><span>Файлы появятся после выбора заявки.</span></div>';
}

const adminTourSteps = [
    {
        selector: '.admin-topbar',
        title: 'Главный экран',
        text: 'Здесь находится панель управления сайтом. Слева навигация по разделам, ниже короткая сводка по каталогу и новым заявкам.',
    },
    {
        selector: '.admin-nav',
        title: 'Навигация',
        text: 'Через меню можно быстро перейти к товарам, тканям, заказам, заявкам по чертежам, отзывам и настройкам сайта.',
    },
    {
        selector: '.admin-summary',
        title: 'Сводка',
        text: 'Эти карточки помогают быстро понять объем данных: категории, товары, материалы и новые заявки, которые требуют внимания.',
    },
    {
        selector: '#categories',
        title: 'Категории',
        text: 'В этом разделе создаются и редактируются разделы каталога. Категории могут быть верхнего уровня или вложенными.',
    },
    {
        selector: '#products',
        title: 'Товары',
        text: 'Здесь заполняются готовые изделия: название, артикул, цена, размеры, остаток, изображения и статус публикации.',
    },
    {
        selector: '#fabrics',
        title: 'Ткани',
        text: 'Ткани используются в конструкторе и карточках товаров. Важно поддерживать актуальные цены и характеристики материалов.',
    },
    {
        selector: '#colors',
        title: 'Цвета',
        text: 'Цвета привязаны к тканям. Клиент видит их при выборе материала, поэтому лучше загружать понятные образцы.',
    },
    {
        selector: '#fasteners',
        title: 'Крепления',
        text: 'Крепления и фурнитура добавляются в конструктор. Здесь можно менять цену, совместимость и активность варианта.',
    },
    {
        selector: '#formulas',
        title: 'Формулы',
        text: 'Формулы отвечают за расчет стоимости нестандартных форм. Менять их нужно аккуратно, потому что они влияют на калькулятор.',
    },
    {
        selector: '#orders',
        title: 'Заказы',
        text: 'Основной рабочий раздел менеджера. Здесь проверяются заказы, меняются статусы, подтверждается оплата и ведется доставка.',
    },
    {
        selector: '#orders [data-sync-cdek]',
        title: 'Трекинг СДЭК',
        text: 'После создания отправления в личном кабинете СДЭК менеджер указывает трек-номер и нажимает эту кнопку, чтобы подтянуть статус доставки.',
    },
    {
        selector: '#drawing-orders',
        title: 'Заявки по чертежу',
        text: 'Сюда попадают заявки с файлами клиента. Менеджер проверяет чертеж, уточняет детали и переводит заявку в нужный статус.',
    },
    {
        selector: '#constructor-images',
        title: 'Изображения конструктора',
        text: 'Этот раздел управляет визуальными подсказками конструктора: формами, схемами и изображениями для клиента.',
    },
    {
        selector: '#reviews',
        title: 'Отзывы',
        text: 'Отзывы и галерея выводятся на сайте. Здесь можно добавлять реальные кейсы, подписи, город и статус публикации.',
    },
    {
        selector: '#site-settings',
        title: 'Настройки сайта',
        text: 'Здесь хранятся контакты, реквизиты, ссылки на соцсети, карта и email менеджеров для уведомлений.',
    },
];

let adminTourState = {
    index: 0,
    target: null,
    root: null,
};

function createAdminTour() {
    const root = document.createElement('div');
    root.className = 'admin-tour';
    root.hidden = true;
    root.innerHTML = `
        <div class="admin-tour__overlay" data-tour-close></div>
        <div class="admin-tour__spotlight" aria-hidden="true"></div>
        <section class="admin-tour__card" role="dialog" aria-modal="true" aria-live="polite" aria-labelledby="admin-tour-title">
            <button class="admin-tour__close" type="button" aria-label="Закрыть обучение" data-tour-close>&times;</button>
            <span class="admin-tour__kicker" data-tour-counter></span>
            <h3 id="admin-tour-title" data-tour-title></h3>
            <p data-tour-text></p>
            <div class="admin-tour__actions">
                <button type="button" data-tour-prev>Назад</button>
                <button type="button" data-tour-next>Далее</button>
            </div>
        </section>
    `;
    document.body.append(root);
    return root;
}

function adminTourElements() {
    const root = adminTourState.root || createAdminTour();
    adminTourState.root = root;
    return {
        root,
        spotlight: root.querySelector('.admin-tour__spotlight'),
        card: root.querySelector('.admin-tour__card'),
        counter: root.querySelector('[data-tour-counter]'),
        title: root.querySelector('[data-tour-title]'),
        text: root.querySelector('[data-tour-text]'),
        prev: root.querySelector('[data-tour-prev]'),
        next: root.querySelector('[data-tour-next]'),
    };
}

function visibleAdminTourSteps() {
    return adminTourSteps.filter((step) => document.querySelector(step.selector));
}

function closeAdminTour() {
    const { root } = adminTourElements();
    adminTourState.target?.classList.remove('admin-tour-highlight');
    adminTourState.target = null;
    root.hidden = true;
}

function positionAdminTour() {
    const { root, spotlight, card } = adminTourElements();
    const target = adminTourState.target;

    if (root.hidden || !target) {
        return;
    }

    const rect = target.getBoundingClientRect();
    const gap = 14;
    const padding = 10;
    const left = Math.max(padding, rect.left - padding);
    const top = Math.max(padding, rect.top - padding);
    const width = Math.min(window.innerWidth - left - padding, rect.width + padding * 2);
    const height = Math.min(window.innerHeight - top - padding, rect.height + padding * 2);

    spotlight.style.left = `${left}px`;
    spotlight.style.top = `${top}px`;
    spotlight.style.width = `${Math.max(40, width)}px`;
    spotlight.style.height = `${Math.max(40, height)}px`;

    const cardRect = card.getBoundingClientRect();
    const canRight = rect.right + gap + cardRect.width <= window.innerWidth - gap;
    const canLeft = rect.left - gap - cardRect.width >= gap;
    let cardLeft = canRight ? rect.right + gap : canLeft ? rect.left - gap - cardRect.width : gap;
    let cardTop = rect.top;

    if (!canRight && !canLeft) {
        cardLeft = Math.min(Math.max(gap, rect.left), window.innerWidth - cardRect.width - gap);
        cardTop = rect.bottom + gap;
        if (cardTop + cardRect.height > window.innerHeight - gap) {
            cardTop = Math.max(gap, rect.top - cardRect.height - gap);
        }
    }

    cardTop = Math.min(Math.max(gap, cardTop), window.innerHeight - cardRect.height - gap);
    card.style.left = `${cardLeft}px`;
    card.style.top = `${cardTop}px`;
}

function showAdminTourStep(index) {
    const steps = visibleAdminTourSteps();
    const { root, counter, title, text, prev, next } = adminTourElements();

    if (!steps.length) {
        return;
    }

    adminTourState.index = Math.min(Math.max(index, 0), steps.length - 1);
    const step = steps[adminTourState.index];
    const target = document.querySelector(step.selector);

    adminTourState.target?.classList.remove('admin-tour-highlight');
    adminTourState.target = target;
    target.classList.add('admin-tour-highlight');
    root.hidden = false;

    counter.textContent = `${adminTourState.index + 1} из ${steps.length}`;
    title.textContent = step.title;
    text.textContent = step.text;
    prev.disabled = adminTourState.index === 0;
    next.textContent = adminTourState.index === steps.length - 1 ? 'Завершить' : 'Далее';

    target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    requestAnimationFrame(positionAdminTour);
    setTimeout(positionAdminTour, 260);
}

function nextAdminTourStep() {
    const steps = visibleAdminTourSteps();
    if (adminTourState.index >= steps.length - 1) {
        closeAdminTour();
        return;
    }
    showAdminTourStep(adminTourState.index + 1);
}

function initAdminTour() {
    const start = document.querySelector('[data-admin-tour-start]');
    if (!start) {
        return;
    }

    const { root, prev, next } = adminTourElements();
    start.addEventListener('click', () => showAdminTourStep(0));
    root.querySelectorAll('[data-tour-close]').forEach((button) => button.addEventListener('click', closeAdminTour));
    prev.addEventListener('click', () => showAdminTourStep(adminTourState.index - 1));
    next.addEventListener('click', nextAdminTourStep);

    document.addEventListener('keydown', (event) => {
        if (root.hidden) {
            return;
        }

        if (event.key === 'Escape') {
            closeAdminTour();
        } else if (event.key === 'ArrowRight') {
            nextAdminTourStep();
        } else if (event.key === 'ArrowLeft') {
            showAdminTourStep(adminTourState.index - 1);
        }
    });

    window.addEventListener('resize', positionAdminTour);
    document.querySelector('.admin-main')?.addEventListener('scroll', positionAdminTour, { passive: true });
    window.addEventListener('scroll', positionAdminTour, { passive: true });
}

function normalizeGalleryItems(images) {
    return (Array.isArray(images) ? images : [])
        .filter(Boolean)
        .map((item) => {
            if (typeof item === 'string') {
                return { id: '', url: item, file: null, name: '' };
            }

            return {
                id: item.id ? String(item.id) : '',
                url: item.url || item.src || '',
                file: item.file || null,
                name: item.name || item.file?.name || '',
            };
        })
        .filter((item) => item.url || item.file);
}

function galleryItems(upload) {
    if (!upload) {
        return [];
    }

    upload._galleryItems = normalizeGalleryItems(upload._galleryItems || []);
    upload._images = upload._galleryItems.map((item) => item.url).filter(Boolean);
    return upload._galleryItems;
}

function updateGalleryPreview(upload, images) {
    const list = normalizeGalleryItems(images);
    const image = upload?.querySelector('[data-gallery-last-preview]');
    const dropzone = upload?.querySelector('.admin-upload__dropzone');
    const count = upload?.querySelector('[data-gallery-count]');
    const button = upload?.querySelector('[data-gallery-preview]');

    if (!upload || !image || !dropzone) {
        return;
    }

    upload._galleryItems = list;
    upload._images = list.map((item) => item.url).filter(Boolean);
    image.src = list[list.length - 1]?.url || image.dataset.defaultSrc || BLANK_IMAGE_SRC;
    dropzone.classList.toggle('is-empty', list.length === 0);
    if (count) {
        count.textContent = list.length ? `В галерее ${list.length} изображ.` : 'Изображения не выбраны';
    }
    if (button) {
        button.hidden = list.length === 0;
    }
}

async function loadItem(section, id) {
    const entity = sectionEntity(section);
    const response = await fetch(entityUrl(entity, id), { headers: { Accept: 'application/json' } });
    const payload = await response.json();

    if (!response.ok) {
        throw new Error(payload.error || 'Не удалось загрузить запись.');
    }

    return payload.item;
}

function cleanFormData(form) {
    const data = new FormData(form);

    form.querySelectorAll('input[type="file"]').forEach((input) => {
        if (!input.files || input.files.length === 0) {
            data.delete(input.name);
        }
    });

    form.querySelectorAll('[data-gallery-upload]').forEach((upload) => {
        const input = upload.querySelector('input[type="file"]');
        const inputName = input?.name || 'gallery_images';
        const items = galleryItems(upload);

        data.delete(inputName);
        data.delete('gallery_keep_ids');
        data.append('gallery_keep_ids', '');
        items.forEach((item) => {
            if (item.file) {
                data.append(inputName, item.file, item.file.name);
            } else if (item.id) {
                data.append('gallery_keep_ids', item.id);
            }
        });
    });

    formFields(form).forEach((field) => {
        if (field.disabled || field.name === '') {
            data.delete(field.name);
        }
    });

    return data;
}

async function saveForm(section) {
    const form = getForm(section);
    const entity = sectionEntity(section);
    const isEdit = form.dataset.mode === 'edit';
    const url = isEdit ? entityUrl(entity, form.dataset.id) : entityUrl(entity);
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken(), Accept: 'application/json' },
        body: cleanFormData(form),
    });
    const responseText = await response.text();
    let payload = {};

    try {
        payload = responseText ? JSON.parse(responseText) : {};
    } catch (error) {
        payload = { error: responseText.trim() };
    }

    if (!response.ok || payload.ok === false) {
        const message = payload.errors
            ? Object.entries(payload.errors).map(([key, value]) => {
                const errorText = Array.isArray(value) ? value.join(', ') : String(value);
                return `${key}: ${errorText}`;
            }).join('\n')
            : payload.error;
        const fallback = response.status ? `Не удалось сохранить запись. Код ответа: ${response.status}.` : 'Не удалось сохранить запись.';
        throw new Error(message || fallback);
    }
}

async function syncCdekTracking(section) {
    const form = getForm(section);
    const id = form?.dataset.id;

    if (sectionEntity(section) !== 'orders' || form?.dataset.mode !== 'edit' || !id) {
        throw new Error('Сначала выберите заказ.');
    }

    const response = await fetch(`${entityUrl('orders', id)}cdek-tracking/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken(), Accept: 'application/json' },
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || 'Не удалось обновить статус СДЭК.');
    }

    if (payload.item) {
        fillForm(section, payload.item);
        form.dataset.currentItem = JSON.stringify(payload.item);
    }

    return payload.item;
}

async function deleteRow(section, id) {
    const entity = sectionEntity(section);
    const response = await fetch(entityUrl(entity, id), {
        method: 'DELETE',
        headers: { 'X-CSRFToken': csrfToken(), Accept: 'application/json' },
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || 'Не удалось удалить запись.');
    }
}

function initUploads(scope = document) {
    scope.querySelectorAll('[data-image-upload], [data-gallery-upload]').forEach((upload) => {
        const input = upload.querySelector('input[type="file"]');
        const dropzone = upload.querySelector('.admin-upload__dropzone');
        const image = upload.querySelector('img');

        if (image && !image.dataset.defaultSrc) {
            image.dataset.defaultSrc = image.getAttribute('src') || BLANK_IMAGE_SRC;
        }
        if (!input || !dropzone) {
            return;
        }

        const applyFiles = (files) => {
            const fileList = [...files].filter((file) => file.type.startsWith('image/'));
            if (fileList.length === 0) {
                return;
            }

            if (upload.hasAttribute('data-gallery-upload')) {
                const nextItems = galleryItems(upload).concat(
                    fileList.map((file) => ({
                        id: '',
                        file,
                        url: URL.createObjectURL(file),
                        name: file.name,
                    }))
                );
                updateGalleryPreview(upload, nextItems);
                input.value = '';
            } else {
                updateImagePreview(image, URL.createObjectURL(fileList[0]));
            }
        };

        dropzone.addEventListener('click', () => input.click());
        dropzone.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                input.click();
            }
        });
        input.addEventListener('change', () => applyFiles(input.files || []));

        ['dragenter', 'dragover'].forEach((eventName) => {
            upload.addEventListener(eventName, (event) => {
                event.preventDefault();
                dropzone.classList.add('is-dragover');
            });
        });
        upload.addEventListener('dragleave', (event) => {
            event.preventDefault();
            if (!upload.contains(event.relatedTarget)) {
                dropzone.classList.remove('is-dragover');
            }
        });
        upload.addEventListener('drop', (event) => {
            event.preventDefault();
            dropzone.classList.remove('is-dragover');
            applyFiles(event.dataTransfer?.files || []);
        });
    });
}

function initPreviewModal() {
    const modal = document.querySelector('[data-preview-modal]');
    const image = modal?.querySelector('.admin-preview-modal__dialog > img');
    const gallery = modal?.querySelector('[data-preview-gallery]');
    const title = modal?.querySelector('#admin-preview-title');

    if (!modal || !image || !gallery || !title) {
        return;
    }

    const close = () => {
        modal.hidden = true;
        gallery.hidden = true;
        gallery.innerHTML = '';
        image.hidden = false;
        image.src = BLANK_IMAGE_SRC;
    };

    document.querySelectorAll('.admin-category-preview').forEach((button) => {
        button.addEventListener('click', () => {
            title.textContent = button.closest('tr')?.querySelector('td')?.innerText.trim() || 'Превью';
            image.src = button.dataset.previewUrl || button.querySelector('img')?.src || BLANK_IMAGE_SRC;
            image.hidden = false;
            gallery.hidden = true;
            gallery.innerHTML = '';
            modal.hidden = false;
        });
    });

    const renderGalleryModal = (upload) => {
        const items = galleryItems(upload);
        title.textContent = 'Галерея изображений';
        image.hidden = true;
        gallery.innerHTML = '';
        gallery.hidden = false;

        items.forEach((item, index) => {
            const card = document.createElement('div');
            card.className = 'admin-preview-gallery__item';

            const picture = document.createElement('img');
            picture.src = item.url || BLANK_IMAGE_SRC;
            picture.alt = item.name || '';

            const remove = document.createElement('button');
            remove.type = 'button';
            remove.textContent = '×';
            remove.setAttribute('aria-label', 'Удалить изображение');
            remove.addEventListener('click', () => {
                const nextItems = galleryItems(upload).filter((_, itemIndex) => itemIndex !== index);
                updateGalleryPreview(upload, nextItems);

                if (nextItems.length === 0) {
                    close();
                    return;
                }

                renderGalleryModal(upload);
            });

            card.append(picture, remove);
            gallery.append(card);
        });
    };

    document.querySelectorAll('[data-gallery-preview]').forEach((button) => {
        button.addEventListener('click', () => {
            const upload = button.closest('[data-gallery-upload]');
            if (galleryItems(upload).length === 0) {
                return;
            }
            renderGalleryModal(upload);
            modal.hidden = false;
        });
    });

    modal.querySelectorAll('[data-preview-close]').forEach((button) => {
        button.addEventListener('click', close);
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.hidden) {
            close();
        }
    });
}

function initAutoFields(section) {
    const form = getForm(section);
    const title = form?.elements.namedItem('title');
    const slug = form?.querySelector('[data-slug-field]');
    const code = form?.querySelector('[data-code-field]');

    title?.addEventListener('input', () => {
        if (slug && form.dataset.mode !== 'edit') {
            slug.value = createSlug(title.value);
        }
        if (code && form.dataset.mode !== 'edit') {
            code.value = createSlug(title.value).replace(/-/g, '_');
        }
    });
}

function initSection(section) {
    const entity = sectionEntity(section);
    const form = getForm(section);
    const newButton = section.querySelector('[data-new-record]');

    if (!form || !entity) {
        return;
    }

    setMode(section, section.dataset.readonlyCreate ? 'edit' : 'create');
    initAutoFields(section);

    if (entity === 'categories') {
        form.elements.namedItem('parent')?.addEventListener('change', () => updateCategoryPosition(form, true));
        updateCategoryPosition(form);
    }

    const editRow = async (row, shouldScroll = true) => {
        const id = row?.dataset.adminId;
        if (!id) {
            return;
        }

        const item = await loadItem(section, id);
        section.querySelectorAll('tr').forEach((tableRow) => tableRow.classList.toggle('is-selected', tableRow === row));
        fillForm(section, item);
        form.dataset.currentItem = JSON.stringify(item);
        setMode(section, 'edit', id);
        if (shouldScroll) {
            form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    };

    newButton?.addEventListener('click', () => {
        resetForm(section);
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });

    form.querySelector('[data-reset-form]')?.addEventListener('click', () => {
        if (form.dataset.mode === 'edit' && form.dataset.currentItem) {
            fillForm(section, JSON.parse(form.dataset.currentItem));
        } else {
            resetForm(section);
        }
    });

    form.querySelector('[data-sync-cdek]')?.addEventListener('click', async () => {
        try {
            await saveForm(section);
            await syncCdekTracking(section);
            rememberAdminScroll();
            window.location.reload();
        } catch (error) {
            window.alert(error.message);
        }
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (section.dataset.readonlyCreate && form.dataset.mode !== 'edit') {
            window.alert('Сначала выберите запись в таблице.');
            return;
        }
        try {
            await saveForm(section);
            rememberAdminScroll();
            window.location.reload();
        } catch (error) {
            window.alert(error.message);
        }
    });

    section.querySelectorAll('[data-edit-row]').forEach((button) => {
        button.addEventListener('click', async () => {
            const row = button.closest('tr');
            try {
                await editRow(row);
            } catch (error) {
                window.alert(error.message);
            }
        });
    });

    section.querySelectorAll('[data-delete-row]').forEach((button) => {
        button.addEventListener('click', async () => {
            const row = button.closest('tr');
            const id = row?.dataset.adminId;
            const title = row?.querySelector('td')?.innerText.trim() || 'запись';

            if (!id || !window.confirm(`Удалить ${title}?`)) {
                return;
            }
            try {
                await deleteRow(section, id);
                rememberAdminScroll();
                window.location.reload();
            } catch (error) {
                window.alert(error.message);
            }
        });
    });

    const firstRow = section.querySelector('tbody tr[data-admin-id]');
    if (section.dataset.readonlyCreate && firstRow) {
        editRow(firstRow, false).catch((error) => window.alert(error.message));
    }
}

initUploads();
initPreviewModal();
initCustomSelects();
initCategoryFilters();
initProductFilters();
initSecondaryTableFilters();
initAdminNavigation();
initAdminTour();
document.querySelectorAll('.admin-section[data-entity]').forEach(initSection);
restoreAdminScroll();

document.addEventListener('click', (event) => {
    if (!event.target.closest('.admin-custom-select') && !event.target.closest('.admin-custom-select__menu')) {
        closeCustomSelects();
    }
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeCustomSelects();
        closeAdminTour();
    }
});

window.addEventListener('resize', () => {
    document.querySelectorAll('.admin-custom-select.is-open').forEach(positionCustomSelectMenu);
});

document.querySelector('.admin-main')?.addEventListener('scroll', () => {
    document.querySelectorAll('.admin-custom-select.is-open').forEach(positionCustomSelectMenu);
}, { passive: true });
