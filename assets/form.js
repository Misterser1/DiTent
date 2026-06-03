const mainImage = document.getElementById('mainImage');
const galleryItems = document.querySelectorAll('.product-list__item');
const catalogProduct = document.querySelector('[data-catalog-product]');
const addCatalogToCartButton = document.querySelector('[data-add-catalog-to-cart]');
const catalogCartMessage = document.querySelector('[data-catalog-cart-message]');
const CART_KEY = 'ditentCart';

function readJson(key, fallback = []) {
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

async function addCartItemToBackend(item) {
    const response = await fetch('cart/api/items/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            Accept: 'application/json',
        },
        body: JSON.stringify(item),
    });
    const result = await response.json().catch(() => ({}));

    if (!response.ok || result.ok === false) {
        throw new Error(result.error || 'Не удалось добавить товар в корзину.');
    }

    writeJson(CART_KEY, result.cart.items || []);

    return result.cart;
}

function parseDimensions(value = '') {
    return value
        .split(';')
        .map(item => item.trim())
        .filter(Boolean)
        .map(item => {
            const [label = '', rawValue = ''] = item.split(':');
            const [dimensionLabel, dimensionCode = ''] = label.split('|');
            const valueNumber = Number(rawValue.trim());
            const codeMatch = label.match(/\b[A-ZА-Я]\b/u);

            return {
                label: dimensionLabel.trim(),
                code: dimensionCode.trim() || (codeMatch ? codeMatch[0] : ''),
                value: Number.isFinite(valueNumber) ? valueNumber : rawValue.trim(),
            };
        });
}

function getQuantity() {
    const value = document.querySelector('.product-sticky .product-counter__value');
    const quantity = parseInt(value?.textContent || '1', 10);
    const stock = getCatalogStock();

    if (!Number.isFinite(quantity) || quantity < 1) {
        return 1;
    }

    return stock > 0 ? Math.min(quantity, stock) : quantity;
}

function getCatalogStock() {
    const stock = parseInt(catalogProduct?.dataset.productStock || '0', 10);

    return Number.isFinite(stock) ? Math.max(0, stock) : 0;
}

function syncCatalogCounterState(counter) {
    const stock = getCatalogStock();
    const value = counter?.querySelector('.product-counter__value');
    const plusBtn = counter?.querySelector('.product-counter__btn--next');
    const minusBtn = counter?.querySelector('.product-counter__btn--prev');
    const count = parseInt(value?.textContent || '1', 10) || 1;

    if (plusBtn) {
        plusBtn.style.opacity = stock > 0 && count >= stock ? '0.45' : '';
        plusBtn.setAttribute('aria-disabled', stock > 0 && count >= stock ? 'true' : 'false');
    }

    if (minusBtn) {
        minusBtn.style.opacity = count <= 1 ? '0.45' : '';
        minusBtn.setAttribute('aria-disabled', count <= 1 ? 'true' : 'false');
    }

    if (addCatalogToCartButton && stock <= 0) {
        addCatalogToCartButton.disabled = true;
        showCatalogCartMessage('\u0422\u043e\u0432\u0430\u0440 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u043b\u0441\u044f.');
    }
}

function buildCatalogCartItem() {
    if (!catalogProduct) {
        return null;
    }

    const quantity = getQuantity();
    const unitPrice = Number(catalogProduct.dataset.productPrice || 0);
    const sku = catalogProduct.dataset.productSku || `DT-CATALOG-${Date.now()}`;

    return {
        id: `${sku}-${Date.now()}`,
        type: 'catalog-product',
        title: catalogProduct.dataset.productTitle || catalogProduct.querySelector('h1')?.textContent.trim() || 'Готовый чехол',
        sku,
        quantity,
        unitPrice,
        totalPrice: unitPrice * quantity,
        image: catalogProduct.dataset.productImage || document.getElementById('mainImage')?.getAttribute('src') || 'assets/image/card-img-1.png',
        shape: {
            title: catalogProduct.dataset.productShape || 'Готовое изделие из каталога',
            code: 'CATALOG',
        },
        dimensions: parseDimensions(catalogProduct.dataset.productDimensions),
        fabric: {
            name: catalogProduct.dataset.productFabric || '',
            code: 'CAT-FABRIC',
            price: 0,
        },
        color: {
            name: catalogProduct.dataset.productColor || '',
            code: 'CAT-COLOR',
            price: 0,
        },
        fastener: {
            name: catalogProduct.dataset.productFastener || '',
            code: 'CAT-FASTENER',
            price: 0,
        },
        accessory: null,
        comments: 'Готовое изделие из каталога',
    };
}

function showCatalogCartMessage(text) {
    if (!catalogCartMessage) {
        return;
    }

    catalogCartMessage.textContent = text;
}

galleryItems.forEach(item => {
    item.addEventListener('click', () => {
        galleryItems.forEach(el => {
            el.classList.remove('active');
        });

        item.classList.add('active');

        const imgSrc = item.querySelector('img').src;
        mainImage.src = imgSrc;
    });
});

const counters = document.querySelectorAll('.product-counter__wrapper');

counters.forEach(counter => {
    const minusBtn = counter.querySelector('.product-counter__btn--prev');
    const plusBtn = counter.querySelector('.product-counter__btn--next');
    const value = counter.querySelector('.product-counter__value');
    let count = parseInt(value.textContent, 10);

    minusBtn.addEventListener('click', () => {
        if (count > 1) {
            count--;
            value.textContent = count;
        }
        syncCatalogCounterState(counter);
    });

    plusBtn.addEventListener('click', () => {
        const stock = getCatalogStock();
        if (stock > 0 && count >= stock) {
            showCatalogCartMessage(`\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e ${stock} \u0448\u0442.`);
            syncCatalogCounterState(counter);
            return;
        }

        count++;
        value.textContent = count;
        syncCatalogCounterState(counter);
    });

    syncCatalogCounterState(counter);
});

const wrapper = document.querySelector('.useful-wrapper');
const items = document.querySelectorAll('.useful-item');
const btnPrev = document.querySelector('.useful-btn--prev');
const btnNext = document.querySelector('.useful-btn--next');

function getStep() {
    const item = items[0];
    const style = getComputedStyle(wrapper);
    const gap = parseInt(style.columnGap || style.gap || 0, 10);

    return item.offsetWidth + gap;
}

btnNext?.addEventListener('click', () => {
    wrapper.scrollBy({
        left: getStep(),
        behavior: 'smooth',
    });
});

btnPrev?.addEventListener('click', () => {
    wrapper.scrollBy({
        left: -getStep(),
        behavior: 'smooth',
    });
});

addCatalogToCartButton?.addEventListener('click', async () => {
    const cartItem = buildCatalogCartItem();

    if (!cartItem) {
        showCatalogCartMessage('Не удалось подготовить товар для корзины.');
        return;
    }

    addCatalogToCartButton.disabled = true;

    try {
        const cart = await addCartItemToBackend(cartItem);
        window.ditentLastCartItem = cart.items?.[cart.items.length - 1] || cartItem;
        showCatalogCartMessage('Товар добавлен в корзину.');
    } catch (error) {
        showCatalogCartMessage(error.message);
    } finally {
        addCatalogToCartButton.disabled = false;
    }
});
