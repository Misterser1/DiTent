const authModal = document.querySelector('[data-auth-modal]');
const authLoginForm = document.querySelector('[data-auth-login-form]');
const authRegisterForm = document.querySelector('[data-auth-register-form]');
const authOpenLinks = document.querySelectorAll('.header-actions__link[href="cabinet.html"], [data-auth-open]');

let authMode = 'login';

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);

    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }

    return '';
}

async function authApi(url, payload) {
    const response = await fetch(url, {
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
        const error = new Error(result.error || 'Не удалось выполнить запрос.');
        error.payload = result;
        error.status = response.status;
        throw error;
    }

    return result;
}

async function fetchAuthStatus() {
    const response = await fetch('auth/api/status/', {
        headers: { Accept: 'application/json' },
    });

    return response.json().catch(() => ({}));
}

function activeAuthForm() {
    return authMode === 'register' ? authRegisterForm : authLoginForm;
}

function activeAuthMessage() {
    return document.querySelector(`[data-auth-message="${authMode}"]`);
}

function clearAuthMessages() {
    document.querySelectorAll('[data-auth-message]').forEach(message => {
        message.textContent = '';
        message.className = 'auth-modal__message';
    });
}

function updateAuthModalScale() {
    if (!authModal) {
        return;
    }

    if (window.matchMedia('(max-width: 768px)').matches) {
        authModal.style.setProperty('--auth-modal-scale', '1');
        return;
    }

    const isCodeSent = authModal.classList.contains('auth-modal--code-sent');
    const baseHeight = authMode === 'register' ? (isCodeSent ? 360 : 790) : 335;
    const scaleByHeight = (window.innerHeight - 72) / baseHeight;
    const scaleByWidth = (window.innerWidth - 96) / 660;
    const scale = Math.min(1, scaleByHeight, scaleByWidth);
    authModal.style.setProperty('--auth-modal-scale', Math.max(0.72, scale).toFixed(3));
}

function hideCodeSteps() {
    authModal?.classList.remove('auth-modal--code-sent');

    document.querySelectorAll('[data-auth-code-step]').forEach(step => {
        step.hidden = true;
    });
}

function showCodeStep(mode) {
    const step = document.querySelector(`[data-auth-code-step="${mode}"]`);

    if (!step) {
        return;
    }

    authModal?.classList.add('auth-modal--code-sent');
    step.hidden = false;
    step.querySelector('input[name="code"]')?.focus();
    updateAuthModalScale();
}

function setAuthMode(mode) {
    authMode = mode === 'register' ? 'register' : 'login';

    if (authModal) {
        authModal.classList.toggle('auth-modal--register', authMode === 'register');
        authModal.classList.toggle('auth-modal--login', authMode === 'login');
        authModal.querySelector('[role="dialog"]')?.setAttribute(
            'aria-labelledby',
            authMode === 'register' ? 'auth-modal-register-title' : 'auth-modal-title'
        );
    }

    if (authLoginForm) {
        authLoginForm.hidden = authMode !== 'login';
    }

    if (authRegisterForm) {
        authRegisterForm.hidden = authMode !== 'register';
    }

    clearAuthMessages();
    hideCodeSteps();
    updateAuthModalScale();

    const focusSelector = authMode === 'register' ? 'input[name="lastName"]' : 'input[name="email"]';
    activeAuthForm()?.querySelector(focusSelector)?.focus();
}

async function openAuthModal(event) {
    event?.preventDefault();

    if (!authModal) {
        window.location.href = 'cabinet.html';
        return;
    }

    try {
        const status = await fetchAuthStatus();

        if (status.authenticated) {
            if (status.user?.email) {
                localStorage.setItem('ditentCheckoutAuth', JSON.stringify({
                    mode: 'session',
                    email: status.user.email,
                    authorizedAt: new Date().toISOString(),
                }));
            }

            window.location.href = 'cabinet.html';
            return;
        }
    } catch {
        localStorage.removeItem('ditentCheckoutAuth');
    }

    const requestedMode = event?.currentTarget?.dataset.authOpen || 'login';
    setAuthMode(requestedMode);
    authModal.hidden = false;
    document.body.classList.add('auth-modal-open');
}

function closeAuthModal() {
    if (!authModal) {
        return;
    }

    authModal.hidden = true;
    document.body.classList.remove('auth-modal-open');
}

function showAuthMessage(text, type = 'error') {
    const authMessage = activeAuthMessage();

    if (!authMessage) {
        return;
    }

    authMessage.textContent = text;
    authMessage.className = `auth-modal__message auth-modal__message--${type}`;
}

function isValidPhone(phone) {
    const value = String(phone || '').trim();

    if (!value) {
        return false;
    }

    if (/[^0-9\s()+.-]/.test(value)) {
        return false;
    }

    if ((value.match(/\+/g) || []).length > 1 || (value.includes('+') && !value.startsWith('+'))) {
        return false;
    }

    const digits = value.replace(/\D/g, '');
    return digits.length >= 10 && digits.length <= 15;
}

function isValidEmail(email) {
    const value = String(email || '').trim();
    return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value) && value.length <= 254;
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

function formatWaitTime(seconds) {
    const totalSeconds = Math.max(1, Number(seconds) || 1);
    const minutes = Math.floor(totalSeconds / 60);
    const restSeconds = totalSeconds % 60;

    if (!minutes) {
        return `${restSeconds} сек.`;
    }

    return restSeconds ? `${minutes} мин. ${restSeconds} сек.` : `${minutes} мин.`;
}

function authPayloadFromForm(form, purpose) {
    const formData = new FormData(form);
    const payload = {
        purpose,
        email: String(formData.get('email') || '').trim(),
        agreement: Boolean(formData.get('agreement')),
    };

    if (purpose === 'register') {
        payload.firstName = String(formData.get('firstName') || '').trim();
        payload.lastName = String(formData.get('lastName') || '').trim();
        payload.middleName = String(formData.get('middleName') || '').trim();
        payload.phone = String(formData.get('phone') || '').trim();
        payload.customerType = String(formData.get('authCustomerType') || '').trim();
    }

    return payload;
}

async function requestAuthCode(form, purpose) {
    const payload = authPayloadFromForm(form, purpose);

    if (!isValidEmail(payload.email)) {
        showAuthMessage('Введите корректный e-mail.');
        form.querySelector('input[name="email"]')?.focus();
        return;
    }

    if (purpose === 'register' && !isValidPersonName(payload.lastName)) {
        showAuthMessage('Введите корректную фамилию.');
        form.querySelector('input[name="lastName"]')?.focus();
        return;
    }

    if (purpose === 'register' && !isValidPersonName(payload.firstName)) {
        showAuthMessage('Введите корректное имя.');
        form.querySelector('input[name="firstName"]')?.focus();
        return;
    }

    if (purpose === 'register' && !isValidPersonName(payload.middleName, false)) {
        showAuthMessage('Введите корректное отчество.');
        form.querySelector('input[name="middleName"]')?.focus();
        return;
    }

    if (purpose === 'register' && !isValidPhone(payload.phone)) {
        showAuthMessage('Введите корректный номер телефона.');
        form.querySelector('input[name="phone"]')?.focus();
        return;
    }

    if (!payload.agreement) {
        showAuthMessage('Подтвердите согласие на обработку данных.');
        return;
    }

    try {
        const result = await authApi('auth/api/code/request/', payload);
        showCodeStep(purpose);
        const debugText = result.debugCode ? ` Код для локальной проверки: ${result.debugCode}` : '';
        showAuthMessage(`${result.message || 'Код отправлен на e-mail.'}${debugText}`, 'success');
    } catch (error) {
        if (error.status === 429 && error.payload?.retryAfterSeconds) {
            showAuthMessage(`Код уже отправлен. Новый код можно запросить через ${formatWaitTime(error.payload.retryAfterSeconds)}.`);
            return;
        }

        showAuthMessage(error.message);
    }
}

async function verifyAuthCode(purpose) {
    authMode = purpose;
    const form = activeAuthForm();
    const email = String(new FormData(form).get('email') || '').trim();
    const code = String(form.querySelector(`[data-auth-code-step="${purpose}"] input[name="code"]`)?.value || '').trim();

    if (!isValidEmail(email) || code.length !== 6) {
        showAuthMessage('Введите e-mail и 6-значный код.');
        return;
    }

    try {
        const result = await authApi('auth/api/code/verify/', { purpose, email, code });
        localStorage.setItem('ditentCheckoutAuth', JSON.stringify({
            mode: purpose,
            email: result.user?.email || email,
            authorizedAt: new Date().toISOString(),
        }));
        window.dispatchEvent(new CustomEvent('ditent:auth-changed', {
            detail: { user: result.user || null },
        }));

        if (window.location.pathname.endsWith('/card.html')) {
            showAuthMessage('Вход выполнен. Данные подставлены в заказ.', 'success');
            setTimeout(closeAuthModal, 500);
            return;
        }

        showAuthMessage('Вход выполнен. Открываем личный кабинет.', 'success');
        setTimeout(() => {
            window.location.href = 'cabinet.html';
        }, 500);
    } catch (error) {
        showAuthMessage(error.message);
    }
}

authOpenLinks.forEach(link => {
    link.addEventListener('click', openAuthModal);
});

document.querySelectorAll('[data-auth-close]').forEach(button => {
    button.addEventListener('click', closeAuthModal);
});

document.querySelectorAll('[data-auth-mode-switch]').forEach(button => {
    button.addEventListener('click', () => {
        setAuthMode(button.dataset.authModeSwitch);
    });
});

document.querySelectorAll('[data-auth-code-verify]').forEach(button => {
    button.addEventListener('click', () => {
        verifyAuthCode(button.dataset.authCodeVerify);
    });
});

document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && authModal && !authModal.hidden) {
        closeAuthModal();
    }
});

window.addEventListener('resize', () => {
    if (authModal && !authModal.hidden) {
        updateAuthModalScale();
    }
});

authLoginForm?.addEventListener('submit', event => {
    event.preventDefault();
    setAuthMode('login');
    requestAuthCode(authLoginForm, 'login');
});

authRegisterForm?.addEventListener('submit', event => {
    event.preventDefault();
    setAuthMode('register');
    requestAuthCode(authRegisterForm, 'register');
});
