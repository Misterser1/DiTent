const drawingForm = document.querySelector('[data-drawing-form]');
const drawingInput = document.querySelector('[data-drawing-file]');
const drawingDropzone = document.querySelector('[data-drawing-dropzone]');
const drawingFileTitle = document.querySelector('[data-drawing-file-title]');
const drawingMessage = document.querySelector('[data-drawing-message]');

const DRAWING_REQUESTS_KEY = 'ditentDrawingRequests';
const MAX_FILE_SIZE = 20 * 1024 * 1024;
const ALLOWED_FILE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.pdf', '.heic', '.heif'];
const phoneInput = drawingForm?.querySelector('input[name="phone"]');
const clientNameInput = drawingForm?.querySelector('input[name="clientName"]');
const emailInput = drawingForm?.querySelector('input[name="email"]');
const clientTypeSelect = drawingForm?.querySelector('[data-client-type-select]');
const clientTypeInput = drawingForm?.querySelector('[data-client-type-input]');
const clientTypeButton = drawingForm?.querySelector('[data-client-type-button]');
const requisitesFields = drawingForm?.querySelector('[data-requisites-fields]');
const companyLegalFormSelect = drawingForm?.querySelector('[data-company-legal-form-select]');
const companyLegalFormInput = drawingForm?.querySelector('[data-company-legal-form-input]');
const companyLegalFormButton = drawingForm?.querySelector('[data-company-legal-form-button]');
const companyNameInput = drawingForm?.querySelector('[name="companyName"]');
const innInput = drawingForm?.querySelector('[name="inn"]');
const kppInput = drawingForm?.querySelector('[name="kpp"]');
const ogrnInput = drawingForm?.querySelector('[name="ogrn"]');
const legalAddressInput = drawingForm?.querySelector('[name="legalAddress"]');
const settlementAccountInput = drawingForm?.querySelector('[name="settlementAccount"]');
const bankInput = drawingForm?.querySelector('[name="bank"]');
const itemNameInput = drawingForm?.querySelector('input[name="itemName"]');
const dimensionsInput = drawingForm?.querySelector('input[name="dimensions"]');
const commentInput = drawingForm?.querySelector('textarea[name="comment"]');

const clientTypeLabels = {
    individual: 'Физическое лицо',
    entrepreneur: 'ИП',
    company: 'Юридическое лицо',
};

const companyLegalFormLabels = {
    '': 'Выберите форму',
    'ИП': 'ИП',
    'ООО': 'ООО',
    'АО': 'АО',
    'ПАО': 'ПАО',
    'НКО': 'НКО',
    'Другое': 'Другое',
};

function getCookie(name) {
    return document.cookie
        .split('; ')
        .find(row => row.startsWith(`${name}=`))
        ?.split('=')[1] || '';
}

function readJson(key, fallback = []) {
    try {
        return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
    } catch {
        return fallback;
    }
}

function writeJson(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
}

function setFieldValueIfEmpty(field, value) {
    if (field && value && !field.value.trim()) {
        field.value = value;
    }
}

function setFieldValue(field, value) {
    if (field && value) {
        field.value = value;
    }
}

function drawingClientTypeFromProfile(type) {
    if (type === 'company' || type === 'entrepreneur') {
        return type;
    }

    return 'individual';
}

function setClientType(value) {
    const normalized = clientTypeLabels[value] ? value : 'individual';

    if (clientTypeInput) {
        clientTypeInput.value = normalized;
    }

    if (clientTypeButton) {
        clientTypeButton.textContent = clientTypeLabels[normalized];
    }

    updateRequisitesVisibility(normalized);
}

function setCompanyLegalForm(value) {
    const normalized = Object.prototype.hasOwnProperty.call(companyLegalFormLabels, value) ? value : '';

    if (companyLegalFormInput) {
        companyLegalFormInput.value = normalized;
        companyLegalFormInput.setCustomValidity('');
    }

    if (companyLegalFormButton) {
        companyLegalFormButton.textContent = companyLegalFormLabels[normalized];
        companyLegalFormButton.classList.toggle('is-placeholder', !normalized);
    }
}

function isBusinessClientType(value = clientTypeInput?.value) {
    return value === 'entrepreneur' || value === 'company';
}

function updateRequisitesVisibility(value = clientTypeInput?.value) {
    const isBusiness = isBusinessClientType(value);

    if (requisitesFields) {
        requisitesFields.hidden = !isBusiness;
    }

    if (companyLegalFormInput && value === 'entrepreneur') {
        setCompanyLegalForm('ИП');
    } else if (companyLegalFormInput && companyLegalFormInput.value === 'ИП' && value === 'company') {
        setCompanyLegalForm('');
    }

    [companyLegalFormInput, companyNameInput, innInput, ogrnInput, legalAddressInput, settlementAccountInput, bankInput].forEach(field => {
        if (field) {
            field.required = isBusiness;
        }
    });

    if (kppInput) {
        kppInput.required = value === 'company';
        kppInput.closest('label')?.classList.toggle('is-optional', value === 'entrepreneur');
    }
}

function fullNameFromUser(user) {
    return [user.lastName, user.firstName, user.middleName]
        .map(part => String(part || '').trim())
        .filter(Boolean)
        .join(' ');
}

function splitClientName(value) {
    const parts = String(value || '').trim().split(/\s+/).filter(Boolean);

    return {
        lastName: parts[0] || '',
        firstName: parts[1] || '',
        middleName: parts.slice(2).join(' '),
    };
}

function fillContactsFromUser(user) {
    if (!user) {
        return;
    }

    setFieldValueIfEmpty(clientNameInput, fullNameFromUser(user) || user.email || '');
    setFieldValueIfEmpty(phoneInput, user.phone || '');
    setFieldValueIfEmpty(emailInput, user.email || '');
    if (companyLegalFormInput && user.companyLegalForm && !companyLegalFormInput.value.trim()) {
        setCompanyLegalForm(user.companyLegalForm);
    }
    setFieldValueIfEmpty(companyNameInput, user.companyName || '');
    setFieldValueIfEmpty(innInput, user.inn || '');
    setFieldValueIfEmpty(kppInput, user.kpp || '');
    setFieldValueIfEmpty(ogrnInput, user.ogrn || '');
    setFieldValueIfEmpty(legalAddressInput, user.legalAddress || '');
    setFieldValueIfEmpty(settlementAccountInput, user.settlementAccount || '');
    setFieldValueIfEmpty(bankInput, user.bank || '');

    if (clientTypeSelect && !clientTypeSelect.dataset.userChanged) {
        setClientType(drawingClientTypeFromProfile(user.type));
    }
}

async function loadAuthProfile() {
    try {
        const response = await fetch('auth/api/status/', {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });
        const result = await response.json().catch(() => ({}));

        if (response.ok && result.authenticated && result.user) {
            fillContactsFromUser(result.user);
        }
    } catch {
        // Prefill is optional; the form remains usable without it.
    }
}

function authCustomerTypeLabel(value) {
    return {
        individual: 'Физическое лицо',
        entrepreneur: 'ИП',
        company: 'Юридическое лицо',
    }[value] || 'Физическое лицо';
}

function openDrawingAuthModal(formData) {
    const modal = document.querySelector('[data-auth-modal]');
    const loginForm = document.querySelector('[data-auth-login-form]');
    const registerForm = document.querySelector('[data-auth-register-form]');
    const loginMessage = document.querySelector('[data-auth-message="login"]');
    const clientName = splitClientName(formData.get('clientName'));
    const email = String(formData.get('email') || '').trim();
    const phone = String(formData.get('phone') || '').trim();
    const clientType = String(formData.get('clientType') || 'individual').trim();

    if (!modal || !loginForm || !registerForm) {
        setMessage('Для отправки заявки нужно войти или зарегистрироваться.', 'error');
        return;
    }

    setFieldValue(loginForm.querySelector('input[name="email"]'), email);
    setFieldValue(registerForm.querySelector('input[name="email"]'), email);
    setFieldValue(registerForm.querySelector('input[name="lastName"]'), clientName.lastName);
    setFieldValue(registerForm.querySelector('input[name="firstName"]'), clientName.firstName);
    setFieldValue(registerForm.querySelector('input[name="middleName"]'), clientName.middleName);
    setFieldValue(registerForm.querySelector('input[name="phone"]'), phone);
    setFieldValue(registerForm.querySelector('[name="companyLegalForm"]'), formData.get('companyLegalForm') || '');
    setFieldValue(registerForm.querySelector('input[name="companyName"]'), formData.get('companyName') || '');
    setFieldValue(registerForm.querySelector('input[name="inn"]'), formData.get('inn') || '');
    setFieldValue(registerForm.querySelector('input[name="kpp"]'), formData.get('kpp') || '');
    setFieldValue(registerForm.querySelector('input[name="ogrn"]'), formData.get('ogrn') || '');
    setFieldValue(registerForm.querySelector('input[name="legalAddress"]'), formData.get('legalAddress') || '');
    setFieldValue(registerForm.querySelector('input[name="settlementAccount"]'), formData.get('settlementAccount') || '');
    setFieldValue(registerForm.querySelector('input[name="bank"]'), formData.get('bank') || '');

    const typeInput = Array.from(registerForm.querySelectorAll('input[name="authCustomerType"]'))
        .find(input => input.value === authCustomerTypeLabel(clientType));
    if (typeInput) {
        typeInput.checked = true;
        typeInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    modal.hidden = false;
    modal.classList.add('auth-modal--login');
    modal.classList.remove('auth-modal--register', 'auth-modal--code-sent');
    modal.querySelector('[role="dialog"]')?.setAttribute('aria-labelledby', 'auth-modal-title');
    document.querySelectorAll('[data-auth-code-step]').forEach(step => {
        step.hidden = true;
    });
    loginForm.hidden = false;
    registerForm.hidden = true;
    document.body.classList.add('auth-modal-open');

    if (loginMessage) {
        loginMessage.textContent = 'Войдите по e-mail или зарегистрируйтесь. Данные из заявки уже подставлены.';
        loginMessage.className = 'auth-modal__message auth-modal__message--error';
    }

    loginForm.querySelector('input[name="email"]')?.focus();
}

function formatFileSize(size) {
    if (size >= 1024 * 1024) {
        return `${(size / 1024 / 1024).toFixed(1)} МБ`;
    }

    return `${Math.max(1, Math.round(size / 1024))} КБ`;
}

function setMessage(text, type = '') {
    if (!drawingMessage) {
        return;
    }

    drawingMessage.textContent = text;
    drawingMessage.classList.toggle('drawing-order__message--success', type === 'success');
    drawingMessage.classList.toggle('drawing-order__message--error', type === 'error');
}

function setSelectedFile(file) {
    if (!file || !drawingFileTitle || !drawingDropzone) {
        return;
    }

    drawingFileTitle.textContent = `${file.name} · ${formatFileSize(file.size)}`;
    drawingDropzone.classList.add('drawing-upload--selected');
    setMessage('');
}

function validateFile(file) {
    if (!file) {
        return 'Загрузите чертеж, эскиз или фото изделия.';
    }

    const fileName = String(file.name || '').toLowerCase();
    const hasAllowedExtension = ALLOWED_FILE_EXTENSIONS.some(extension => fileName.endsWith(extension));

    if (!hasAllowedExtension) {
        return 'Загрузите файл в формате PDF, JPG, PNG, WEBP или HEIC.';
    }

    if (file.size > MAX_FILE_SIZE) {
        return 'Файл слишком большой. Максимальный размер - 20 МБ.';
    }

    return '';
}

function normalizePhone(value) {
    return window.ditentFormatRuPhone
        ? window.ditentFormatRuPhone(value)
        : String(value || '').replace(/[^0-9\s()+.-]/g, '');
}

function onlyDigits(value) {
    return String(value || '').replace(/\D/g, '');
}

function isValidPhone(phone) {
    return window.ditentIsRuPhone
        ? window.ditentIsRuPhone(phone)
        : /^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$/.test(String(phone || '').trim());
}

function validateRequisites() {
    const clientType = clientTypeInput?.value || 'individual';

    if (!isBusinessClientType(clientType)) {
        return true;
    }

    const isCompany = clientType === 'company';
    const legalForm = companyLegalFormInput?.value.trim() || '';
    const companyName = companyNameInput?.value.trim() || '';
    const inn = onlyDigits(innInput?.value);
    const kpp = onlyDigits(kppInput?.value);
    const ogrn = onlyDigits(ogrnInput?.value);
    const legalAddress = legalAddressInput?.value.trim() || '';
    const settlementAccount = onlyDigits(settlementAccountInput?.value);
    const bank = bankInput?.value.trim() || '';

    if (!legalForm) {
        return setFieldValidity(companyLegalFormInput, 'Выберите форму юр. лица.');
    }
    setFieldValidity(companyLegalFormInput, '');

    if (!companyName || companyName.length < 2) {
        return setFieldValidity(companyNameInput, 'Введите название компании.');
    }
    setFieldValidity(companyNameInput, '');

    if (!((isCompany && inn.length === 10) || (!isCompany && inn.length === 12))) {
        return setFieldValidity(innInput, 'Введите корректный ИНН.');
    }
    setFieldValidity(innInput, '');

    if ((isCompany && kpp.length !== 9) || (!isCompany && kpp && kpp.length !== 9)) {
        return setFieldValidity(kppInput, isCompany ? 'Введите корректный КПП.' : 'Введите корректный КПП или оставьте поле пустым.');
    }
    setFieldValidity(kppInput, '');

    if (!((isCompany && ogrn.length === 13) || (!isCompany && ogrn.length === 15))) {
        return setFieldValidity(ogrnInput, 'Введите корректный ОГРН или ОГРНИП.');
    }
    setFieldValidity(ogrnInput, '');

    if (!legalAddress || legalAddress.length < 5) {
        return setFieldValidity(legalAddressInput, 'Введите юридический адрес.');
    }
    setFieldValidity(legalAddressInput, '');

    if (settlementAccount.length !== 20) {
        return setFieldValidity(settlementAccountInput, 'Введите 20 цифр расчетного счета.');
    }
    setFieldValidity(settlementAccountInput, '');

    if (!bank || bank.length < 2) {
        return setFieldValidity(bankInput, 'Введите банк.');
    }
    setFieldValidity(bankInput, '');

    return true;
}

function hasMeaningfulText(value) {
    return [...String(value || '')].some(char => /[\p{L}\p{N}]/u.test(char));
}

function isValidDimensions(value) {
    const text = String(value || '').trim();

    if (!text) {
        return true;
    }

    return text.length <= 180
        && /\d/.test(text)
        && /^[0-9A-Za-zА-Яа-яЁё\s.,:;xхХ*×/\\()\-+]+$/.test(text);
}

function setFieldValidity(field, message) {
    if (!field) {
        return !message;
    }

    field.setCustomValidity(message || '');

    if (message) {
        field.reportValidity();
        setMessage(message, 'error');
        return false;
    }

    return true;
}

function validateDrawingForm() {
    const clientName = clientNameInput?.value.trim() || '';
    const phone = phoneInput?.value.trim() || '';
    const itemName = itemNameInput?.value.trim() || '';
    const dimensions = dimensionsInput?.value.trim() || '';
    const comment = commentInput?.value.trim() || '';

    if (!clientName || clientName.length < 2 || !hasMeaningfulText(clientName)) {
        return setFieldValidity(clientNameInput, 'Введите имя или название компании.');
    }

    setFieldValidity(clientNameInput, '');

    if (!phone) {
        phoneInput?.setCustomValidity('');
    } else if (!isValidPhone(phone)) {
        return setFieldValidity(phoneInput, 'Введите корректный номер телефона.');
    }

    setFieldValidity(phoneInput, '');

    if (itemName && !hasMeaningfulText(itemName)) {
        return setFieldValidity(itemNameInput, 'Укажите корректное название изделия.');
    }

    setFieldValidity(itemNameInput, '');

    if (!isValidDimensions(dimensions)) {
        return setFieldValidity(dimensionsInput, 'Укажите размеры в понятном формате, например: 300 x 100 x 75 см.');
    }

    setFieldValidity(dimensionsInput, '');

    if (comment.length > 2000) {
        return setFieldValidity(commentInput, 'Комментарий должен быть не длиннее 2000 символов.');
    }

    setFieldValidity(commentInput, '');
    if (!validateRequisites()) {
        return false;
    }

    return true;
}

drawingInput?.addEventListener('change', () => {
    const file = drawingInput.files?.[0];
    const error = validateFile(file);

    if (error) {
        setMessage(error, 'error');
        return;
    }

    setSelectedFile(file);
});

phoneInput?.addEventListener('input', () => {
    const normalized = normalizePhone(phoneInput.value);

    if (phoneInput.value !== normalized) {
        phoneInput.value = normalized;
    }

    phoneInput.setCustomValidity(isValidPhone(phoneInput.value) || !phoneInput.value.trim()
        ? ''
        : 'Введите корректный номер телефона.');
});

[clientNameInput, itemNameInput, dimensionsInput, commentInput].forEach(field => {
    field?.addEventListener('input', () => {
        field.setCustomValidity('');
    });
});

[innInput, kppInput, ogrnInput, settlementAccountInput].forEach(field => {
    field?.addEventListener('input', () => {
        field.value = onlyDigits(field.value);
        field.setCustomValidity('');
    });
});

[companyLegalFormInput, companyNameInput, legalAddressInput, bankInput].forEach(field => {
    field?.addEventListener('input', () => {
        field.setCustomValidity('');
    });
});

clientTypeSelect?.addEventListener('change', () => {
    clientTypeSelect.dataset.userChanged = 'true';
});

clientTypeButton?.addEventListener('click', event => {
    event.stopPropagation();
    companyLegalFormSelect?.classList.remove('open');
    clientTypeSelect?.classList.toggle('open');
});

clientTypeSelect?.querySelectorAll('[data-client-type-option]').forEach(option => {
    option.addEventListener('click', event => {
        event.stopPropagation();
        setClientType(option.value);
        clientTypeSelect.dataset.userChanged = 'true';
        clientTypeSelect.classList.remove('open');
    });
});

companyLegalFormButton?.addEventListener('click', event => {
    event.stopPropagation();
    clientTypeSelect?.classList.remove('open');
    companyLegalFormSelect?.classList.toggle('open');
});

companyLegalFormSelect?.querySelectorAll('[data-company-legal-form-option]').forEach(option => {
    option.addEventListener('click', event => {
        event.stopPropagation();
        setCompanyLegalForm(option.value);
        companyLegalFormSelect.classList.remove('open');
    });
});

setCompanyLegalForm(companyLegalFormInput?.value || '');
updateRequisitesVisibility();

document.addEventListener('click', () => {
    clientTypeSelect?.classList.remove('open');
    companyLegalFormSelect?.classList.remove('open');
});

['dragenter', 'dragover'].forEach(eventName => {
    drawingDropzone?.addEventListener(eventName, event => {
        event.preventDefault();
        drawingDropzone.classList.add('drawing-upload--dragover');
    });
});

['dragleave', 'drop'].forEach(eventName => {
    drawingDropzone?.addEventListener(eventName, event => {
        event.preventDefault();
        drawingDropzone.classList.remove('drawing-upload--dragover');
    });
});

drawingDropzone?.addEventListener('drop', event => {
    const file = event.dataTransfer?.files?.[0];
    const error = validateFile(file);

    if (error) {
        setMessage(error, 'error');
        return;
    }

    const transfer = new DataTransfer();
    transfer.items.add(file);
    drawingInput.files = transfer.files;
    setSelectedFile(file);
});

drawingForm?.addEventListener('submit', async event => {
    event.preventDefault();

    const file = drawingInput?.files?.[0];
    const fileError = validateFile(file);

    if (fileError) {
        setMessage(fileError, 'error');
        return;
    }

    if (!validateDrawingForm()) {
        return;
    }

    if (!drawingForm.checkValidity()) {
        drawingForm.reportValidity();
        setMessage('Заполните обязательные поля и подтвердите согласие.', 'error');
        return;
    }

    const formData = new FormData(drawingForm);
    let data;

    try {
        const response = await fetch(drawingForm.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: formData,
            credentials: 'same-origin',
        });

        data = await response.json();

        if (!response.ok || !data.ok) {
            if (response.status === 401) {
                openDrawingAuthModal(formData);
                return;
            }

            const errors = data.errors ? Object.values(data.errors).flat().join(' ') : data.error;
            throw new Error(errors || 'Не удалось отправить заявку.');
        }
    } catch (error) {
        setMessage(error.message || 'Не удалось отправить заявку.', 'error');
        return;
    }

    const request = {
        id: data.request.id,
        source: 'drawing-order',
        status: data.request.status,
        statusTitle: data.request.statusTitle,
        createdAt: new Date().toISOString(),
        client: {
            name: formData.get('clientName') || '',
            phone: formData.get('phone') || '',
            email: formData.get('email') || '',
            type: formData.get('clientType') || 'individual',
            companyLegalForm: formData.get('companyLegalForm') || '',
            companyName: formData.get('companyName') || '',
            inn: formData.get('inn') || '',
            kpp: formData.get('kpp') || '',
            ogrn: formData.get('ogrn') || '',
            legalAddress: formData.get('legalAddress') || '',
            settlementAccount: formData.get('settlementAccount') || '',
            bank: formData.get('bank') || '',
        },
        product: {
            itemName: formData.get('itemName') || '',
            dimensions: formData.get('dimensions') || '',
            comment: formData.get('comment') || '',
        },
        files: [{
            name: file.name,
            size: file.size,
            type: file.type,
        }],
    };

    const requests = readJson(DRAWING_REQUESTS_KEY, []);
    requests.unshift(request);
    writeJson(DRAWING_REQUESTS_KEY, requests);

    drawingForm.reset();
    setClientType('individual');
    if (clientTypeSelect) {
        delete clientTypeSelect.dataset.userChanged;
    }
    drawingDropzone?.classList.remove('drawing-upload--selected');
    if (drawingFileTitle) {
        drawingFileTitle.textContent = 'Нажмите на блок, чтобы выбрать файл';
    }

    setMessage(`Заявка ${request.id} отправлена на расчет менеджеру.`, 'success');
});

loadAuthProfile();
