document.querySelectorAll('[data-demo-select]').forEach(select => {
    const button = select.querySelector('[data-demo-select-button]');
    const hiddenInput = select.querySelector('input[type="hidden"]');

    button?.addEventListener('click', event => {
        event.stopPropagation();
        document.querySelectorAll('[data-demo-select].open').forEach(openSelect => {
            if (openSelect !== select) {
                openSelect.classList.remove('open');
            }
        });
        select.classList.toggle('open');
    });

    select.querySelectorAll('[data-demo-select-option]').forEach(option => {
        option.addEventListener('click', () => {
            button.textContent = option.textContent.trim();
            if (hiddenInput) {
                hiddenInput.value = option.textContent.trim();
            }
            select.classList.remove('open');
        });
    });
});

document.addEventListener('click', () => {
    document.querySelectorAll('[data-demo-select].open').forEach(select => {
        select.classList.remove('open');
    });
});
