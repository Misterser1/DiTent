(function () {
    const sections = {
        garden: {
            title: 'Чехлы для садовой мебели',
            description: 'Готовые защитные чехлы для столов, диванов и комплектов мебели. Выберите тип изделия, чтобы перейти к карточкам товаров.',
            categories: [
                {
                    id: 'tables',
                    title: 'Чехлы для столов',
                    count: 12,
                    products: [
                        ['Чехол для стола 300x100x75', 'Оксфорд 600D PU1000, черный, ремни на углах внутри.', '1 000 руб.', 'assets/image/card-img-1.png'],
                        ['Чехол для круглого стола', 'ПВХ Dejia 470, серый, утяжка по нижнему краю.', '2 400 руб.', 'assets/image/catalog-img-1.png'],
                        ['Чехол для журнального стола', 'Защита от влаги и пыли для сезонного хранения.', '1 800 руб.', 'assets/image/item-img-1.png'],
                    ],
                },
                {
                    id: 'sofas',
                    title: 'Чехлы для диванов',
                    count: 8,
                    products: [
                        ['Чехол для прямого дивана', 'Плотная ткань, вентиляционные люверсы и фиксация снизу.', '3 200 руб.', 'assets/image/catalog-img-1.png'],
                        ['Чехол для углового дивана', 'Защита мягкой мебели от дождя, пыли и выгорания.', '4 900 руб.', 'assets/image/card-img-1.png'],
                    ],
                },
                {
                    id: 'sets',
                    title: 'Чехлы для комплектов мебели',
                    count: 6,
                    products: [
                        ['Чехол для комплекта 4+1', 'Единый чехол для стола и кресел в собранном виде.', '5 600 руб.', 'assets/image/catalog-img-1.png'],
                        ['Чехол для лаунж-зоны', 'Усиленные углы и крепления для уличного хранения.', '6 800 руб.', 'assets/image/card-img-1.png'],
                    ],
                },
            ],
        },
        equipment: {
            title: 'Чехлы для оборудования',
            description: 'Защитные чехлы для грилей, генераторов, насосов и другого оборудования, которое хранится на улице или в технических помещениях.',
            categories: [
                {
                    id: 'grills',
                    title: 'Чехлы для грилей',
                    count: 9,
                    products: [
                        ['Чехол для газового гриля', 'Водоотталкивающая ткань, ремни фиксации по бокам.', '2 900 руб.', 'assets/image/catalog-img-2.png'],
                        ['Чехол для мангала', 'Плотная защита от влаги, пыли и сезонного хранения.', '1 700 руб.', 'assets/image/card-img-1.png'],
                    ],
                },
                {
                    id: 'generators',
                    title: 'Чехлы для генераторов',
                    count: 5,
                    products: [
                        ['Чехол для генератора', 'Техническая ткань с усиленными швами и ручками.', '2 300 руб.', 'assets/image/catalog-img-2.png'],
                        ['Чехол для насосной станции', 'Компактный защитный чехол с нижней утяжкой.', '1 900 руб.', 'assets/image/item-img-2.png'],
                    ],
                },
                {
                    id: 'pools',
                    title: 'Чехлы для бассейнов',
                    count: 4,
                    products: [
                        ['Чехол для каркасного бассейна', 'Защита чаши от мусора и осадков в межсезонье.', '4 200 руб.', 'assets/image/catalog-img-2.png'],
                    ],
                },
            ],
        },
        tech: {
            title: 'Чехлы для техники',
            description: 'Чехлы для квадроциклов, мотоциклов, садовой техники и другого транспорта, которому нужна защита при хранении.',
            categories: [
                {
                    id: 'quad',
                    title: 'Чехлы для квадроциклов',
                    count: 7,
                    products: [
                        ['Чехол для квадроцикла', 'Усиленная ткань, крепления снизу и защита от осадков.', '4 500 руб.', 'assets/image/catalog-img-3.png'],
                        ['Чехол для снегохода', 'Увеличенная длина и плотная посадка по корпусу.', '5 100 руб.', 'assets/image/card-img-1.png'],
                    ],
                },
                {
                    id: 'moto',
                    title: 'Чехлы для мотоциклов',
                    count: 10,
                    products: [
                        ['Чехол для мотоцикла', 'Легкий защитный чехол для уличного и гаражного хранения.', '2 800 руб.', 'assets/image/catalog-img-3.png'],
                        ['Чехол для скутера', 'Компактная модель с фиксацией по нижнему краю.', '2 100 руб.', 'assets/image/item-img-3.png'],
                    ],
                },
                {
                    id: 'garden-tech',
                    title: 'Чехлы для садовой техники',
                    count: 6,
                    products: [
                        ['Чехол для газонокосилки', 'Защита корпуса и двигателя от влаги и пыли.', '1 600 руб.', 'assets/image/catalog-img-3.png'],
                    ],
                },
            ],
        },
        special: {
            title: 'Специализированные чехлы',
            description: 'Нестандартные решения для сложных форм, коммерческих объектов и изделий, которые требуют индивидуальной посадки.',
            categories: [
                {
                    id: 'custom',
                    title: 'Чехлы по индивидуальным размерам',
                    count: 11,
                    products: [
                        ['Индивидуальный защитный чехол', 'Расчет по размерам, форме и выбранной ткани.', 'от 1 000 руб.', 'assets/image/catalog-img-4.png'],
                        ['Чехол сложной формы', 'Подходит для нестандартных объектов и оборудования.', 'от 2 500 руб.', 'assets/image/card-img-1.png'],
                    ],
                },
                {
                    id: 'commercial',
                    title: 'Чехлы для коммерческих объектов',
                    count: 5,
                    products: [
                        ['Чехол для уличной стойки', 'Износостойкая ткань и аккуратная посадка по форме.', '3 400 руб.', 'assets/image/catalog-img-4.png'],
                    ],
                },
                {
                    id: 'storage',
                    title: 'Чехлы для хранения',
                    count: 8,
                    products: [
                        ['Чехол для сезонного хранения', 'Базовая защита от пыли, влаги и солнечного света.', '1 900 руб.', 'assets/image/item-img-4.png'],
                    ],
                },
            ],
        },
    };

    const params = new URLSearchParams(window.location.search);
    const sectionKey = sections[params.get('section')] ? params.get('section') : 'garden';
    const section = sections[sectionKey];
    const categoryId = params.get('category');
    const activeCategory = section.categories.find((item) => item.id === categoryId) || section.categories[0];

    const setText = (selector, value) => {
        document.querySelectorAll(selector).forEach((element) => {
            element.textContent = value;
        });
    };

    const createProductCard = ([title, text, price, image]) => `
        <article class="category-product">
            <a class="category-product__img" href="form.html">
                <img src="${image}" alt="">
            </a>
            <div class="category-product__body">
                <h3>${title}</h3>
                <p>${text}</p>
                <div>
                    <b>${price}</b>
                    <a href="form.html">Подробнее</a>
                </div>
            </div>
        </article>
    `;

    document.title = `DiTent - ${section.title}`;
    setText('[data-section-title]', section.title);
    setText('[data-section-description]', section.description);
    setText('[data-category-title]', activeCategory.title);
    setText('[data-category-count]', `${activeCategory.count} товаров`);

    const nav = document.querySelector('[data-category-nav]');
    if (nav) {
        nav.innerHTML = section.categories.map((item) => {
            const isActive = item.id === activeCategory.id ? ' class="is-active"' : '';
            return `
                <a${isActive} href="category.html?section=${sectionKey}&category=${item.id}">
                    <span>${item.title}</span>
                    <b>${item.count}</b>
                </a>
            `;
        }).join('');
    }

    const productGrid = document.querySelector('[data-product-grid]');
    if (productGrid) {
        productGrid.innerHTML = activeCategory.products.map(createProductCard).join('');
    }
}());
