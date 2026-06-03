(function () {
    const EMAIL_SAFE_CHARS = /[^A-Za-z0-9.!#$%&'*+/=?^_`{|}~@-]/g;
    const PHONE_SAFE_CHARS = /[^0-9\s()+.-]/g;
    const INTEGER_FIELD_NAMES = new Set([
        'code',
        'inn',
        'kpp',
        'ogrn',
        'settlementAccount',
        'settlement_account',
    ]);
    const INTEGER_SIZE_FIELD_NAMES = new Set([
        'width_cm',
        'depth_cm',
        'height_cm',
        'roll_width_cm',
        'min_size_cm',
        'max_size_cm',
    ]);

    function isEmailField(input) {
        const name = String(input.name || '').toLowerCase();
        const field = String(input.dataset.clientField || input.dataset.profileField || '').toLowerCase();

        return input.type === 'email' || name === 'email' || field === 'email';
    }

    function isPhoneField(input) {
        const name = String(input.name || '').toLowerCase();
        const field = String(input.dataset.clientField || input.dataset.profileField || '').toLowerCase();

        if (name === 'phone_href') {
            return false;
        }

        return input.type === 'tel' || name.includes('phone') || field === 'phone';
    }

    function isIntegerField(input) {
        const name = input.name || '';
        const field = input.dataset.clientField || input.dataset.profileField || input.dataset.key || '';

        return input.hasAttribute('data-size-input')
            || input.inputMode === 'numeric'
            || INTEGER_FIELD_NAMES.has(name)
            || INTEGER_FIELD_NAMES.has(field)
            || INTEGER_SIZE_FIELD_NAMES.has(name);
    }

    function isDecimalNumberField(input) {
        return input.type === 'number' && !isIntegerField(input);
    }

    function sanitizeDecimal(value, allowNegative) {
        let next = String(value || '').replace(allowNegative ? /[^0-9.,-]/g : /[^0-9.,]/g, '');
        const firstSeparator = next.search(/[.,]/);

        if (firstSeparator !== -1) {
            next = next.slice(0, firstSeparator + 1)
                + next.slice(firstSeparator + 1).replace(/[.,]/g, '');
        }

        if (allowNegative) {
            next = next.replace(/(?!^)-/g, '');
        }

        return next;
    }

    function phoneDigits(value) {
        let digits = String(value || '').replace(/\D/g, '');

        if (!digits) {
            return '';
        }

        if (digits.startsWith('8')) {
            digits = `7${digits.slice(1)}`;
        } else if (!digits.startsWith('7')) {
            digits = `7${digits}`;
        }

        return digits.slice(0, 11);
    }

    function formatRuPhone(value) {
        const digits = phoneDigits(value);

        if (!digits) {
            return '';
        }

        const local = digits.slice(1);
        let result = '+7';

        if (local.length > 0) {
            result += ` (${local.slice(0, 3)}`;
        }
        if (local.length >= 3) {
            result += ')';
        }
        if (local.length > 3) {
            result += ` ${local.slice(3, 6)}`;
        }
        if (local.length > 6) {
            result += `-${local.slice(6, 8)}`;
        }
        if (local.length > 8) {
            result += `-${local.slice(8, 10)}`;
        }

        return result;
    }

    function isRuPhone(value) {
        return /^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$/.test(String(value || '').trim());
    }

    function sanitizeValue(input, value) {
        if (isEmailField(input)) {
            return String(value || '').replace(EMAIL_SAFE_CHARS, '').toLowerCase();
        }

        if (isPhoneField(input)) {
            return formatRuPhone(String(value || '').replace(PHONE_SAFE_CHARS, ''));
        }

        if (isIntegerField(input)) {
            return String(value || '').replace(/\D/g, '');
        }

        if (isDecimalNumberField(input)) {
            const allowNegative = input.min === '' || Number(input.min) < 0;
            return sanitizeDecimal(value, allowNegative);
        }

        return value;
    }

    function sanitizeInput(input) {
        const value = input.value;
        const sanitized = sanitizeValue(input, value);

        if (sanitized !== value) {
            const cursor = input.selectionStart;
            input.value = sanitized;

            if (isPhoneField(input) && input.setSelectionRange) {
                input.setSelectionRange(sanitized.length, sanitized.length);
            } else if (typeof cursor === 'number' && input.setSelectionRange) {
                const nextCursor = Math.max(0, cursor - (value.length - sanitized.length));
                input.setSelectionRange(nextCursor, nextCursor);
            }
        }
    }

    function shouldGuard(input) {
        return input instanceof HTMLInputElement
            && (isEmailField(input) || isPhoneField(input) || isIntegerField(input) || isDecimalNumberField(input));
    }

    document.addEventListener('beforeinput', event => {
        const input = event.target;

        if (!shouldGuard(input) || !event.data) {
            return;
        }

        if (isPhoneField(input)) {
            if (/[^\d+]/.test(event.data)) {
                event.preventDefault();
            }
            return;
        }

        if (sanitizeValue(input, event.data) !== event.data) {
            event.preventDefault();
        }
    });

    document.addEventListener('input', event => {
        const input = event.target;

        if (shouldGuard(input)) {
            sanitizeInput(input);
        }
    });

    document.addEventListener('paste', event => {
        const input = event.target;

        if (!shouldGuard(input)) {
            return;
        }

        window.requestAnimationFrame(() => sanitizeInput(input));
    });

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('input').forEach(input => {
            if (shouldGuard(input)) {
                sanitizeInput(input);
            }
        });
    });

    window.ditentFormatRuPhone = formatRuPhone;
    window.ditentIsRuPhone = isRuPhone;
})();
