const galleryWrapper = document.querySelector('.gallery-wrapper');
const prevBtn = document.querySelector('.gallery-btn__prev');
const nextBtn = document.querySelector('.gallery-btn__next');

const galleryItems = document.querySelectorAll('.gallery-item');

let currentIndex = 0;

function scrollToItem(index) {
    galleryItems[index].scrollIntoView({
        behavior: 'smooth',
        inline: 'start',
        block: 'nearest'
    });
}

nextBtn.addEventListener('click', () => {
    currentIndex++;

    if (currentIndex >= galleryItems.length) {
        currentIndex = galleryItems.length - 1;
    }

    scrollToItem(currentIndex);
});

prevBtn.addEventListener('click', () => {
    currentIndex--;

    if (currentIndex < 0) {
        currentIndex = 0;
    }

    scrollToItem(currentIndex);
});



const faqHeaders = document.querySelectorAll('.faq-item__header');

faqHeaders.forEach(header => {
    header.addEventListener('click', () => {
        const faqItem = header.closest('.faq-item');
        faqItem.classList.toggle('open');
    });
});