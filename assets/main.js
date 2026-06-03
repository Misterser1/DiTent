const galleryWrapper = document.querySelector('.gallery-wrapper');
const prevBtn = document.querySelector('.gallery-btn__prev');
const nextBtn = document.querySelector('.gallery-btn__next');
const galleryItems = document.querySelectorAll('.gallery-item');

let currentIndex = 0;

function scrollToItem(index) {
    galleryItems[index]?.scrollIntoView({
        behavior: 'smooth',
        inline: 'start',
        block: 'nearest',
    });
}

nextBtn?.addEventListener('click', () => {
    currentIndex = Math.min(currentIndex + 1, galleryItems.length - 1);
    scrollToItem(currentIndex);
});

prevBtn?.addEventListener('click', () => {
    currentIndex = Math.max(currentIndex - 1, 0);
    scrollToItem(currentIndex);
});

const faqItems = document.querySelectorAll('.faq-item');

function setFaqHeight(item, isOpen) {
    const dropdown = item.querySelector('.faq-item__dropdown');

    if (!dropdown) {
        return;
    }

    if (isOpen) {
        item.classList.add('open');
        dropdown.style.height = `${dropdown.scrollHeight}px`;
        return;
    }

    dropdown.style.height = `${dropdown.scrollHeight}px`;
    dropdown.offsetHeight;
    item.classList.remove('open');
    dropdown.style.height = '0px';
}

faqItems.forEach((item) => {
    const header = item.querySelector('.faq-item__header');
    const dropdown = item.querySelector('.faq-item__dropdown');

    if (!header || !dropdown) {
        return;
    }

    dropdown.style.height = item.classList.contains('open') ? `${dropdown.scrollHeight}px` : '0px';

    header.addEventListener('click', () => {
        setFaqHeight(item, !item.classList.contains('open'));
    });
});

window.addEventListener('resize', () => {
    faqItems.forEach((item) => {
        const dropdown = item.querySelector('.faq-item__dropdown');
        if (item.classList.contains('open') && dropdown) {
            dropdown.style.height = `${dropdown.scrollHeight}px`;
        }
    });
});
