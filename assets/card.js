const CART_KEY = 'ditentCart';
const ORDERS_KEY = 'ditentOrders';
const AUTH_KEY = 'ditentCheckoutAuth';
const DELIVERY_LOCATION_CACHE_PREFIX = 'ditentDeliveryLocation:v4:';
const DELIVERY_LOCATION_CACHE_TTL = 6 * 60 * 60 * 1000;
const VAT_RATE = 0.2;

const cartList = document.querySelector('[data-cart-list]');
const subtotalElement = document.querySelector('[data-cart-subtotal]');
const discountElement = document.querySelector('[data-cart-discount]');
const deliveryElement = document.querySelector('[data-cart-delivery]');
const vatElement = document.querySelector('[data-cart-vat]');
const totalElement = document.querySelector('[data-cart-total]');
const checkoutButton = document.querySelector('[data-checkout-submit]');
const returnConfirm = document.querySelector('[data-return-confirm]');
const orderMessage = document.querySelector('[data-order-message]');
let latestDeliveryQuote = null;
const deliveryLocationState = {
    country: null,
    region: null,
    city: null,
    pickupPoint: null,
};

function formatPrice(value) {
    return `${Math.round(value).toLocaleString('ru-RU')} руб.`;
}

function readJson(key, fallback) {
    try {
        return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
    } catch {
        return fallback;
    }
}

function writeJson(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
    if (key === CART_KEY) {
        window.ditentUpdateCartBadge?.(value);
        window.dispatchEvent(new CustomEvent('ditent:cart-updated', { detail: { items: value } }));
    }
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);

    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }

    return '';
}

async function cartApi(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            Accept: 'application/json',
            ...(options.headers || {}),
        },
    });
    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.ok === false) {
        throw new Error(result.error || 'Не удалось обновить корзину.');
    }

    if (result.cart?.items) {
        writeJson(CART_KEY, result.cart.items);
    }

    return result.cart;
}

async function loadCartFromBackend() {
    return cartApi('cart/api/', { method: 'GET', headers: {} });
}

async function loadAuthStatus() {
    const response = await fetch('auth/api/status/', {
        headers: { Accept: 'application/json' },
    });
    const result = await response.json().catch(() => ({}));

    if (result.authenticated && result.user?.email) {
        setAuthState({
            mode: 'session',
            email: result.user.email,
            authorizedAt: new Date().toISOString(),
        });
        fillClientFromUser(result.user);
    } else {
        localStorage.removeItem(AUTH_KEY);
    }

    return result;
}

window.addEventListener('ditent:auth-changed', event => {
    const user = event.detail?.user;

    if (user?.email) {
        setAuthState({
            mode: 'session',
            email: user.email,
            authorizedAt: new Date().toISOString(),
        });
        fillClientFromUser(user);
    }
});

window.addEventListener('storage', event => {
    if (event.key === AUTH_KEY && event.newValue) {
        loadAuthStatus().catch(() => {});
    }
});

async function updateCartItemQuantityOnBackend(id, quantity) {
    return cartApi(`cart/api/items/${encodeURIComponent(id)}/quantity/`, {
        method: 'POST',
        body: JSON.stringify({ quantity }),
    });
}

async function deleteCartItemOnBackend(id) {
    return cartApi(`cart/api/items/${encodeURIComponent(id)}/delete/`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

function getCart() {
    return readJson(CART_KEY, []).map((item, index) => ({
        id: item.id || `cart-item-${index}`,
        type: item.type || '',
        title: item.title || 'Чехол по индивидуальным размерам',
        sku: item.sku || 'DT-CUSTOM',
        quantity: Number(item.quantity || 1),
        stock: Number(item.stock || 0),
        unitPrice: Number(item.unitPrice || item.price || 0),
        totalPrice: Number(item.totalPrice || (item.unitPrice || item.price || 0) * (item.quantity || 1)),
        shape: item.shape || null,
        dimensions: item.dimensions || [],
        fabric: item.fabric || null,
        color: item.color || null,
        fastener: item.fastener || null,
        accessory: item.accessory || null,
        comments: item.comments || '',
        image: item.image || 'assets/image/card-img-1.png',
        attachments: item.attachments || [],
    }));
}

function setCart(cart) {
    writeJson(CART_KEY, cart.map(item => ({
        ...item,
        quantity: Number(item.quantity || 1),
        totalPrice: Number(item.unitPrice || 0) * Number(item.quantity || 1),
    })));
}

function getSelectedDelivery() {
    const input = document.querySelector('input[name="delivery"]:checked');
    const addressInput = input?.closest('.card-delivery')?.querySelector('.card-delivery__address input');
    const pickupAddress = input?.value === 'cdek-point' ? deliveryLocationState.pickupPoint?.address || '' : '';

    return {
        type: input?.value || '',
        title: input?.dataset.deliveryTitle || '',
        price: Number(input?.dataset.deliveryPrice || 0),
        provider: input?.dataset.deliveryProvider || '',
        days: input?.dataset.deliveryDays || '',
        note: input?.dataset.deliveryNote || '',
        pickupPointCode: deliveryLocationState.pickupPoint?.code || '',
        pickupPointTitle: deliveryLocationState.pickupPoint?.title || '',
        pickupPointAddress: pickupAddress,
        address: pickupAddress || addressInput?.value.trim() || '',
    };
}

function getSelectedPayment() {
    const input = document.querySelector('input[name="payment"]:checked');

    return {
        type: input?.value || '',
        title: input?.dataset.paymentTitle || input?.closest('.card-item__payments-method')?.querySelector('h4')?.textContent.trim() || '',
    };
}

function getAuthState() {
    return readJson(AUTH_KEY, null);
}

function setAuthState(state) {
    writeJson(AUTH_KEY, state);
}

function getClientType() {
    const input = document.querySelector('input[name="user"]:checked');

    return input?.value || input?.closest('.card-item__user-label')?.textContent.trim() || 'person';
}

function getClientData() {
    return {
        type: getClientType(),
        lastName: document.querySelector('[data-client-field="lastName"]')?.value.trim() || '',
        firstName: document.querySelector('[data-client-field="firstName"]')?.value.trim() || '',
        middleName: document.querySelector('[data-client-field="middleName"]')?.value.trim() || '',
        phone: document.querySelector('[data-client-field="phone"]')?.value.trim() || '',
        email: document.querySelector('[data-client-field="email"]')?.value.trim() || '',
        comment: document.querySelector('[data-client-field="comment"]')?.value.trim() || '',
    };
}

function setAuthFormValue(form, name, value) {
    const field = form?.querySelector(`[name="${name}"]`);

    if (field && value) {
        field.value = value;
    }
}

function fillAuthModalFromCheckout(client) {
    const loginForm = document.querySelector('[data-auth-login-form]');
    const registerForm = document.querySelector('[data-auth-register-form]');

    setAuthFormValue(loginForm, 'email', client.email);
    setAuthFormValue(registerForm, 'email', client.email);
    setAuthFormValue(registerForm, 'lastName', client.lastName);
    setAuthFormValue(registerForm, 'firstName', client.firstName);
    setAuthFormValue(registerForm, 'middleName', client.middleName);
    setAuthFormValue(registerForm, 'phone', client.phone);

    const typeIndex = { person: 0, company: 1, entrepreneur: 2 }[client.type];
    const typeInputs = registerForm?.querySelectorAll('input[name="authCustomerType"]') || [];

    if (typeIndex !== undefined && typeInputs[typeIndex]) {
        typeInputs[typeIndex].checked = true;
        typeInputs[typeIndex].dispatchEvent(new Event('change', { bubbles: true }));
    }
}

function openCheckoutAuthModal(client) {
    const modal = document.querySelector('[data-auth-modal]');
    const loginForm = document.querySelector('[data-auth-login-form]');
    const registerForm = document.querySelector('[data-auth-register-form]');
    const dialog = modal?.querySelector('[role="dialog"]');
    const message = document.querySelector('[data-auth-message="login"]');

    if (!modal) {
        return;
    }

    fillAuthModalFromCheckout(client);
    modal.hidden = false;
    modal.classList.add('auth-modal--login');
    modal.classList.remove('auth-modal--register', 'auth-modal--code-sent');
    dialog?.setAttribute('aria-labelledby', 'auth-modal-title');
    document.querySelectorAll('[data-auth-code-step]').forEach(step => {
        step.hidden = true;
    });

    if (loginForm) {
        loginForm.hidden = false;
    }

    if (registerForm) {
        registerForm.hidden = true;
    }

    if (message) {
        message.textContent = 'Войдите по e-mail или зарегистрируйтесь. Данные из заказа уже подставлены.';
        message.className = 'auth-modal__message auth-modal__message--error';
    }

    document.body.classList.add('auth-modal-open');
    loginForm?.querySelector('input[name="email"]')?.focus();
}

function fillClientFromUser(user) {
    const fields = {
        lastName: user.lastName || '',
        firstName: user.firstName || '',
        middleName: user.middleName || '',
        phone: user.phone || '',
        email: user.email || '',
    };

    Object.entries(fields).forEach(([key, value]) => {
        const input = document.querySelector(`[data-client-field="${key}"]`);

        if (input && value) {
            input.value = value;
        }
    });

    const clientType = user.type || '';
    const clientTypeTitle = user.typeTitle || '';
    const typeInput = Array.from(document.querySelectorAll('input[name="user"]')).find(input => {
        const title = input.closest('.card-item__user-label')?.textContent.trim() || '';
        return input.value === clientType || title === clientTypeTitle;
    });

    if (typeInput) {
        typeInput.checked = true;
    }
}

function getLocationData() {
    return {
        country: deliveryLocationState.country?.title || '',
        countryCode: deliveryLocationState.country?.code || '',
        region: deliveryLocationState.region?.title || '',
        regionCode: deliveryLocationState.region?.code || '',
        city: deliveryLocationState.city?.title || '',
        cityCode: deliveryLocationState.city?.code || '',
        pickupPointCode: deliveryLocationState.pickupPoint?.code || '',
        pickupPointAddress: deliveryLocationState.pickupPoint?.address || '',
        pickupPointTitle: deliveryLocationState.pickupPoint?.title || '',
    };
}

function baseCartSubtotal(cart = getCart()) {
    return cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0);
}

function baseCartCount(cart = getCart()) {
    return cart.reduce((sum, item) => sum + item.quantity, 0);
}

function updateDeliveryBlock(input, quote) {
    const block = input?.closest('.card-delivery');
    const values = block?.querySelectorAll('.card-delivery__row p b') || [];

    if (quote.title) {
        input.dataset.deliveryTitle = quote.title;
    }

    input.dataset.deliveryPrice = String(quote.price || 0);
    input.dataset.deliveryProvider = quote.provider || '';
    input.dataset.deliveryDays = quote.days || '';
    input.dataset.deliveryNote = quote.note || '';

    if (values[0]) {
        values[0].textContent = quote.days || 'После согласования';
    }

    if (values[2]) {
        values[2].textContent = quote.price > 0 ? formatPrice(quote.price) : 'после расчета';
    }
}

async function refreshDeliveryQuote() {
    const input = document.querySelector('input[name="delivery"]:checked');
    const cart = getCart();

    if (!input || !cart.length) {
        latestDeliveryQuote = null;
        renderSummary(cart);
        return null;
    }

    const payload = {
        method: input.value,
        ...getLocationData(),
        address: input.closest('.card-delivery')?.querySelector('.card-delivery__address input')?.value.trim() || '',
        itemsCount: baseCartCount(cart),
        subtotal: baseCartSubtotal(cart),
        items: cart,
    };
    const response = await fetch('checkout/api/delivery/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            Accept: 'application/json',
        },
        body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.ok === false) {
        throw new Error(result.error || 'Не удалось рассчитать доставку.');
    }

    latestDeliveryQuote = result.quote;
    updateDeliveryBlock(input, latestDeliveryQuote);
    renderSummary(cart);

    return latestDeliveryQuote;
}

function clearValidation() {
    document.querySelectorAll('.card-field--error').forEach(element => {
        element.classList.remove('card-field--error');
    });

    if (orderMessage) {
        orderMessage.textContent = '';
        orderMessage.className = 'card-action__message';
    }
}

function markField(input) {
    input?.closest('label')?.classList.add('card-field--error');
}

function showMessage(text, type = 'error') {
    if (!orderMessage) {
        return;
    }

    orderMessage.textContent = text;
    orderMessage.className = `card-action__message card-action__message--${type}`;
}

function buildDescription(item) {
    const details = [];

    if (item.shape?.title) {
        details.push(item.shape.title);
    }

    if (item.dimensions?.length) {
        details.push(`Размеры: ${item.dimensions.map(dimension => `${dimension.label} ${dimension.code} - ${dimension.value} см`).join(', ')}`);
    }

    if (item.fabric?.name) {
        details.push(`Ткань: ${item.fabric.name}`);
    }

    if (item.color?.name) {
        details.push(`Цвет: ${item.color.name}`);
    }

    if (item.fastener?.name) {
        details.push(`Крепление: ${item.fastener.name}`);
    }

    if (item.accessory?.name) {
        details.push(`Аксессуар: ${item.accessory.name}`);
    }

    if (item.comments) {
        details.push(`Комментарий: ${item.comments}`);
    }

    if (item.attachments?.length) {
        details.push(`Файлы: ${item.attachments.map(file => file.name).join(', ')}`);
    }

    return details.join('; ');
}

function createCartItem(item) {
    const element = document.createElement('div');
    element.className = 'card-checked__item';
    element.dataset.cartId = item.id;
    element.innerHTML = `
        <div class="card-checked__item-img">
            <img src="${item.image}" alt="">
        </div>
        <button class="card-checked__remove" type="button" aria-label="Удалить товар" data-remove-item>
            <svg width="25" height="25" viewBox="0 0 25 25" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M18.75 6.25L6.25 18.75M18.75 18.75L6.25 6.25" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
        </button>
        <div class="card-checked__item-main">
            <div class="card-checked__top">
                <h3>${item.title}</h3>
                <p>${buildDescription(item)}</p>
                <span>Артикул: ${item.sku}</span>
            </div>
            <div class="card-checked__bottom">
                <div class="card-checked__price">
                    <span>Цена:</span>
                    <p>${formatPrice(item.unitPrice)}</p>
                </div>
                <div class="card-checked__right">
                    <div class="card-checked__price">
                        <span>Сумма:</span>
                        <p data-line-total>${formatPrice(item.unitPrice * item.quantity)}</p>
                    </div>
                    <div class="card-checked__counter">
                        <button class="card-checked__counter-btn card-checked__counter-btn--minus" type="button" data-qty-minus>
                            <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M3.75 7.5H11.25" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                        </button>
                        <p class="card-checked__counter-value" data-qty-value>${item.quantity}</p>
                        <button class="card-checked__counter-btn card-checked__counter-btn--plus" type="button" data-qty-plus>
                            <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M3.75 7.5H11.25" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                                <path d="M7.5 11.25V3.75" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    return element;
}

function getSummary(cart = getCart()) {
    const subtotal = baseCartSubtotal(cart);
    const wholesaleDiscount = 0;
    const delivery = cart.length ? getSelectedDelivery().price : 0;
    const taxableAmount = Math.max(subtotal - wholesaleDiscount, 0);
    const vat = taxableAmount * VAT_RATE / (1 + VAT_RATE);
    const total = taxableAmount + delivery;

    return {
        subtotal,
        discount: wholesaleDiscount,
        delivery,
        vat,
        total,
    };
}

function renderSummary(cart = getCart()) {
    const summary = getSummary(cart);

    if (subtotalElement) {
        subtotalElement.textContent = formatPrice(summary.subtotal);
    }

    if (discountElement) {
        discountElement.textContent = summary.discount > 0 ? `- ${formatPrice(summary.discount)}` : '0 руб.';
    }

    if (deliveryElement) {
        deliveryElement.textContent = summary.delivery > 0 ? formatPrice(summary.delivery) : 'После расчета';
    }

    if (vatElement) {
        vatElement.textContent = formatPrice(summary.vat);
    }

    if (totalElement) {
        totalElement.textContent = formatPrice(summary.total);
    }
}

function renderCart() {
    const cart = getCart();
    window.ditentUpdateCartBadge?.(cart);

    if (!cartList) {
        return;
    }

    cartList.innerHTML = '';

    if (!cart.length) {
        cartList.innerHTML = `
            <div class="card-empty">
                <h3>Корзина пуста</h3>
                <p>Создайте чехол в конструкторе или выберите готовое изделие из каталога.</p>
                <a href="constructor.html">Создать чехол</a>
            </div>
        `;
        checkoutButton?.setAttribute('disabled', 'disabled');
        renderSummary(cart);
        return;
    }

    checkoutButton?.removeAttribute('disabled');
    cart.forEach(item => {
        cartList.append(createCartItem(item));
    });
    renderSummary(cart);
    refreshDeliveryQuote().catch(error => showMessage(error.message));
}

async function changeQuantity(id, direction) {
    const currentItem = getCart().find(item => item.id === id);

    if (!currentItem) {
        return;
    }

    const nextQuantity = Math.max(1, currentItem.quantity + direction);

    if (
        direction > 0
        && currentItem.type === 'catalog-product'
        && currentItem.stock > 0
        && nextQuantity > currentItem.stock
    ) {
        showMessage(`Доступно только ${currentItem.stock} шт.`, 'error');
        return;
    }

    await updateCartItemQuantityOnBackend(id, nextQuantity);
    renderCart();
}

async function removeItem(id) {
    await deleteCartItemOnBackend(id);
    renderCart();
}

async function validateAuth() {
    const status = await loadAuthStatus();
    return Boolean(status.authenticated);
}

function isValidPhone(phone) {
    return window.ditentIsRuPhone
        ? window.ditentIsRuPhone(phone)
        : /^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$/.test(String(phone || '').trim());
}

function isValidEmail(email) {
    const value = String(email || '').trim();
    return /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$/.test(value)
        && value.length <= 254;
}

function isValidPersonName(name) {
    const value = String(name || '').trim();
    return value.length >= 2
        && value.length <= 80
        && /^[A-Za-zА-Яа-яЁё]+(?:[ '-][A-Za-zА-Яа-яЁё]+)*$/.test(value);
}

function validateClient() {
    let isValid = true;
    const fields = {
        lastName: {
            valid: value => isValidPersonName(value),
        },
        firstName: {
            valid: value => isValidPersonName(value),
        },
        phone: {
            valid: value => isValidPhone(value),
        },
        email: {
            valid: value => isValidEmail(value),
        },
    };

    Object.entries(fields).forEach(([field, rule]) => {
        const input = document.querySelector(`[data-client-field="${field}"]`);
        const value = input?.value.trim() || '';

        if (!rule.valid(value)) {
            markField(input);
            isValid = false;
        }
    });

    return isValid;
}

function createOrder() {
    const cart = getCart();
    const summary = getSummary(cart);
    const order = {
        id: `DT-${Date.now()}`,
        status: 'pending-manager-confirmation',
        statusTitle: 'Ожидает подтверждения менеджером',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        items: cart,
        summary,
        auth: getAuthState(),
        client: getClientData(),
        location: getLocationData(),
        delivery: getSelectedDelivery(),
        payment: getSelectedPayment(),
        returnTermsAccepted: Boolean(returnConfirm?.checked),
    };
    const orders = readJson(ORDERS_KEY, []);

    orders.unshift(order);
    writeJson(ORDERS_KEY, orders);
    localStorage.removeItem(CART_KEY);
    window.ditentUpdateCartBadge?.([]);
    window.dispatchEvent(new CustomEvent('ditent:cart-updated', { detail: { items: [] } }));

    return order;
}

async function submitOrderToBackend() {
    const payload = {
        items: getCart(),
        client: getClientData(),
        location: getLocationData(),
        delivery: getSelectedDelivery(),
        payment: getSelectedPayment(),
        auth: getAuthState(),
        returnTermsAccepted: Boolean(returnConfirm?.checked),
    };
    const response = await fetch('checkout/api/orders/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            Accept: 'application/json',
        },
        body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.ok === false) {
        const errors = result.errors && typeof result.errors === 'object'
            ? Object.values(result.errors).flat().join(' ')
            : '';
        throw new Error(result.error || errors || 'Не удалось создать заказ.');
    }

    return result.order;
}

function updateAuthStatus() {
    return getAuthState();
}

cartList?.addEventListener('click', async event => {
    const item = event.target.closest('.card-checked__item');

    if (!item) {
        return;
    }

    const id = item.dataset.cartId;

    if (event.target.closest('[data-remove-item]')) {
        await removeItem(id);
        return;
    }

    if (event.target.closest('[data-qty-minus]')) {
        await changeQuantity(id, -1);
        return;
    }

    if (event.target.closest('[data-qty-plus]')) {
        await changeQuantity(id, 1);
    }
});

document.querySelectorAll('input[name="delivery"]').forEach(input => {
    input.addEventListener('change', () => {
        refreshDeliveryQuote().catch(error => showMessage(error.message));
    });
});

checkoutButton?.addEventListener('click', async () => {
    clearValidation();

    const cart = getCart();

    if (!cart.length) {
        showMessage('Добавьте товар в корзину перед оформлением.');
        return;
    }

    try {
        const authorized = await validateAuth();
        if (!authorized) {
            showMessage('Войдите или зарегистрируйтесь перед оформлением заказа.');
            openCheckoutAuthModal(getClientData());
            return;
        }
    } catch (error) {
        showMessage(error.message);
        return;
    }

    if (!validateClient()) {
        showMessage('Заполните имя, фамилию, телефон и корректный e-mail.');
        return;
    }

    if (getSelectedDelivery().type === 'cdek-point' && !deliveryLocationState.pickupPoint?.code) {
        showMessage('Выберите пункт выдачи СДЭК.');
        return;
    }

    if (!returnConfirm?.checked) {
        showMessage('Подтвердите условия возврата индивидуального изделия.');
        document.querySelector('.card-action label')?.classList.add('card-field--error');
        return;
    }

    checkoutButton.disabled = true;
    let backendOrder;

    try {
        backendOrder = await submitOrderToBackend();
    } catch (error) {
        checkoutButton.disabled = false;
        showMessage(error.message);
        return;
    }

    const order = createOrder();
    order.id = backendOrder.id || order.id;
    order.status = backendOrder.status || order.status;
    order.statusTitle = backendOrder.statusTitle || order.statusTitle;
    order.paymentUrl = backendOrder.paymentUrl || '';
    const savedOrders = readJson(ORDERS_KEY, []);
    if (savedOrders[0]) {
        savedOrders[0] = order;
        writeJson(ORDERS_KEY, savedOrders);
    }

    renderCart();
    checkoutButton.disabled = false;
    showMessage(`Заказ ${order.id} создан. Статус: ${order.statusTitle}.`, 'success');
    sessionStorage.setItem('ditentLastOrder', JSON.stringify(order));
    window.location.href = `order-success.html?order=${encodeURIComponent(order.id)}`;
});

function setLocationLabel(type, text) {
    const select = document.querySelector(`[data-location-select="${type}"]`);
    const label = select?.querySelector('[data-location-label]');

    if (label) {
        label.textContent = text;
    }
}

function clearCitySearch() {
    const search = document.querySelector('[data-location-select="city"] [data-location-search]');

    if (search) {
        search.value = '';
    }
}

function locationDisplayTitle(item) {
    if (!item) {
        return '';
    }

    if (item.subRegion && item.subRegion !== item.title) {
        return `${item.title}, ${item.subRegion}`;
    }

    return item.title || '';
}

function deliveryLocationCacheKey(type, params = {}) {
    const entries = Object.entries(params)
        .filter(([, value]) => value !== undefined && value !== null && value !== '')
        .sort(([left], [right]) => left.localeCompare(right));

    return `${DELIVERY_LOCATION_CACHE_PREFIX}${type}:${JSON.stringify(entries)}`;
}

function readDeliveryLocationCache(key) {
    try {
        const cached = JSON.parse(localStorage.getItem(key) || 'null');

        if (!cached || Date.now() - cached.createdAt > DELIVERY_LOCATION_CACHE_TTL) {
            localStorage.removeItem(key);
            return null;
        }

        return Array.isArray(cached.items) ? cached.items : null;
    } catch {
        localStorage.removeItem(key);
        return null;
    }
}

function writeDeliveryLocationCache(key, items) {
    try {
        localStorage.setItem(key, JSON.stringify({
            createdAt: Date.now(),
            items,
        }));
    } catch {
        // Storage can be unavailable in private mode; network loading still works.
    }
}

async function fetchDeliveryLocations(type, params = {}) {
    const search = new URLSearchParams({ type, ...params });
    const response = await fetch(`checkout/api/delivery/locations/?${search.toString()}`, {
        headers: { Accept: 'application/json' },
    });
    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.ok === false) {
        throw new Error(result.error || 'Не удалось загрузить справочник доставки.');
    }

    return result.items || [];
}

async function loadDeliveryLocations(type, params = {}) {
    const cacheKey = deliveryLocationCacheKey(type, params);
    const cached = readDeliveryLocationCache(cacheKey);

    if (cached) {
        fetchDeliveryLocations(type, params)
            .then(items => {
                if (items.length) {
                    writeDeliveryLocationCache(cacheKey, items);
                } else {
                    localStorage.removeItem(cacheKey);
                }
            })
            .catch(() => {});
        return cached;
    }

    const items = await fetchDeliveryLocations(type, params);
    if (items.length) {
        writeDeliveryLocationCache(cacheKey, items);
    } else {
        localStorage.removeItem(cacheKey);
    }
    return items;
}

function renderLocationItems(type, items, mutedText = 'Ничего не найдено') {
    const select = document.querySelector(`[data-location-select="${type}"]`);
    const list = select?.querySelector('[data-location-list]');

    if (!list) {
        return;
    }

    list.innerHTML = '';

    if (!items.length) {
        const empty = document.createElement('div');
        empty.className = 'card-select__list-item card-select__list-item--muted';
        empty.textContent = mutedText;
        list.append(empty);
        return;
    }

    items.forEach(item => {
        const option = document.createElement('button');
        option.className = 'card-select__list-item';
        option.type = 'button';
        option.textContent = locationDisplayTitle(item);
        option.dataset.code = item.code || '';
        option.addEventListener('click', () => selectDeliveryLocation(type, item));
        list.append(option);
    });
}

function setPickupStatus(text) {
    const status = document.querySelector('[data-pickup-status]');

    if (status) {
        status.textContent = text;
    }
}

async function loadPickupPoints(cityCode) {
    if (!cityCode) {
        return [];
    }

    const cacheKey = `${DELIVERY_LOCATION_CACHE_PREFIX}pickup:${cityCode}`;
    const cached = readDeliveryLocationCache(cacheKey);

    if (cached) {
        return cached;
    }

    const search = new URLSearchParams({ city: cityCode });
    const response = await fetch(`checkout/api/delivery/pickup-points/?${search.toString()}`, {
        headers: { Accept: 'application/json' },
    });
    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.ok === false) {
        throw new Error(result.error || 'Не удалось загрузить пункты выдачи СДЭК.');
    }

    const items = result.items || [];
    if (items.length) {
        writeDeliveryLocationCache(cacheKey, items);
    } else {
        localStorage.removeItem(cacheKey);
    }
    return items;
}

function renderPickupPoints(points) {
    const list = document.querySelector('[data-pickup-list]');

    if (!list) {
        return;
    }

    list.innerHTML = '';
    deliveryLocationState.pickupPoint = null;

    if (!points.length) {
        setPickupStatus('Для выбранного города пункты выдачи не найдены.');
        return;
    }

    setPickupStatus('Выберите удобный пункт выдачи.');
    points.forEach(point => {
        const button = document.createElement('button');
        button.className = 'card-pickup__item';
        button.type = 'button';
        button.innerHTML = `
            <strong>${point.title || point.code}</strong>
            <span>${point.address || ''}</span>
            ${point.workTime ? `<span>${point.workTime}</span>` : ''}
        `;
        button.addEventListener('click', () => selectPickupPoint(point, button));
        list.append(button);
    });
}

function selectPickupPoint(point, element) {
    deliveryLocationState.pickupPoint = point;
    document.querySelectorAll('.card-pickup__item--active').forEach(item => {
        item.classList.remove('card-pickup__item--active');
    });
    element.classList.add('card-pickup__item--active');
    setPickupStatus(point.address || point.title || 'Пункт выдачи выбран.');
    refreshDeliveryQuote().catch(error => showMessage(error.message));
}

async function selectDeliveryLocation(type, item) {
    deliveryLocationState[type] = item;
    setLocationLabel(type, locationDisplayTitle(item));
    document.querySelector(`[data-location-select="${type}"]`)?.classList.remove('open');

    if (type === 'country') {
        deliveryLocationState.region = null;
        deliveryLocationState.city = null;
        deliveryLocationState.pickupPoint = null;
        clearCitySearch();
        setLocationLabel('region', 'Область');
        setLocationLabel('city', 'Населенный пункт');
        renderLocationItems('city', [], 'Начните вводить населенный пункт');
        renderLocationItems('region', [], 'Загружаем области...');
        renderPickupPoints([]);
        setPickupStatus('Выберите населенный пункт, чтобы загрузить ПВЗ.');
        const regions = await loadDeliveryLocations('regions', { country: item.code });
        renderLocationItems('region', regions, 'Для страны нет отдельного списка областей');

        if (!regions.length) {
            const cities = await loadDeliveryLocations('cities', {
                country: item.code,
            });
            renderLocationItems('city', cities, 'Для страны нет пунктов выдачи СДЭК');
        }
    }

    if (type === 'region') {
        deliveryLocationState.city = null;
        deliveryLocationState.pickupPoint = null;
        clearCitySearch();
        setLocationLabel('city', 'Населенный пункт');
        renderLocationItems('city', [], 'Загружаем населенные пункты...');
        renderPickupPoints([]);
        setPickupStatus('Выберите населенный пункт, чтобы загрузить ПВЗ.');
        const cities = await loadDeliveryLocations('cities', {
            country: deliveryLocationState.country?.code || 'RU',
            region: item.code || '',
        });
        renderLocationItems('city', cities, 'В этой области нет пунктов выдачи СДЭК');
    }

    if (type === 'city') {
        if (item.regionCode && item.region && deliveryLocationState.region?.code !== item.regionCode) {
            deliveryLocationState.region = {
                code: item.regionCode,
                title: item.region,
                countryCode: item.countryCode || deliveryLocationState.country?.code || '',
            };
            setLocationLabel('region', item.region);
        }
        deliveryLocationState.pickupPoint = null;
        renderPickupPoints([]);
        setPickupStatus('Загружаем пункты выдачи...');
        try {
            const points = await loadPickupPoints(item.code);
            renderPickupPoints(points);
        } catch (error) {
            renderPickupPoints([]);
            setPickupStatus(error.message);
        }
    }

    refreshDeliveryQuote().catch(error => showMessage(error.message));
}

function debounce(callback, delay = 250) {
    let timer;

    return (...args) => {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => callback(...args), delay);
    };
}

async function initializeDeliveryLocations() {
    const countrySelect = document.querySelector('[data-location-select="country"]');
    const regionSelect = document.querySelector('[data-location-select="region"]');
    const citySelect = document.querySelector('[data-location-select="city"]');
    const citySearch = citySelect?.querySelector('[data-location-search]');

    if (!countrySelect || !regionSelect || !citySelect) {
        return;
    }

    [countrySelect, regionSelect, citySelect].forEach(select => {
        const main = select.querySelector('.card-select__main');
        main?.addEventListener('click', () => {
            document.querySelectorAll('.card-select.open').forEach(opened => {
                if (opened !== select) {
                    opened.classList.remove('open');
                }
            });
            select.classList.toggle('open');
            if (select === citySelect) {
                citySearch?.focus();
            }
        });
    });

    citySearch?.addEventListener('click', event => event.stopPropagation());
    citySearch?.addEventListener('input', debounce(async event => {
        const query = event.target.value.trim();
        const cities = await loadDeliveryLocations('cities', {
            country: deliveryLocationState.country?.code || 'RU',
            region: deliveryLocationState.region?.code || '',
            q: query,
        });
        renderLocationItems('city', cities, query ? 'Ничего не найдено' : 'Начните вводить населенный пункт');
    }));

    try {
        renderLocationItems('country', [], 'Загружаем страны...');
        const countries = await loadDeliveryLocations('countries');
        renderLocationItems('country', countries);
        const defaultCountry = countries.find(item => item.code === 'RU') || countries[0];

        if (defaultCountry) {
            await selectDeliveryLocation('country', defaultCountry);
        }
    } catch (error) {
        showMessage(error.message);
    }
}

const selects = document.querySelectorAll('.card-select:not([data-location-select])');

selects.forEach(select => {
    const main = select.querySelector('.card-select__main');
    const checked = select.querySelector('.card-select__checked');
    const items = select.querySelectorAll('.card-select__list-item');

    main.addEventListener('click', () => {
        select.classList.toggle('open');
    });

    items.forEach(item => {
        item.addEventListener('click', () => {
            checked.textContent = item.textContent;
            select.classList.remove('open');
            refreshDeliveryQuote().catch(error => showMessage(error.message));
        });
    });
});

async function initializeCart() {
    try {
        await loadCartFromBackend();
        await loadAuthStatus();
    } catch (error) {
        showMessage(error.message);
    }

    updateAuthStatus();
    renderCart();
    initializeDeliveryLocations().catch(error => showMessage(error.message));
}

initializeCart();

