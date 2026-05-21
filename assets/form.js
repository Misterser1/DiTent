const mainImage = document.getElementById('mainImage');
const galleryItems = document.querySelectorAll('.product-list__item');

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

    let count = parseInt(value.textContent);

    minusBtn.addEventListener('click', () => {
        if (count > 1) {
            count--;
            value.textContent = count;
        }
    });

    plusBtn.addEventListener('click', () => {
        count++;
        value.textContent = count;
    });
});


const wrapper = document.querySelector('.useful-wrapper');
const items = document.querySelectorAll('.useful-item');

const btnPrev = document.querySelector('.useful-btn--prev');
const btnNext = document.querySelector('.useful-btn--next');

function getStep() {
    const item = items[0];
    const style = getComputedStyle(wrapper);

    const gap = parseInt(style.columnGap || style.gap || 0);
    return item.offsetWidth + gap;
}
btnNext.addEventListener('click', () => {
    wrapper.scrollBy({
        left: getStep(),
        behavior: 'smooth'
    });
});
btnPrev.addEventListener('click', () => {
    wrapper.scrollBy({
        left: -getStep(),
        behavior: 'smooth'
    });
});