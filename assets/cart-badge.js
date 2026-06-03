const DITENT_CART_KEY = 'ditentCart';

function ditentCartItemsCount(items) {
    return (Array.isArray(items) ? items : []).reduce((sum, item) => {
        const quantity = Number(item?.quantity || 0);
        return sum + (Number.isFinite(quantity) ? Math.max(0, quantity) : 0);
    }, 0);
}

function ditentStoredCartItems() {
    try {
        return JSON.parse(localStorage.getItem(DITENT_CART_KEY) || '[]');
    } catch {
        return [];
    }
}

function ditentSetCartBadge(count) {
    const normalizedCount = Math.max(0, Number(count) || 0);
    document.querySelectorAll('[data-cart-count]').forEach((badge) => {
        badge.textContent = normalizedCount > 99 ? '99+' : String(normalizedCount);
        badge.classList.toggle('is-visible', normalizedCount > 0);
        const link = badge.closest('a');
        if (link) {
            link.setAttribute('aria-label', normalizedCount > 0 ? `Корзина, товаров: ${normalizedCount}` : 'Корзина');
        }
    });
}

function ditentUpdateCartBadgeFromItems(items) {
    ditentSetCartBadge(ditentCartItemsCount(items));
}

async function ditentRefreshCartBadge() {
    ditentUpdateCartBadgeFromItems(ditentStoredCartItems());

    try {
        const response = await fetch('cart/api/', {
            headers: { Accept: 'application/json' },
        });
        const payload = await response.json().catch(() => ({}));
        if (response.ok && payload.cart?.items) {
            localStorage.setItem(DITENT_CART_KEY, JSON.stringify(payload.cart.items));
            ditentUpdateCartBadgeFromItems(payload.cart.items);
        }
    } catch {
        ditentUpdateCartBadgeFromItems(ditentStoredCartItems());
    }
}

window.ditentUpdateCartBadge = function ditentUpdateCartBadge(cartOrItems) {
    const items = Array.isArray(cartOrItems) ? cartOrItems : cartOrItems?.items;
    ditentUpdateCartBadgeFromItems(items || ditentStoredCartItems());
};

window.addEventListener('storage', (event) => {
    if (event.key === DITENT_CART_KEY) {
        ditentUpdateCartBadgeFromItems(ditentStoredCartItems());
    }
});

window.addEventListener('ditent:cart-updated', (event) => {
    window.ditentUpdateCartBadge(event.detail?.cart || event.detail?.items);
});

document.addEventListener('DOMContentLoaded', ditentRefreshCartBadge);
