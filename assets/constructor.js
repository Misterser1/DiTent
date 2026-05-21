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

const clothItems = document.querySelectorAll('.product-cloth__item');
clothItems.forEach(item => {
    item.addEventListener('click', () => {
        clothItems.forEach(el => {
            el.classList.remove('product-cloth__item--active');
        });
        item.classList.add('product-cloth__item--active');
    });
});

const colorItems = document.querySelectorAll('.product-color__item');
colorItems.forEach(item => {
    item.addEventListener('click', () => {
        colorItems.forEach(el => {
            el.classList.remove('product-color__item--active');
        });
        item.classList.add('product-color__item--active');
    });
});