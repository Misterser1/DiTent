const adminEntities = {
    categories: {
        newButton: 'Новая категория',
        newTitle: 'Новая категория',
        editTitle: 'Редактирование категории',
        createButton: 'Создать категорию',
    },
    products: {
        newButton: 'Новый товар',
        newTitle: 'Новый товар',
        editTitle: 'Редактирование товара',
        createButton: 'Создать товар',
    },
    fabrics: {
        newButton: 'Новая ткань',
        newTitle: 'Новая ткань',
        editTitle: 'Редактирование ткани',
        createButton: 'Создать ткань',
    },
    colors: {
        newButton: 'Новый цвет',
        newTitle: 'Новый цвет',
        editTitle: 'Редактирование цвета',
        createButton: 'Создать цвет',
    },
    fasteners: {
        newButton: 'Новое крепление',
        newTitle: 'Новое крепление',
        editTitle: 'Редактирование крепления',
        createButton: 'Создать крепление',
    },
    formulas: {
        newButton: 'Новая формула',
        newTitle: 'Новая формула',
        editTitle: 'Редактирование формулы',
        createButton: 'Создать формулу',
    },
};

function getSectionParts(section) {
    const form = section.querySelector('.admin-form');
    const title = form?.querySelector('h3');
    const actionButton = form?.querySelector('.admin-form__actions button:last-child');
    const cancelButton = form?.querySelector('.admin-form__actions button:first-child');

    return { form, title, actionButton, cancelButton };
}

function getFormFields(form) {
    return [...form.querySelectorAll('input, textarea, select')];
}

function captureFormState(form) {
    return getFormFields(form).map((field) => ({
        field,
        selectedIndex: field.tagName === 'SELECT' ? field.selectedIndex : null,
        value: field.type === 'file' ? '' : field.value,
    }));
}

function restoreFormState(form) {
    const state = form._adminSavedState;

    if (!state) {
        return;
    }

    state.forEach(({ field, selectedIndex, value }) => {
        if (field.tagName === 'SELECT') {
            field.selectedIndex = selectedIndex ?? 0;
            return;
        }

        field.value = field.type === 'file' ? '' : value;
    });

    updateCategoryImagePreview(form, form._adminSavedImage);
}

function rememberFormState(form) {
    form._adminSavedState = captureFormState(form);
    form._adminSavedImage = form.querySelector('[data-category-upload] img')?.src || '';
}

function setSelectByText(select, value) {
    const normalized = value.trim().toLowerCase();
    const option = [...select.options].find((item) => {
        const text = item.textContent.trim().toLowerCase();
        return text === normalized || text.includes(normalized) || normalized.includes(text);
    });

    if (option) {
        select.value = option.value;
    }
}

function toNumber(value) {
    return value.replace(/[^\d.,-]/g, '').replace(',', '.');
}

function createSlug(value) {
    const map = {
        а: 'a',
        б: 'b',
        в: 'v',
        г: 'g',
        д: 'd',
        е: 'e',
        ё: 'e',
        ж: 'zh',
        з: 'z',
        и: 'i',
        й: 'y',
        к: 'k',
        л: 'l',
        м: 'm',
        н: 'n',
        о: 'o',
        п: 'p',
        р: 'r',
        с: 's',
        т: 't',
        у: 'u',
        ф: 'f',
        х: 'h',
        ц: 'c',
        ч: 'ch',
        ш: 'sh',
        щ: 'sch',
        ъ: '',
        ы: 'y',
        ь: '',
        э: 'e',
        ю: 'yu',
        я: 'ya',
    };

    return value
        .toLowerCase()
        .split('')
        .map((letter) => map[letter] ?? letter)
        .join('')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function updateCategoryOrder(section) {
    section.querySelectorAll('tbody tr').forEach((row, index) => {
        const order = index + 1;
        const orderCell = row.querySelector('.admin-order');

        if (orderCell) {
            orderCell.textContent = order;
        }
    });

    const { form } = getSectionParts(section);
    const selectedRow = section._adminSelectedRow;

    if (form && selectedRow && selectedRow.isConnected && form.dataset.mode === 'edit') {
        const fields = getFormFields(form);
        fields[3].value = getCategoryPosition(selectedRow);
        rememberFormState(form);
    }
}

function getCategoryPosition(row) {
    return row?.querySelector('.admin-order')?.textContent.trim() || '';
}

function updateCategoryImagePreview(form, imagePath) {
    const previewImage = form?.querySelector('[data-category-upload] .admin-upload__dropzone img');
    const dropzone = form?.querySelector('[data-category-upload] .admin-upload__dropzone');

    if (previewImage && imagePath) {
        previewImage.src = imagePath;
        dropzone?.classList.remove('is-empty');
        return;
    }

    previewImage?.removeAttribute('src');
    dropzone?.classList.add('is-empty');
}

function updateUploadPreview(upload, imagePath) {
    const previewImage = upload?.querySelector('.admin-upload__dropzone img');
    const dropzone = upload?.querySelector('.admin-upload__dropzone');

    if (previewImage && imagePath) {
        previewImage.src = imagePath;
        dropzone?.classList.remove('is-empty');
        return;
    }

    previewImage?.removeAttribute('src');
    dropzone?.classList.add('is-empty');
}

function isImageFile(file) {
    return Boolean(file && (file.type.startsWith('image/') || /\.(avif|gif|jpe?g|png|webp|svg)$/i.test(file.name)));
}

function createPreviewUrl(file) {
    try {
        return URL.createObjectURL(file);
    } catch {
        return '';
    }
}

function syncFileInput(input, files) {
    if (!input || !window.DataTransfer) {
        return;
    }

    try {
        const dataTransfer = new DataTransfer();
        files.forEach((file) => dataTransfer.items.add(file));
        input.files = dataTransfer.files;
    } catch {
        // Some browsers restrict programmatic file assignment. Preview still works without it.
    }
}

function previewImageFile(upload, file, input) {
    if (!isImageFile(file)) {
        return false;
    }

    syncFileInput(input, [file]);

    const previewUrl = createPreviewUrl(file);
    if (!previewUrl) {
        return false;
    }

    updateUploadPreview(upload, previewUrl);
    return true;
}

function previewCategoryImageFile(form, file, input) {
    return previewImageFile(form?.querySelector('[data-category-upload]'), file, input);
}

function getGalleryImages(value) {
    return (value || '')
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function updateGalleryPreview(upload, images) {
    const dropzone = upload?.querySelector('.admin-upload__dropzone');
    const count = upload?.querySelector('[data-gallery-count]');
    const previewButton = upload?.querySelector('[data-gallery-preview]');
    const lastPreview = upload?.querySelector('[data-gallery-last-preview]');
    const imageList = Array.isArray(images) ? images : getGalleryImages(images);

    if (!upload || !dropzone) {
        return;
    }

    upload._adminGalleryImages = imageList;
    if (count) {
        count.textContent = imageList.length === 0
            ? 'Изображения не выбраны'
            : `В галерее ${imageList.length} ${getPlural(imageList.length, ['изображение', 'изображения', 'изображений'])}`;
    }
    if (previewButton) {
        previewButton.hidden = imageList.length === 0;
    }
    if (lastPreview) {
        const lastImage = imageList[imageList.length - 1] || '';

        if (lastImage) {
            lastPreview.src = lastImage;
        } else {
            lastPreview.removeAttribute('src');
        }
    }
    dropzone.classList.toggle('is-empty', imageList.length === 0);
}

function getPlural(number, forms) {
    const mod10 = number % 10;
    const mod100 = number % 100;

    if (mod10 === 1 && mod100 !== 11) {
        return forms[0];
    }

    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
        return forms[1];
    }

    return forms[2];
}

function previewGalleryFiles(upload, fileList, input) {
    const files = Array.from(fileList || []).filter(isImageFile);

    if (files.length === 0) {
        return false;
    }

    syncFileInput(input, files);

    const previewUrls = files.map(createPreviewUrl).filter(Boolean);
    if (previewUrls.length === 0) {
        return false;
    }

    updateGalleryPreview(upload, previewUrls);
    return true;
}

function initImageUpload(upload) {
    const input = upload?.querySelector('input[type="file"]');
    const dropzone = upload?.querySelector('.admin-upload__dropzone');

    if (!upload || !input || !dropzone) {
        return;
    }

    dropzone.addEventListener('click', (event) => {
        event.stopPropagation();
        input.click();
    });

    dropzone.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') {
            return;
        }

        event.preventDefault();
        input.click();
    });

    input.addEventListener('change', () => {
        previewImageFile(upload, input.files?.[0]);
    });

    const handleDragEvent = (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (event.dataTransfer) {
            event.dataTransfer.dropEffect = 'copy';
        }
    };

    ['dragenter', 'dragover'].forEach((eventName) => {
        upload.addEventListener(eventName, (event) => {
            handleDragEvent(event);
            dropzone.classList.add('is-dragover');
        });
    });

    upload.addEventListener('dragleave', (event) => {
        handleDragEvent(event);

        if (!upload.contains(event.relatedTarget)) {
            dropzone.classList.remove('is-dragover');
        }
    });

    upload.addEventListener('drop', (event) => {
        handleDragEvent(event);
        dropzone.classList.remove('is-dragover');
        previewImageFile(upload, event.dataTransfer?.files?.[0], input);
    });
}

function initGalleryUpload(upload) {
    const input = upload?.querySelector('input[type="file"]');
    const dropzone = upload?.querySelector('.admin-upload__dropzone');
    const previewButton = upload?.querySelector('[data-gallery-preview]');

    if (!upload || !input || !dropzone) {
        return;
    }

    dropzone.addEventListener('click', (event) => {
        event.stopPropagation();
        input.click();
    });

    dropzone.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') {
            return;
        }

        event.preventDefault();
        input.click();
    });

    input.addEventListener('change', () => {
        previewGalleryFiles(upload, input.files);
    });

    previewButton?.addEventListener('click', (event) => {
        event.stopPropagation();
        openGalleryModal(upload._adminGalleryImages || []);
    });

    const handleDragEvent = (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (event.dataTransfer) {
            event.dataTransfer.dropEffect = 'copy';
        }
    };

    ['dragenter', 'dragover'].forEach((eventName) => {
        upload.addEventListener(eventName, (event) => {
            handleDragEvent(event);
            dropzone.classList.add('is-dragover');
        });
    });

    upload.addEventListener('dragleave', (event) => {
        handleDragEvent(event);

        if (!upload.contains(event.relatedTarget)) {
            dropzone.classList.remove('is-dragover');
        }
    });

    upload.addEventListener('drop', (event) => {
        handleDragEvent(event);
        dropzone.classList.remove('is-dragover');
        previewGalleryFiles(upload, event.dataTransfer?.files, input);
    });
}

function openGalleryModal(images) {
    const modal = document.querySelector('[data-category-preview-modal]');
    const modalImage = modal?.querySelector('.admin-preview-modal__dialog > img');
    const modalGallery = modal?.querySelector('[data-preview-gallery]');
    const modalTitle = modal?.querySelector('#category-preview-title');

    if (!modal || !modalImage || !modalGallery || images.length === 0) {
        return;
    }

    modalTitle.textContent = 'Галерея изображений';
    modalImage.removeAttribute('src');
    modalImage.hidden = true;
    modalGallery.innerHTML = '';

    images.forEach((src) => {
        const image = document.createElement('img');
        image.src = src;
        image.alt = '';
        modalGallery.append(image);
    });

    modalGallery.hidden = false;
    modal.hidden = false;
}

function applyRowToForm(section, row) {
    const { form } = getSectionParts(section);
    const fields = getFormFields(form);
    const cells = [...row.querySelectorAll('td')].map((cell) => cell.innerText.trim());

    if (!form || cells.length === 0) {
        return;
    }

    if (section.id === 'categories') {
        fields[0].value = cells[1] || '';
        fields[1].value = cells[2] || '';
        setSelectByText(fields[2], row.dataset.parent || cells[3] || '');
        fields[3].value = getCategoryPosition(row);
        setSelectByText(fields[4], row.dataset.status || cells[5] || '');
        updateCategoryImagePreview(form, row.dataset.image);
        section._adminSelectedRow = row;
    }

    if (section.id === 'products') {
        const title = row.querySelector('.admin-category-cell span')?.textContent.trim() || cells[0] || '';
        const setProductValue = (name, value) => {
            const field = form.elements.namedItem(name);

            if (!field) {
                return;
            }

            if (field.tagName === 'SELECT') {
                setSelectByText(field, value || '');
                return;
            }

            field.value = value || '';
        };

        setProductValue('product-title', title);
        setProductValue('product-category', cells[1] || '');
        setProductValue('product-sku', row.dataset.sku || '');
        setProductValue('product-price', toNumber(cells[3] || ''));
        setProductValue('product-stock', cells[4] || '');
        setProductValue('product-status', cells[5] || '');
        setProductValue('product-width', row.dataset.width || '');
        setProductValue('product-depth', row.dataset.depth || '');
        setProductValue('product-height', row.dataset.height || '');
        setProductValue('product-fabric', row.dataset.fabric || '');
        setProductValue('product-color', row.dataset.color || '');
        setProductValue('product-fastener', row.dataset.fastener || '');
        setProductValue('product-purpose', row.dataset.purpose || '');
        setProductValue('product-description', row.dataset.description || (title ? `Готовое изделие: ${title}.` : ''));
        updateUploadPreview(form.querySelector('[data-product-upload]'), row.dataset.image);
        updateGalleryPreview(form.querySelector('[data-product-gallery-upload]'), row.dataset.gallery);
    }

    if (section.id === 'fabrics') {
        const fabricName = row.querySelector('td:first-child b')?.textContent.trim() || cells[0] || '';
        const fabricMeta = row.querySelector('td:first-child span')?.textContent.trim() || '';
        const [density = '', width = ''] = fabricMeta.split('·').map((item) => item.trim());

        fields[0].value = fabricName;
        fields[1].value = density;
        fields[2].value = toNumber(cells[1] || '');
        fields[3].value = toNumber(width || '');
        fields[4].value = row.dataset.property || cells[2] || '';
        setSelectByText(fields[5], row.dataset.uv || '');
        setSelectByText(fields[6], row.dataset.durability || '');
        setSelectByText(fields[7], row.dataset.strength || '');
        setSelectByText(fields[8], row.dataset.care || '');
        setSelectByText(fields[9], cells[4] || '');
        fields[10].value = row.dataset.purpose || '';
        fields[11].value = row.dataset.description || (fabricName ? `Материал для расчета стоимости: ${fabricName}.` : '');
    }

    if (section.id === 'colors') {
        fields[0].value = row.querySelector('.admin-category-cell span')?.textContent.trim() || (cells[0] || '').replace(/\n/g, ' ').trim();
        fields[1].value = cells[1] || '';
        setSelectByText(fields[2], cells[2] || '');
        fields[3].value = row.dataset.surcharge || toNumber(cells[3] || '');
        setSelectByText(fields[4], cells[4] || '');
        updateUploadPreview(form.querySelector('[data-color-upload]'), row.dataset.image);
    }

    if (section.id === 'fasteners') {
        fields[0].value = cells[0] || '';
        setSelectByText(fields[1], cells[1] || '');
        fields[2].value = toNumber(cells[2] || '');
        fields[4].value = cells[0] ? `Крепление: ${cells[0]}.` : '';
    }

    if (section.id === 'formulas') {
        setSelectByText(fields[0], cells[0] || '');
        fields[1].value = cells[1] || '';
        fields[2].value = toNumber(cells[2] || '');
        setSelectByText(fields[5], cells[4] || '');
        fields[6].value = cells[1] ? `Формула ${cells[1]}` : '';
        fields[7].value = cells[0] ? `Формула расчета для формы: ${cells[0]}.` : '';
    }
}

function setFormMode(section, mode) {
    const entity = adminEntities[section.id];
    const { form, title, actionButton, cancelButton } = getSectionParts(section);

    if (!entity || !form || !title || !actionButton) {
        return;
    }

    form.dataset.mode = mode;
    title.textContent = mode === 'create' ? entity.newTitle : entity.editTitle;
    actionButton.textContent = mode === 'create' ? entity.createButton : 'Сохранить изменения';
    cancelButton.hidden = false;
    cancelButton.textContent = mode === 'create' ? 'Отменить создание' : 'Сбросить изменения';

    if (mode === 'edit') {
        restoreFormState(form);
        return;
    }

    getFormFields(form).forEach((field) => {
        if (mode === 'create') {
            if (field.tagName === 'SELECT') {
                field.selectedIndex = 0;
                return;
            }

            field.value = '';
        }
    });

    if (section.id === 'categories') {
        const fields = getFormFields(form);
        fields[3].value = section.querySelectorAll('tbody tr').length + 1;
        updateCategoryImagePreview(form, '');
        section._adminSelectedRow = null;
    }

    if (section.id === 'products') {
        updateUploadPreview(form.querySelector('[data-product-upload]'), '');
        updateGalleryPreview(form.querySelector('[data-product-gallery-upload]'), []);
    }

    if (section.id === 'colors') {
        updateUploadPreview(form.querySelector('[data-color-upload]'), '');
    }
}

function initCategoryForm(section) {
    const { form } = getSectionParts(section);

    if (!form) {
        return;
    }

    const [nameField, slugField] = getFormFields(form);
    nameField?.addEventListener('input', () => {
        slugField.value = createSlug(nameField.value);
    });

    initImageUpload(form.querySelector('[data-category-upload]'));
}

function initCategoryDrag(section) {
    const tbody = section.querySelector('tbody');
    let draggedRow = null;

    if (!tbody) {
        return;
    }

    tbody.querySelectorAll('tr').forEach((row) => {
        row.addEventListener('dragstart', () => {
            draggedRow = row;
            row.classList.add('admin-row--dragging');
        });

        row.addEventListener('dragend', () => {
            row.classList.remove('admin-row--dragging');
            draggedRow = null;
            updateCategoryOrder(section);
        });
    });

    tbody.addEventListener('dragover', (event) => {
        event.preventDefault();

        const targetRow = event.target.closest('tr');

        if (!draggedRow || !targetRow || draggedRow === targetRow) {
            return;
        }

        const rect = targetRow.getBoundingClientRect();
        const shouldInsertAfter = event.clientY > rect.top + rect.height / 2;

        tbody.insertBefore(draggedRow, shouldInsertAfter ? targetRow.nextSibling : targetRow);
    });

    updateCategoryOrder(section);
}

function initCategoryPreview(section) {
    const modal = document.querySelector('[data-category-preview-modal]');
    const modalImage = modal?.querySelector('.admin-preview-modal__dialog > img');
    const modalTitle = modal?.querySelector('#category-preview-title');
    const closeButtons = modal?.querySelectorAll('[data-preview-close]');

    if (!modal || !modalImage || !modalTitle) {
        return;
    }

    const closeModal = () => {
        modal.hidden = true;
        modalImage.src = '';
        modalImage.hidden = false;
        const modalGallery = modal.querySelector('[data-preview-gallery]');
        if (modalGallery) {
            modalGallery.hidden = true;
            modalGallery.innerHTML = '';
        }
    };

    section.querySelectorAll('.admin-category-preview').forEach((button) => {
        button.addEventListener('click', () => {
            const row = button.closest('tr');
            const categoryName = row?.querySelector('.admin-category-cell span')?.textContent.trim() || 'Изображение категории';
            const imagePath = row?.dataset.image || button.querySelector('img')?.src || '';
            const modalGallery = modal.querySelector('[data-preview-gallery]');

            modalTitle.textContent = categoryName;
            modalImage.src = imagePath;
            modalImage.hidden = false;
            if (modalGallery) {
                modalGallery.hidden = true;
                modalGallery.innerHTML = '';
            }
            modal.hidden = false;
        });
    });

    closeButtons?.forEach((button) => {
        button.addEventListener('click', closeModal);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.hidden) {
            closeModal();
        }
    });
}

document.querySelectorAll('.admin-section').forEach((section) => {
    const entity = adminEntities[section.id];

    if (!entity) {
        return;
    }

    if (section.id === 'categories') {
        initCategoryForm(section);
        initCategoryDrag(section);
        initCategoryPreview(section);
    }

    if (section.id === 'products') {
        initImageUpload(section.querySelector('[data-product-upload]'));
        const galleryUpload = section.querySelector('[data-product-gallery-upload]');
        initGalleryUpload(galleryUpload);
        updateGalleryPreview(galleryUpload, section.querySelector('tbody tr')?.dataset.gallery || '');
        initCategoryPreview(section);
    }

    if (section.id === 'colors') {
        initImageUpload(section.querySelector('[data-color-upload]'));
        initCategoryPreview(section);
    }

    const newButton = section.querySelector('.admin-section__head button');
    const { form, cancelButton } = getSectionParts(section);

    if (newButton && form) {
        rememberFormState(form);
        if (section.id === 'categories') {
            section._adminSelectedRow = section.querySelector('tbody tr');
        }
        setFormMode(section, 'edit');

        newButton.textContent = entity.newButton;
        newButton.addEventListener('click', () => {
            setFormMode(section, 'create');
            form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    }

    cancelButton?.addEventListener('click', () => {
        setFormMode(section, 'edit');
        form?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });

    section.querySelectorAll('.admin-table__action').forEach((button) => {
        button.addEventListener('click', () => {
            setFormMode(section, 'edit');
            applyRowToForm(section, button.closest('tr'));
            rememberFormState(form);
            form?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    });
});
