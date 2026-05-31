const mainImage = document.getElementById('mainImage');
const galleryItems = document.querySelectorAll('.product-list__item');
const shapeItems = document.querySelectorAll('.product-shape__item');
const constructorTitle = document.querySelector('[data-constructor-title]');
const sizeFieldsWrapper = document.querySelector('[data-size-fields]');
const priceElement = document.querySelector('[data-product-price]');
const skuElement = document.querySelector('[data-product-sku]');
const addToCartButton = document.querySelector('[data-add-to-cart]');
const priceNote = document.querySelector('.product-sticky__counter span');
const attachmentInput = document.querySelector('[data-attachment-input]');
const attachmentDropzone = document.querySelector('[data-attachment-dropzone]');
const attachmentList = document.querySelector('[data-attachment-list]');
const constructorRoot = document.querySelector('[data-constructor-api]');
const constructorConfig = (() => {
    try {
        return JSON.parse(document.getElementById('constructor-config')?.textContent || '{}');
    } catch {
        return {};
    }
})();

const MIN_SIZE = 10;
const MAX_SIZE = 500;
const MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024;

let selectedAttachments = [];

let shapeConfigs = {
    rectangular: {
        title: 'Чехол квадратной или прямоугольной формы',
        sku: 'RECT',
        coefficient: 1,
        minimumPrice: 1000,
        seamPriceCm: 0,
        topstitchPriceCm: 0,
        edgingPriceCm: 0,
        fields: [
            { key: 'width', label: 'Ширина', code: 'A' },
            { key: 'depth', label: 'Глубина', code: 'B' },
            { key: 'height', label: 'Высота', code: 'H' },
        ],
    },
    round: {
        title: 'Чехол круглой формы',
        sku: 'ROUND',
        coefficient: 0.95,
        minimumPrice: 1000,
        seamPriceCm: 0,
        topstitchPriceCm: 0,
        edgingPriceCm: 0,
        fields: [
            { key: 'diameter', label: 'Диаметр', code: 'D' },
            { key: 'height', label: 'Высота', code: 'H' },
            { key: 'reserve', label: 'Запас', code: 'Z' },
        ],
    },
    wedge: {
        title: 'Чехол клиновидной формы',
        sku: 'WEDGE',
        coefficient: 1.08,
        minimumPrice: 1000,
        seamPriceCm: 0,
        topstitchPriceCm: 0,
        edgingPriceCm: 0,
        fields: [
            { key: 'length', label: 'Длина', code: 'A' },
            { key: 'lowHeight', label: 'Меньшая высота', code: 'B' },
            { key: 'depth', label: 'Глубина', code: 'C' },
            { key: 'highHeight', label: 'Большая высота', code: 'D' },
        ],
    },
    oval: {
        title: 'Чехол овальной формы',
        sku: 'OVAL',
        coefficient: 1.03,
        minimumPrice: 1000,
        seamPriceCm: 0,
        topstitchPriceCm: 0,
        edgingPriceCm: 0,
        fields: [
            { key: 'length', label: 'Длина', code: 'A' },
            { key: 'width', label: 'Ширина', code: 'B' },
            { key: 'height', label: 'Высота', code: 'H' },
        ],
    },
    'l-shape': {
        title: 'Чехол Г-образной формы',
        sku: 'L',
        coefficient: 1.18,
        minimumPrice: 1000,
        seamPriceCm: 0,
        topstitchPriceCm: 0,
        edgingPriceCm: 0,
        fields: [
            { key: 'backLength', label: 'Задняя длина', code: 'A' },
            { key: 'rightDepth', label: 'Правая глубина', code: 'B' },
            { key: 'highHeight', label: 'Большая высота', code: 'C' },
            { key: 'lowHeight', label: 'Меньшая высота', code: 'D' },
            { key: 'leftDepth', label: 'Левая глубина', code: 'E' },
            { key: 'frontLength', label: 'Передняя длина', code: 'F' },
            { key: 'innerLength', label: 'Внутренняя длина', code: 'G' },
            { key: 'innerDepth', label: 'Внутренняя глубина', code: 'H' },
        ],
    },
    'u-shape': {
        title: 'Чехол П-образной формы',
        sku: 'U',
        coefficient: 1.22,
        minimumPrice: 1000,
        seamPriceCm: 0,
        topstitchPriceCm: 0,
        edgingPriceCm: 0,
        fields: [
            { key: 'backWidth', label: 'Задняя ширина', code: 'A' },
            { key: 'leftDepth', label: 'Левая глубина', code: 'B' },
            { key: 'highHeight', label: 'Большая высота', code: 'C' },
            { key: 'lowHeight', label: 'Меньшая высота', code: 'D' },
            { key: 'leftFrontWidth', label: 'Левая передняя ширина', code: 'E' },
            { key: 'rightFrontWidth', label: 'Правая передняя ширина', code: 'F' },
            { key: 'innerDepth', label: 'Внутренняя глубина', code: 'G' },
            { key: 'rightDepth', label: 'Правая глубина', code: 'H' },
        ],
    },
};

if (constructorConfig.shapes?.length) {
    shapeConfigs = Object.fromEntries(constructorConfig.shapes.map(shape => [
        shape.key,
        {
            title: shape.title,
            sku: shape.sku,
            coefficient: Number(shape.coefficient || 1),
            minimumPrice: Number(shape.minimumPrice || 1000),
            seamPriceCm: Number(shape.seamPriceCm || 0),
            topstitchPriceCm: Number(shape.topstitchPriceCm || 0),
            edgingPriceCm: Number(shape.edgingPriceCm || 0),
            fields: shape.fields || [],
        },
    ]));
}

let currentShape = 'rectangular';

function formatPrice(value) {
    return `${Math.round(value).toLocaleString('ru-RU')} руб.`;
}

function getNumber(value) {
    const normalizedValue = String(value).replace(',', '.').trim();
    const number = Number(normalizedValue);

    return Number.isFinite(number) ? number : null;
}

function createSizeField(field) {
    const label = document.createElement('label');
    label.className = 'product-filter__item';

    label.innerHTML = `
        <span>${field.label} <b>${field.code}</b></span>
        <input type="number" min="${MIN_SIZE}" max="${MAX_SIZE}" step="1" placeholder="-" data-size-input data-key="${field.key}" data-label="${field.label}" data-code="${field.code}">
        <span class="product-filter__item-value">см.</span>
        <span class="product-filter__error" aria-live="polite"></span>
    `;

    const input = label.querySelector('input');
    input.addEventListener('input', () => {
        validateSizes(false);
        updateProductSummary();
    });

    return label;
}

function renderSizeFields(shapeKey) {
    if (!sizeFieldsWrapper) {
        return;
    }

    const shape = shapeConfigs[shapeKey] || shapeConfigs.rectangular;

    sizeFieldsWrapper.innerHTML = '';
    shape.fields.forEach(field => {
        sizeFieldsWrapper.append(createSizeField(field));
    });
}

function getDimensions() {
    return [...document.querySelectorAll('[data-size-input]')].map(input => ({
        key: input.dataset.key,
        label: input.dataset.label,
        code: input.dataset.code,
        value: getNumber(input.value),
        input,
        wrapper: input.closest('.product-filter__item'),
    }));
}

function validateSizes(showErrors = true) {
    let isValid = true;
    const dimensions = getDimensions();

    dimensions.forEach(dimension => {
        const hasValue = dimension.value !== null;
        const hasError = !hasValue || dimension.value < MIN_SIZE || dimension.value > MAX_SIZE;
        const errorElement = dimension.wrapper?.querySelector('.product-filter__error');

        if (hasError) {
            isValid = false;
        }

        if (!showErrors && !dimension.input.value) {
            dimension.wrapper?.classList.remove('product-filter__item--error');
            if (errorElement) {
                errorElement.textContent = '';
            }
            return;
        }

        dimension.wrapper?.classList.toggle('product-filter__item--error', hasError);

        if (errorElement) {
            errorElement.textContent = hasError ? `От ${MIN_SIZE} до ${MAX_SIZE} см` : '';
        }
    });

    const values = Object.fromEntries(dimensions.map(item => [item.key, item.value]));
    const hasAllValidNumbers = dimensions.every(item => item.value !== null && item.value >= MIN_SIZE && item.value <= MAX_SIZE);
    const setGeometryError = (key, message) => {
        const dimension = dimensions.find(item => item.key === key);
        const errorElement = dimension?.wrapper?.querySelector('.product-filter__error');

        isValid = false;
        dimension?.wrapper?.classList.add('product-filter__item--error');
        if (showErrors && errorElement) {
            errorElement.textContent = message;
        }
    };

    if (hasAllValidNumbers) {
        if (currentShape === 'wedge' && values.highHeight < values.lowHeight) {
            setGeometryError('highHeight', 'Не меньше B');
        }

        if (currentShape === 'l-shape') {
            if (values.innerLength >= values.backLength) {
                setGeometryError('innerLength', 'Меньше A');
            }
            if (values.innerDepth >= values.rightDepth) {
                setGeometryError('innerDepth', 'Меньше B');
            }
        }

        if (currentShape === 'u-shape') {
            if (values.leftFrontWidth + values.rightFrontWidth >= values.backWidth) {
                setGeometryError('leftFrontWidth', 'E + F меньше A');
                setGeometryError('rightFrontWidth', 'E + F меньше A');
            }
            if (values.innerDepth >= values.leftDepth) {
                setGeometryError('innerDepth', 'Меньше B');
            }
            if (values.rightDepth <= values.leftDepth - values.innerDepth) {
                setGeometryError('rightDepth', 'Больше B - G');
            }
        }
    }

    return isValid;
}

function getSelectedFabric() {
    const item = document.querySelector('.product-cloth__item--active') || document.querySelector('.product-cloth__item');

    return {
        id: Number(item?.dataset.fabricId || 0),
        name: item?.dataset.fabricName || item?.querySelector('h3')?.textContent.trim() || '',
        code: item?.dataset.fabricCode || 'FAB',
        price: getNumber(item?.dataset.fabricPrice || 0) || 0,
        rollWidth: getNumber(item?.dataset.fabricRollWidth || 148) || 148,
    };
}

function getSelectedColor() {
    const fabricId = String(getSelectedFabric().id || '');
    const item = document.querySelector(`.product-color__item--active[data-fabric-id="${fabricId}"]`)
        || document.querySelector(`.product-color__item[data-fabric-id="${fabricId}"]`)
        || document.querySelector('.product-color__item--active')
        || document.querySelector('.product-color__item');

    return {
        id: Number(item?.dataset.colorId || 0),
        name: item?.dataset.colorName || '',
        code: item?.dataset.colorCode || 'CLR',
        price: getNumber(item?.dataset.colorPrice || 0) || 0,
        image: item?.querySelector('img')?.getAttribute('src') || '',
    };
}

function syncColorsWithSelectedFabric() {
    const fabricId = String(getSelectedFabric().id || '');
    const items = [...document.querySelectorAll('.product-color__item')];
    let activeItem = items.find(item => item.classList.contains('product-color__item--active') && item.dataset.fabricId === fabricId);

    items.forEach(item => {
        const isCompatible = !fabricId || item.dataset.fabricId === fabricId;
        item.hidden = !isCompatible;

        if (!isCompatible) {
            item.classList.remove('product-color__item--active');
        }
    });

    if (!activeItem) {
        activeItem = items.find(item => item.dataset.fabricId === fabricId) || items[0];
        activeItem?.classList.add('product-color__item--active');
    }
}

function getSelectedFastener() {
    const input = document.querySelector('input[name="system"]:checked');
    const item = input?.closest('.product-system__item') || document.querySelector('.product-system__item');

    return {
        id: Number(item?.dataset.fastenerId || 0),
        name: item?.dataset.fastenerName || item?.querySelector('.product-system__item-row span:last-child')?.textContent.trim() || '',
        code: item?.dataset.fastenerCode || 'FAST',
        price: getNumber(item?.dataset.fastenerPrice || 0) || 0,
    };
}

function getSelectedAccessory() {
    const input = document.querySelector('input[name="bag"]:checked');
    const item = input?.closest('.option-card');

    return {
        id: Number(item?.dataset.accessoryId || 0) || null,
        name: item?.dataset.accessoryName || item?.querySelector('.option-title')?.textContent.trim() || '',
        code: item?.dataset.accessoryCode || 'ACC',
        price: getNumber(item?.dataset.accessoryPrice || 0) || 0,
    };
}

function getQuantity() {
    const valueElement = document.querySelector('.product-counter__value');
    const quantity = parseInt(valueElement?.textContent || '1', 10);

    return Number.isFinite(quantity) && quantity > 0 ? quantity : 1;
}

function formatFileSize(size) {
    if (size >= 1024 * 1024) {
        return `${(size / 1024 / 1024).toFixed(1)} МБ`;
    }

    return `${Math.max(1, Math.round(size / 1024))} КБ`;
}

function getAttachmentMeta(file) {
    return {
        name: file.name,
        size: file.size,
        type: file.type,
        lastModified: file.lastModified,
    };
}

function getProductAttachments() {
    return selectedAttachments.map(getAttachmentMeta);
}

function renderAttachmentList() {
    if (!attachmentList) {
        return;
    }

    attachmentList.innerHTML = '';
    attachmentDropzone?.classList.toggle('upload-area--selected', selectedAttachments.length > 0);

    if (!selectedAttachments.length) {
        return;
    }

    selectedAttachments.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'upload-file';
        item.innerHTML = `
            <span>${file.name}</span>
            <b>${formatFileSize(file.size)}</b>
            <button type="button" aria-label="Удалить файл" data-remove-attachment="${index}">Удалить</button>
        `;
        attachmentList.append(item);
    });
}

function addAttachments(files) {
    const incomingFiles = [...files].filter(file => file.size <= MAX_ATTACHMENT_SIZE);

    selectedAttachments = [...selectedAttachments, ...incomingFiles].filter((file, index, list) => (
        list.findIndex(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified) === index
    ));

    renderAttachmentList();
    updateProductSummary();
}

function extraByHeight(height, rollWidth) {
    if (height <= rollWidth) {
        return 0;
    }
    if (height > rollWidth * 2) {
        return 3;
    }
    return 2;
}

function calculateMetrics(shapeKey, dimensions, rollWidth = 148) {
    const values = Object.fromEntries(dimensions.map(item => [item.key, item.value || 0]));

    if (shapeKey === 'round') {
        const diameter = values.diameter + (values.reserve || 0) * 2;
        const areaCm2 = Math.PI * diameter / 2 * (2 * values.height + diameter / 2);

        return {
            area: areaCm2 / 10000,
            seamLength: Math.PI * diameter + values.height,
            edgingLength: Math.PI * diameter,
            extraSeams: extraByHeight(values.height, rollWidth),
            extraSeamLength: Math.PI * diameter,
        };
    }

    if (shapeKey === 'oval') {
        const perimeter = Math.PI * ((values.length + values.width) / 2);
        const areaCm2 = Math.PI * ((values.length * values.width) / 2) + perimeter * values.height;

        return {
            area: areaCm2 / 10000,
            seamLength: perimeter + values.height,
            edgingLength: perimeter,
            extraSeams: extraByHeight(values.height, rollWidth),
            extraSeamLength: values.length,
        };
    }

    if (shapeKey === 'wedge') {
        const slope = Math.sqrt(((values.highHeight - values.lowHeight) ** 2) + (values.depth ** 2));
        const areaCm2 = ((values.highHeight + slope + values.lowHeight) * values.length)
            + (values.lowHeight * values.depth * 2)
            + ((values.highHeight - values.lowHeight) * values.depth);

        return {
            area: areaCm2 / 10000,
            seamLength: ((values.highHeight + values.lowHeight + slope) * 2) + values.length,
            edgingLength: 2 * (values.length + values.depth),
            extraSeams: values.length <= rollWidth || (values.highHeight + slope) <= rollWidth ? 0 : 2,
            extraSeamLength: values.length,
        };
    }

    if (shapeKey === 'l-shape') {
        const slope = Math.sqrt(((values.highHeight - values.lowHeight) ** 2) + (values.leftDepth ** 2));
        const topArea = (values.backLength * values.rightDepth) - (values.innerLength * values.innerDepth);
        const areaCm2 = (0.5 * (values.highHeight + values.lowHeight) * values.leftDepth)
            + (0.5 * (values.highHeight + values.lowHeight) * values.frontLength)
            + ((values.backLength + values.rightDepth) * values.highHeight)
            + ((values.innerLength + values.innerDepth) * values.lowHeight)
            + topArea;

        return {
            area: areaCm2 / 10000,
            seamLength: ((values.highHeight + values.lowHeight + slope) * 2) + values.backLength + values.rightDepth,
            edgingLength: values.backLength + values.rightDepth + values.frontLength + values.innerDepth + values.innerLength + values.leftDepth,
            extraSeams: values.innerLength <= rollWidth || (values.highHeight + slope) <= rollWidth ? 0 : 2,
            extraSeamLength: values.highHeight + values.lowHeight + values.frontLength,
        };
    }

    if (shapeKey === 'u-shape') {
        const centerWidth = values.backWidth - values.leftFrontWidth - values.rightFrontWidth;
        const rightInnerDepth = values.rightDepth - (values.leftDepth - values.innerDepth);
        const slopeLeft = Math.sqrt(((values.highHeight - values.lowHeight) ** 2) + (values.leftFrontWidth ** 2));
        const slopeCenter = Math.sqrt(((values.highHeight - values.lowHeight) ** 2) + ((values.leftDepth - values.innerDepth) ** 2));
        const slopeRight = Math.sqrt(((values.highHeight - values.lowHeight) ** 2) + (values.rightFrontWidth ** 2));
        const areaCm2 = (0.5 * (values.highHeight + values.lowHeight) * values.leftFrontWidth)
            + (0.5 * (values.highHeight + values.lowHeight) * values.rightFrontWidth)
            + ((values.leftDepth + values.backWidth + values.rightDepth) * values.highHeight)
            + ((values.innerDepth + centerWidth + rightInnerDepth) * values.lowHeight)
            + (((values.leftDepth + values.innerDepth) / 2) * slopeLeft)
            + (((values.backWidth + centerWidth) / 2) * slopeCenter)
            + (((values.rightDepth + rightInnerDepth) / 2) * slopeRight);

        return {
            area: areaCm2 / 10000,
            seamLength: (values.highHeight * 2)
                + (values.lowHeight * 4)
                + slopeLeft
                + slopeRight
                + values.backWidth
                + values.leftDepth
                + values.rightDepth
                + values.innerDepth
                + rightInnerDepth
                + centerWidth,
            edgingLength: values.leftFrontWidth + values.leftDepth + values.backWidth + values.rightDepth + values.rightFrontWidth + rightInnerDepth + centerWidth,
            extraSeams: values.innerDepth <= rollWidth || (values.highHeight + slopeLeft) <= rollWidth ? 0 : 2,
            extraSeamLength: values.highHeight + values.lowHeight + values.rightFrontWidth,
        };
    }

    const areaCm2 = values.width * values.depth + 2 * (values.width + values.depth) * values.height;
    const extraSeams = values.width <= rollWidth || values.depth <= rollWidth
        ? 0
        : Math.min(3, Math.floor(Math.min(values.width, values.depth) / rollWidth));

    return {
        area: areaCm2 / 10000,
        seamLength: 4 * values.height + 2 * (values.width + values.depth),
        edgingLength: 2 * (values.width + values.depth),
        extraSeams,
        extraSeamLength: values.width,
    };
}

function getCalculatedProduct() {
    const shape = shapeConfigs[currentShape] || shapeConfigs.rectangular;
    const dimensions = getDimensions().map(({ input, wrapper, ...dimension }) => dimension);
    const isValid = validateSizes(false);
    const fabric = getSelectedFabric();
    const color = getSelectedColor();
    const fastener = getSelectedFastener();
    const accessory = getSelectedAccessory();
    const quantity = getQuantity();
    const metrics = isValid ? calculateMetrics(currentShape, dimensions, fabric.rollWidth) : {
        area: 0,
        seamLength: 0,
        edgingLength: 0,
        extraSeams: 0,
        extraSeamLength: 0,
    };
    const materialPrice = metrics.area * fabric.price;
    const seamPrice = metrics.seamLength * (shape.seamPriceCm || 0);
    const edgingPrice = metrics.edgingLength * (shape.edgingPriceCm || 0);
    const extraSeamsPrice = metrics.extraSeams * (((shape.seamPriceCm || 0) + (shape.topstitchPriceCm || 0)) * metrics.extraSeamLength);
    const formulaPrice = (materialPrice + seamPrice + edgingPrice + extraSeamsPrice) * shape.coefficient;
    const optionsPrice = color.price + fastener.price + accessory.price;
    const discount = quantity >= 8 ? 0.9 : 1;
    const minimumPrice = getNumber(shape.minimumPrice || 1000) || 0;
    const unitPrice = isValid ? Math.max(minimumPrice, Math.ceil((formulaPrice + optionsPrice) / 50) * 50) : 0;
    const discountedUnitPrice = Math.ceil(unitPrice * discount / 50) * 50;
    const totalPrice = discountedUnitPrice * quantity;
    const sizeCode = dimensions.map(dimension => dimension.value || 'NA').join('x');
    const sku = `DT-${shape.sku}-${fabric.code}-${color.code}-${fastener.code}-${sizeCode}`;

    return {
        isValid,
        shape: {
            key: currentShape,
            title: shape.title,
            code: shape.sku,
        },
        dimensions,
        area: metrics.area,
        pricing: {
            ...metrics,
            materialPrice,
            seamPrice,
            edgingPrice,
            extraSeamsPrice,
            optionsPrice,
            coefficient: shape.coefficient,
            minimumPrice,
        },
        fabric,
        color,
        fastener,
        accessory,
        quantity,
        unitPrice: discountedUnitPrice,
        totalPrice,
        sku,
        comments: document.querySelector('[name="productText"]')?.value.trim() || '',
        attachments: getProductAttachments(),
    };
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);

    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }

    return '';
}

function buildBackendPayload(product) {
    return {
        shape: product.shape.key,
        dimensions: product.dimensions,
        fabricId: product.fabric.id,
        colorId: product.color.id,
        fastenerId: product.fastener.id,
        accessoryId: product.accessory?.id || null,
        quantity: product.quantity,
        comments: product.comments,
        attachments: product.attachments || [],
    };
}

async function verifyProductOnBackend(product) {
    const apiUrl = constructorRoot?.dataset.constructorApi;

    if (!apiUrl) {
        return product;
    }

    const formData = new FormData();
    formData.append('payload', JSON.stringify(buildBackendPayload(product)));
    selectedAttachments.forEach(file => {
        formData.append('attachments', file);
    });

    const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            Accept: 'application/json',
        },
        body: formData,
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || 'Не удалось проверить расчет на сервере.');
    }

    return {
        ...product,
        ...payload.item,
        isValid: true,
        image: 'assets/image/card-img-1.png',
    };
}

async function addCartItemToBackend(product) {
    const response = await fetch('cart/api/items/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
            Accept: 'application/json',
        },
        body: JSON.stringify({
            ...product,
            type: 'custom-cover',
        }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || 'Не удалось добавить товар в корзину.');
    }

    localStorage.setItem('ditentCart', JSON.stringify(payload.cart.items || []));
    window.ditentLastCartItem = payload.cart.items?.[payload.cart.items.length - 1] || product;

    return payload.cart;
}

function updateProductSummary() {
    const product = getCalculatedProduct();

    if (priceElement) {
        priceElement.textContent = product.isValid ? formatPrice(product.totalPrice) : 'Укажите размеры';
    }

    if (skuElement) {
        skuElement.textContent = `Артикул: ${product.sku}`;
    }

    if (priceNote) {
        priceNote.textContent = product.quantity >= 8 ? 'Оптовая цена' : 'Розничная цена';
    }
}

function selectShape(item) {
    const input = item?.querySelector('input');

    if (!item || !input) {
        return;
    }

    shapeItems.forEach(el => {
        el.classList.remove('product-shape__item--active');
    });

    item.classList.add('product-shape__item--active');
    input.checked = true;
    currentShape = input.value;

    const shape = shapeConfigs[currentShape] || shapeConfigs.rectangular;

    if (constructorTitle) {
        constructorTitle.textContent = input.dataset.title || shape.title;
    }

    renderSizeFields(currentShape);
    updateProductSummary();
}

function saveProductToCart(product) {
    const cartItem = {
        id: `${product.sku}-${Date.now()}`,
        type: 'custom-cover',
        title: product.shape.title,
        sku: product.sku,
        quantity: product.quantity,
        unitPrice: product.unitPrice,
        totalPrice: product.totalPrice,
        shape: product.shape,
        dimensions: product.dimensions,
        fabric: product.fabric,
        color: product.color,
        fastener: product.fastener,
        accessory: product.accessory,
        comments: product.comments,
        attachments: product.attachments,
    };
    const cart = JSON.parse(localStorage.getItem('ditentCart') || '[]');

    cart.push(cartItem);
    localStorage.setItem('ditentCart', JSON.stringify(cart));
    window.ditentLastCartItem = cartItem;

    return cartItem;
}

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

shapeItems.forEach(item => {
    item.addEventListener('click', () => {
        selectShape(item);
    });
});

const initialShape = new URLSearchParams(window.location.search).get('shape');
const shapeAliases = {
    rect: 'rectangular',
    rectangle: 'rectangular',
    l: 'l-shape',
    'l-shaped': 'l-shape',
    u: 'u-shape',
    'u-shaped': 'u-shape',
};
const normalizedShape = shapeAliases[initialShape] || initialShape;
const initialShapeItem = [...shapeItems].find(item => item.querySelector('input')?.value === normalizedShape)
    || document.querySelector('.product-shape__item--active')
    || shapeItems[0];

selectShape(initialShapeItem);

const counters = document.querySelectorAll('.product-counter__wrapper');

counters.forEach(counter => {
    const minusBtn = counter.querySelector('.product-counter__btn--prev');
    const plusBtn = counter.querySelector('.product-counter__btn--next');
    const value = counter.querySelector('.product-counter__value');

    let count = parseInt(value.textContent, 10);

    minusBtn.addEventListener('click', () => {
        if (count > 1) {
            count--;
            value.textContent = count;
            updateProductSummary();
        }
    });

    plusBtn.addEventListener('click', () => {
        count++;
        value.textContent = count;
        updateProductSummary();
    });
});

const clothItems = document.querySelectorAll('.product-cloth__item');
clothItems.forEach(item => {
    item.addEventListener('click', () => {
        clothItems.forEach(el => {
            el.classList.remove('product-cloth__item--active');
        });
        item.classList.add('product-cloth__item--active');
        syncColorsWithSelectedFabric();
        updateProductSummary();
    });
});

const colorItems = document.querySelectorAll('.product-color__item');
colorItems.forEach(item => {
    item.addEventListener('click', () => {
        colorItems.forEach(el => {
            el.classList.remove('product-color__item--active');
        });
        item.classList.add('product-color__item--active');
        updateProductSummary();
    });
});

syncColorsWithSelectedFabric();
updateProductSummary();

document.querySelectorAll('input[name="system"], input[name="bag"]').forEach(input => {
    input.addEventListener('change', updateProductSummary);
});

document.querySelector('[name="productText"]')?.addEventListener('input', updateProductSummary);

attachmentInput?.addEventListener('change', () => {
    addAttachments(attachmentInput.files || []);
    attachmentInput.value = '';
});

attachmentList?.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-attachment]');

    if (!button) {
        return;
    }

    selectedAttachments.splice(Number(button.dataset.removeAttachment), 1);
    renderAttachmentList();
    updateProductSummary();
});

['dragenter', 'dragover'].forEach(eventName => {
    attachmentDropzone?.addEventListener(eventName, event => {
        event.preventDefault();
        attachmentDropzone.classList.add('upload-area--dragover');
    });
});

['dragleave', 'drop'].forEach(eventName => {
    attachmentDropzone?.addEventListener(eventName, event => {
        event.preventDefault();
        attachmentDropzone.classList.remove('upload-area--dragover');
    });
});

attachmentDropzone?.addEventListener('drop', event => {
    addAttachments(event.dataTransfer?.files || []);
});

addToCartButton?.addEventListener('click', async () => {
    const isValid = validateSizes(true);

    if (!isValid) {
        document.querySelector('.product-filter__item--error input')?.focus();
        updateProductSummary();
        return;
    }

    const product = getCalculatedProduct();
    const initialText = addToCartButton.textContent;
    addToCartButton.disabled = true;
    addToCartButton.textContent = 'Проверяем расчет';

    try {
        const verifiedProduct = await verifyProductOnBackend(product);
        await addCartItemToBackend(verifiedProduct);
        selectedAttachments = [];
        renderAttachmentList();
        addToCartButton.textContent = 'Добавлено';
    } catch (error) {
        addToCartButton.textContent = error.message;
    } finally {
        addToCartButton.disabled = false;
    }

    setTimeout(() => {
        addToCartButton.textContent = initialText;
    }, 1400);
});

updateProductSummary();
