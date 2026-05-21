const headers = document.querySelectorAll('.user-item__header');

headers.forEach(header => {
    header.addEventListener('click', () => {
        const userItem = header.closest('.user-item');
        userItem.classList.toggle('user-item--open');
    });
});



const navItems = document.querySelectorAll('.cabinet-nav__item');
const contents = document.querySelectorAll('.cabinet-content');

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


const moreButtons = document.querySelectorAll('.order-item__inner-item__more');

moreButtons.forEach(button => {
    button.addEventListener('click', () => {
        const item = button.closest('.order-item__inner-item');
        const text = button.querySelector('p');

        item.classList.toggle('open');

        const isOpen = item.classList.contains('open');

        text.textContent = isOpen ? 'Скрыть' : 'Подробнее';
    });
});