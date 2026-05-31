const headers = document.querySelectorAll('.user-item__header');
const navItems = document.querySelectorAll('.cabinet-nav__item');
const contents = document.querySelectorAll('.cabinet-content');
const moreButtons = document.querySelectorAll('.order-item__inner-item__more');
const profileEmailInputs = document.querySelectorAll('[data-profile-email], [data-profile-field="email"]');
const profileFields = document.querySelectorAll('[data-profile-field]');
const profileTypeInputs = document.querySelectorAll('[data-profile-type]');
const profileSaveButtons = document.querySelectorAll('[data-profile-save]');
const profileMessage = document.querySelector('[data-profile-message]');
const profileTypeTitle = document.querySelector('[data-profile-type-title]');
const logoutButton = document.querySelector('.cabinet-nav__button');
const ordersList = document.querySelector('[data-cabinet-orders]');

const profileTypeTitleMap = {
    person: 'Для физических лиц',
    entrepreneur: 'Для ИП',
    company: 'Для юридических лиц',
};

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);

    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }

    return '';
}

async function cabinetApi(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            ...(options.headers || {}),
        },
    });
    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.ok === false) {
        throw new Error(result.error || 'Не удалось выполнить запрос.');
    }

    return result;
}

function setProfileMessage(text, type = 'error') {
    if (!profileMessage) {
        return;
    }

    profileMessage.textContent = text;
    profileMessage.className = `cabinet-profile__message cabinet-profile__message--${type}`;
}

function isValidEmail(email) {
    const value = String(email || '').trim();
    return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value) && value.length <= 254;
}

function isValidPhone(phone) {
    const value = String(phone || '').trim();

    if (!value || /[^0-9\s()+.-]/.test(value)) {
        return false;
    }

    if ((value.match(/\+/g) || []).length > 1 || (value.includes('+') && !value.startsWith('+'))) {
        return false;
    }

    const digits = value.replace(/\D/g, '');
    return digits.length >= 10 && digits.length <= 15;
}

function isValidPersonName(name, required = true) {
    const value = String(name || '').trim();

    if (!value) {
        return !required;
    }

    return value.length >= 2
        && value.length <= 80
        && /^[A-Za-zА-Яа-яЁё]+(?:[ '-][A-Za-zА-Яа-яЁё]+)*$/.test(value);
}

function setProfileValue(field, value) {
    document.querySelectorAll(`[data-profile-field="${field}"]`).forEach(input => {
        input.value = value || '';
    });

    if (field === 'email') {
        profileEmailInputs.forEach(input => {
            input.value = value || '';
        });
    }
}

function fillProfile(profile) {
    setProfileValue('lastName', profile.lastName);
    setProfileValue('firstName', profile.firstName);
    setProfileValue('middleName', profile.middleName);
    setProfileValue('phone', profile.phone);
    setProfileValue('email', profile.email);

    const type = profile.type || 'person';
    profileTypeInputs.forEach(input => {
        input.checked = input.value === type;
    });

    if (profileTypeTitle) {
        profileTypeTitle.textContent = profileTypeTitleMap[type] || profile.typeTitle || 'Личные данные';
    }
}

function getProfilePayload() {
    const field = name => document.querySelector(`[data-profile-field="${name}"]`)?.value.trim() || '';
    const email = document.querySelector('[data-profile-field="email"]')?.value.trim()
        || document.querySelector('[data-profile-email]')?.value.trim()
        || '';

    return {
        email,
        firstName: field('firstName'),
        lastName: field('lastName'),
        middleName: field('middleName'),
        phone: field('phone'),
        type: document.querySelector('[data-profile-type]:checked')?.value || 'person',
    };
}

function validateProfilePayload(payload) {
    if (!isValidEmail(payload.email)) {
        return 'Введите корректный e-mail.';
    }

    if (!isValidPersonName(payload.lastName)) {
        return 'Введите корректную фамилию.';
    }

    if (!isValidPersonName(payload.firstName)) {
        return 'Введите корректное имя.';
    }

    if (!isValidPersonName(payload.middleName, false)) {
        return 'Введите корректное отчество.';
    }

    if (!isValidPhone(payload.phone)) {
        return 'Введите корректный номер телефона.';
    }

    return '';
}

async function loadProfile() {
    if (!profileFields.length) {
        return;
    }

    try {
        const result = await cabinetApi('cabinet/api/profile/');
        fillProfile(result.profile);
    } catch (error) {
        setProfileMessage('Войдите или зарегистрируйтесь перед использованием кабинета.');
    }
}

async function saveProfile() {
    const payload = getProfilePayload();
    const error = validateProfilePayload(payload);

    if (error) {
        setProfileMessage(error);
        return;
    }

    try {
        const result = await cabinetApi('cabinet/api/profile/update/', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        fillProfile(result.profile);
        setProfileMessage('Изменения профиля сохранены.', 'success');
    } catch (error) {
        setProfileMessage(error.message);
    }
}

const orderExpandIcon = `
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M10.7909 4.84793L7.25927 8.3796C6.84219 8.79668 6.15969 8.79668 5.7426 8.3796L2.21094 4.84793" stroke="currentColor" stroke-opacity="0.8" stroke-width="1.1" stroke-miterlimit="10" stroke-linecap="square" stroke-linejoin="bevel"/>
    </svg>
`;

const orderRepeatIcon = `
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M13.773 6.03769L13.2426 5.50736C10.8995 3.16422 7.1005 3.16422 4.75736 5.50736C2.41421 7.85051 2.41421 11.6495 4.75736 13.9926C7.1005 16.3358 10.8995 16.3358 13.2426 13.9926C14.6053 12.63 15.1755 10.7751 14.9533 9.00039M13.773 2.85571V6.03769H10.591" stroke="currentColor" stroke-opacity="1" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
`;

const orderPayIcon = `
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8.41797 3.45917L11.9588 7L8.41797 10.5408" stroke="currentColor" stroke-width="1.2" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M2.04102 7H11.8585" stroke="currentColor" stroke-width="1.2" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
`;

const orderDotIcon = `
    <svg width="3" height="3" viewBox="0 0 3 3" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="1.5" cy="1.5" r="1.5" fill="#121212" fill-opacity="0.16"/>
    </svg>
`;

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function formatMoney(value) {
    if (value === null || value === undefined || value === '') {
        return 'После расчета';
    }

    const amount = Number(value || 0);

    return `${new Intl.NumberFormat('ru-RU', {
        minimumFractionDigits: Number.isInteger(amount) ? 0 : 2,
        maximumFractionDigits: 2,
    }).format(amount)} руб.`;
}

function formatOrderDate(value) {
    if (!value) {
        return '';
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return '';
    }

    const formatted = new Intl.DateTimeFormat('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
    }).format(date).replace(' г.', '');

    return `от ${formatted}`;
}

function orderStatusClass(status) {
    return {
        'pending-manager-confirmation': 'order-status--pending',
        'pending-manager-calculation': 'order-status--pending',
        'manager-confirmed': 'order-status--success',
        processing: 'order-status--process',
        delivered: 'order-status--done',
        canceled: 'order-status--cancel',
    }[status] || 'order-status--pending';
}

function objectTitle(value) {
    return value && typeof value === 'object' ? (value.title || value.name || '') : '';
}

function orderItemDetails(item) {
    const details = [];

    if (item.sku) {
        details.push(`Артикул: ${item.sku}`);
    }
    if (objectTitle(item.shape)) {
        details.push(`Тип: ${objectTitle(item.shape)}`);
    }

    const dimensions = Array.isArray(item.dimensions) ? item.dimensions.map(dimension => {
        const title = dimension.title || dimension.name || dimension.label || '';
        const value = dimension.value ?? dimension.amount ?? '';
        const unit = dimension.unit || dimension.unitTitle || '';
        const measurement = [value, unit].filter(Boolean).join(' ');

        return [title, measurement].filter(Boolean).join(': ');
    }).filter(Boolean) : [];

    if (dimensions.length) {
        details.push(`Размеры: ${dimensions.join(', ')}`);
    }
    if (objectTitle(item.fabric)) {
        details.push(`Материал: ${objectTitle(item.fabric)}`);
    }
    if (objectTitle(item.color)) {
        details.push(`Цвет: ${objectTitle(item.color)}`);
    }
    if (objectTitle(item.fastener)) {
        details.push(`Крепление: ${objectTitle(item.fastener)}`);
    }
    if (objectTitle(item.accessory)) {
        details.push(`Дополнительно: ${objectTitle(item.accessory)}`);
    }
    if (item.comments) {
        details.push(`Комментарий: ${item.comments}`);
    }

    const attachments = Array.isArray(item.attachments) ? item.attachments.map(file => file.name).filter(Boolean) : [];
    if (attachments.length) {
        details.push(`Файлы: ${attachments.join(', ')}`);
    }

    return details.join('; ') || 'Параметры позиции сохранены в заказе.';
}

function renderOrderPosition(item, index) {
    const isOpen = index === 0;
    const hasPrice = item.totalPrice !== null && item.totalPrice !== undefined && item.totalPrice !== '';
    const quantity = item.quantity ? `${escapeHtml(item.quantity)} шт.` : '';
    const total = item.totalTitle || (hasPrice ? formatMoney(item.totalPrice) : 'После расчета');

    return `
        <div class="order-item__inner-item${isOpen ? ' open' : ''}">
            <h4>${escapeHtml(item.title || 'Позиция заказа')}</h4>
            <button class="order-item__inner-item__more" type="button" data-order-more>
                <p>${isOpen ? 'Скрыть' : 'Подробнее'}</p>
                ${orderExpandIcon}
            </button>
            <div class="order-item__inner-item__dropdown">
                <p>${escapeHtml(orderItemDetails(item))}</p>
            </div>
            <div class="order-item__inner-item__price">
                ${quantity ? `<p>${quantity}</p>${orderDotIcon}` : ''}
                <p>${escapeHtml(total)}</p>
            </div>
        </div>
    `;
}

function renderOrder(order) {
    const items = Array.isArray(order.items) ? order.items : [];
    const orderId = String(order.id || '');
    const canPay = order.canPay === true || (order.canPay !== false && order.status === 'manager-confirmed');
    const canRepeat = order.canRepeat !== false;
    const isDrawingOrder = order.type === 'drawing-order';
    const total = order.summary?.totalTitle || formatMoney(order.summary?.total);
    const paymentUrl = String(order.paymentUrl || '');

    return `
        <div class="order-item" data-order-id="${escapeHtml(orderId)}" data-payment-url="${escapeHtml(paymentUrl)}">
            <div class="order-item__header">
                <div class="order-item__header-left">
                    <h3>${isDrawingOrder ? 'Заявка по чертежу' : 'Заказ'} №${escapeHtml(orderId)}</h3>
                    <p>${escapeHtml(formatOrderDate(order.createdAt))}</p>
                </div>
                <div class="order-item__status ${orderStatusClass(order.status)}">${escapeHtml(order.statusTitle || 'Ожидает обработки')}</div>
            </div>
            <div class="order-item__inner">
                ${items.length ? items.map(renderOrderPosition).join('') : '<p class="order-list__message">В заказе нет позиций.</p>'}
            </div>
            <div class="order-item__row">
                <p class="order-item__price">Итого: <b>${escapeHtml(total)}</b></p>
                ${canRepeat && !isDrawingOrder ? `
                    <button type="button" data-repeat-order="${escapeHtml(orderId)}">
                        ${orderRepeatIcon}
                        Повторить заказ
                    </button>
                ` : ''}
            </div>
            ${canPay && !isDrawingOrder ? `
                <button class="order-item__pay" type="button" data-pay-order="${escapeHtml(orderId)}">
                    Оплатить заказ
                    ${orderPayIcon}
                </button>
            ` : ''}
        </div>
    `;
}

function setOrdersMessage(text, type = '') {
    if (!ordersList) {
        return;
    }

    ordersList.innerHTML = `<div class="order-list__message${type ? ` order-list__message--${type}` : ''}">${escapeHtml(text)}</div>`;
}

async function loadOrders() {
    if (!ordersList) {
        return;
    }

    setOrdersMessage('Загружаем заказы...');

    try {
        const result = await cabinetApi('cabinet/api/orders/');
        const orders = Array.isArray(result.orders) ? result.orders : [];

        if (!orders.length) {
            setOrdersMessage('Заказы пока не созданы.');
            return;
        }

        ordersList.innerHTML = orders.map(renderOrder).join('');
    } catch (error) {
        setOrdersMessage(error.message || 'Не удалось загрузить заказы.', 'error');
    }
}

headers.forEach(header => {
    header.addEventListener('click', () => {
        const userItem = header.closest('.user-item');
        userItem.classList.toggle('user-item--open');
    });
});

navItems.forEach((item, index) => {
    item.addEventListener('click', () => {
        navItems.forEach(el => {
            el.classList.remove('cabinet-nav__item--active');
        });
        contents.forEach(el => {
            el.classList.remove('cabinet-content--active');
        });
        item.classList.add('cabinet-nav__item--active');
        contents[index].classList.add('cabinet-content--active');
    });
});

moreButtons.forEach(button => {
    button.addEventListener('click', () => {
        const item = button.closest('.order-item__inner-item');
        const text = button.querySelector('p');

        item.classList.toggle('open');
        text.textContent = item.classList.contains('open') ? 'Скрыть' : 'Подробнее';
    });
});

ordersList?.addEventListener('click', async event => {
    const moreButton = event.target.closest('[data-order-more]');
    if (moreButton && ordersList.contains(moreButton)) {
        const item = moreButton.closest('.order-item__inner-item');
        const text = moreButton.querySelector('p');

        item.classList.toggle('open');
        text.textContent = item.classList.contains('open') ? 'Скрыть' : 'Подробнее';
        return;
    }

    const repeatButton = event.target.closest('[data-repeat-order]');
    if (repeatButton && ordersList.contains(repeatButton)) {
        repeatButton.disabled = true;

        try {
            await cabinetApi(`cabinet/api/orders/${encodeURIComponent(repeatButton.dataset.repeatOrder)}/repeat/`, {
                method: 'POST',
                body: '{}',
            });
            window.location.href = 'card.html';
        } catch (error) {
            repeatButton.disabled = false;
            setOrdersMessage(error.message || 'Не удалось повторить заказ.', 'error');
        }
        return;
    }

    const payButton = event.target.closest('[data-pay-order]');
    if (payButton && ordersList.contains(payButton)) {
        const orderItem = payButton.closest('.order-item');
        const paymentUrl = orderItem?.dataset.paymentUrl || '';

        if (paymentUrl) {
            window.location.href = paymentUrl;
            return;
        }

        payButton.disabled = true;
        payButton.textContent = 'Оплата пока не подключена';
    }
});

profileSaveButtons.forEach(button => {
    button.addEventListener('click', saveProfile);
});

profileEmailInputs.forEach(input => {
    input.addEventListener('input', () => {
        profileEmailInputs.forEach(otherInput => {
            if (otherInput !== input) {
                otherInput.value = input.value;
            }
        });
    });
});

logoutButton?.addEventListener('click', async () => {
    try {
        await cabinetApi('auth/api/logout/', { method: 'POST', body: '{}' });
    } finally {
        localStorage.removeItem('ditentCheckoutAuth');
        window.location.href = 'index.html';
    }
});

loadProfile();
loadOrders();
