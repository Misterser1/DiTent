const counters = document.querySelectorAll('.card-checked__counter');

counters.forEach(counter => {
    const minus = counter.querySelector('.card-checked__counter-btn--minus');
    const plus = counter.querySelector('.card-checked__counter-btn--plus');
    const value = counter.querySelector('.card-checked__counter-value');

    plus.addEventListener('click', () => {
        let current = parseInt(value.textContent);
        value.textContent = current + 1;
    });

    minus.addEventListener('click', () => {
        let current = parseInt(value.textContent);

        if (current > 1) {
            value.textContent = current - 1;
        }
    });
});



const selects = document.querySelectorAll('.card-select');

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
        });
    });
});