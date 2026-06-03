const mobileMenuToggle = document.querySelector('.header-menu');

function mobileMenuCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);

    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }

    return '';
}

async function mobileMenuAuthStatus() {
    try {
        const response = await fetch('/auth/api/status/', {
            headers: { Accept: 'application/json' },
        });

        return response.json().catch(() => ({}));
    } catch {
        return {};
    }
}

async function mobileMenuLogout() {
    await fetch('/auth/api/logout/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': mobileMenuCookie('csrftoken'),
            Accept: 'application/json',
        },
        body: '{}',
    }).catch(() => {});

    localStorage.removeItem('ditentCheckoutAuth');
    window.location.href = 'index.html';
}

function mobileMenuArrowIcon() {
    return `
        <svg width="10" height="10" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path d="M8.41748 3.45917L11.9583 7L8.41748 10.5408" stroke="currentColor" stroke-width="1.2" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2.04163 7H11.8591" stroke="currentColor" stroke-width="1.2" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    `;
}

function mobileMenuCloseIcon() {
    return `
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M5 5L15 15M15 5L5 15" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
    `;
}

function mobileMenuProfileIcon() {
    return `
        <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M3 17C4.1 14.9 6.5 13.6 10 13.6C13.5 13.6 15.9 14.9 17 17M13 6.5C13 8.16 11.66 9.5 10 9.5C8.34 9.5 7 8.16 7 6.5C7 4.84 8.34 3.5 10 3.5C11.66 3.5 13 4.84 13 6.5Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
    `;
}

function mobileMenuBagIcon() {
    return `
        <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M13 7V4.5C13 2.84 11.66 1.5 10 1.5C8.34 1.5 7 2.84 7 4.5V7M4 18.5H16C17.1 18.5 18 17.64 18 16.58L16.75 6.5C16.75 5.44 15.86 4.58 14.75 4.58H5.25C4.14 4.58 3.25 5.44 3.25 6.5L2 16.58C2 17.64 2.9 18.5 4 18.5Z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    `;
}

function mobileMenuLogoutIcon() {
    return `
        <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M12 6V4.5C12 4.1 11.84 3.72 11.56 3.44C11.28 3.16 10.9 3 10.5 3H4.5C4.1 3 3.72 3.16 3.44 3.44C3.16 3.72 3 4.1 3 4.5V15.5C3 15.9 3.16 16.28 3.44 16.56C3.72 16.84 4.1 17 4.5 17H10.5C10.9 17 11.28 16.84 11.56 16.56C11.84 16.28 12 15.9 12 15.5V14M7 10H17M14.5 7.5L17 10L14.5 12.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    `;
}

function createMobileMenu() {
    const root = document.createElement('div');
    root.className = 'mobile-menu-panel';
    root.hidden = true;
    root.setAttribute('data-mobile-menu', '');
    document.body.append(root);
    return root;
}

const mobileMenuPanel = createMobileMenu();

function renderMobileMenu(status = {}) {
    const isAuthenticated = Boolean(status.authenticated);
    const email = status.user?.email || '';

    mobileMenuPanel.classList.toggle('mobile-menu-panel--profile', isAuthenticated);
    mobileMenuPanel.classList.toggle('mobile-menu-panel--guest', !isAuthenticated);

    mobileMenuPanel.innerHTML = `
        <div class="mobile-menu-panel__sheet" role="dialog" aria-modal="true" aria-label="Меню">
            <div class="mobile-menu-panel__head">
                <p>Меню</p>
                <button class="mobile-menu-panel__close" type="button" data-mobile-menu-close aria-label="Закрыть меню">
                    ${mobileMenuCloseIcon()}
                </button>
            </div>
            <button class="mobile-menu-panel__account" type="button" data-mobile-menu-account>
                ${isAuthenticated ? `
                    <span>Подтверждён</span>
                    <b>${email}</b>
                ` : '<b>Войти в личный кабинет</b>'}
            </button>
            <nav class="mobile-menu-panel__nav">
                <a href="about.html">О фабрике</a>
                <a href="catalog.html">Каталог готовых изделий</a>
                <a href="delivery.html">Доставка и оплата</a>
                <a href="review.html">Галерея и отзывы</a>
                <a href="contacts.html">Контакты</a>
            </nav>
            ${isAuthenticated ? `
                <div class="mobile-menu-panel__cabinet">
                    <a href="cabinet.html#profile">${mobileMenuProfileIcon()}<span>Личные данные</span></a>
                    <a href="cabinet.html#orders">${mobileMenuBagIcon()}<span>Мои заказы</span></a>
                </div>
                <button class="mobile-menu-panel__logout" type="button" data-mobile-menu-logout>
                    ${mobileMenuLogoutIcon()}<span>Выйти</span>
                </button>
            ` : ''}
            <a class="mobile-menu-panel__constructor" href="constructor.html">
                Создать чехол ${mobileMenuArrowIcon()}
            </a>
        </div>
    `;
}

function closeMobileMenu() {
    mobileMenuPanel.hidden = true;
    document.body.classList.remove('mobile-menu-open');
}

async function openMobileMenu() {
    renderMobileMenu(await mobileMenuAuthStatus());
    mobileMenuPanel.hidden = false;
    document.body.classList.add('mobile-menu-open');
}

mobileMenuToggle?.setAttribute('role', 'button');
mobileMenuToggle?.setAttribute('tabindex', '0');
mobileMenuToggle?.setAttribute('aria-label', 'Открыть меню');

mobileMenuToggle?.addEventListener('click', openMobileMenu);
mobileMenuToggle?.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openMobileMenu();
    }
});

mobileMenuPanel.addEventListener('click', event => {
    if (event.target.closest('[data-mobile-menu-close]')) {
        closeMobileMenu();
        return;
    }

    if (event.target.closest('[data-mobile-menu-logout]')) {
        mobileMenuLogout();
        return;
    }

    if (event.target.closest('[data-mobile-menu-account]')) {
        closeMobileMenu();
        document.querySelector('.header-actions__link[href="cabinet.html"]')?.click();
        return;
    }

    if (event.target.closest('a')) {
        closeMobileMenu();
    }
});

document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !mobileMenuPanel.hidden) {
        closeMobileMenu();
    }
});
