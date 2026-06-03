import math
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from django.core.exceptions import ValidationError

from .models import Accessory, Color, CoverShape, Fabric, Fastener, Formula, PublishStatus


MIN_SIZE = 10
MAX_SIZE = 500
DEFAULT_MINIMUM_PRICE = Decimal('1000.00')
DEFAULT_ROLL_WIDTH = Decimal('148')
PI = Decimal('3.141592653589793238462643383279502884')

SHAPE_DEFINITIONS = {
    CoverShape.RECTANGULAR: {
        'ui_key': 'rectangular',
        'sku': 'RECT',
        'title': 'Чехол квадратной или прямоугольной формы',
        'image': 'assets/image/item-img-1.png',
        'fields': [
            {'key': 'width', 'label': 'Ширина', 'code': 'A'},
            {'key': 'depth', 'label': 'Глубина', 'code': 'B'},
            {'key': 'height', 'label': 'Высота', 'code': 'H'},
        ],
        'default_coefficient': Decimal('1.000'),
    },
    CoverShape.ROUND: {
        'ui_key': 'round',
        'sku': 'ROUND',
        'title': 'Чехол круглой формы',
        'image': 'assets/image/item-img-2.png',
        'fields': [
            {'key': 'diameter', 'label': 'Диаметр', 'code': 'D'},
            {'key': 'height', 'label': 'Высота', 'code': 'H'},
            {'key': 'reserve', 'label': 'Запас', 'code': 'Z'},
        ],
        'default_coefficient': Decimal('0.950'),
    },
    CoverShape.WEDGE: {
        'ui_key': 'wedge',
        'sku': 'WEDGE',
        'title': 'Чехол клиновидной формы',
        'image': 'assets/image/item-img-3.png',
        'fields': [
            {'key': 'length', 'label': 'Длина', 'code': 'A'},
            {'key': 'lowHeight', 'label': 'Меньшая высота', 'code': 'B'},
            {'key': 'depth', 'label': 'Глубина', 'code': 'C'},
            {'key': 'highHeight', 'label': 'Большая высота', 'code': 'D'},
        ],
        'default_coefficient': Decimal('1.080'),
    },
    CoverShape.OVAL: {
        'ui_key': 'oval',
        'sku': 'OVAL',
        'title': 'Чехол овальной формы',
        'image': 'assets/image/item-img-4.png',
        'fields': [
            {'key': 'length', 'label': 'Длина', 'code': 'A'},
            {'key': 'width', 'label': 'Ширина', 'code': 'B'},
            {'key': 'height', 'label': 'Высота', 'code': 'H'},
        ],
        'default_coefficient': Decimal('1.030'),
    },
    CoverShape.L_SHAPED: {
        'ui_key': 'l-shape',
        'sku': 'L',
        'title': 'Чехол Г-образной формы',
        'image': 'assets/image/item-img-5.png',
        'fields': [
            {'key': 'backLength', 'label': 'Задняя длина', 'code': 'A'},
            {'key': 'rightDepth', 'label': 'Правая глубина', 'code': 'B'},
            {'key': 'highHeight', 'label': 'Большая высота', 'code': 'C'},
            {'key': 'lowHeight', 'label': 'Меньшая высота', 'code': 'D'},
            {'key': 'leftDepth', 'label': 'Левая глубина', 'code': 'E'},
            {'key': 'frontLength', 'label': 'Передняя длина', 'code': 'F'},
            {'key': 'innerLength', 'label': 'Внутренняя длина', 'code': 'G'},
            {'key': 'innerDepth', 'label': 'Внутренняя глубина', 'code': 'H'},
        ],
        'default_coefficient': Decimal('1.180'),
    },
    CoverShape.U_SHAPED: {
        'ui_key': 'u-shape',
        'sku': 'U',
        'title': 'Чехол П-образной формы',
        'image': 'assets/image/item-img-6.png',
        'fields': [
            {'key': 'backWidth', 'label': 'Задняя ширина', 'code': 'A'},
            {'key': 'leftDepth', 'label': 'Левая глубина', 'code': 'B'},
            {'key': 'highHeight', 'label': 'Большая высота', 'code': 'C'},
            {'key': 'lowHeight', 'label': 'Меньшая высота', 'code': 'D'},
            {'key': 'leftFrontWidth', 'label': 'Левая передняя ширина', 'code': 'E'},
            {'key': 'rightFrontWidth', 'label': 'Правая передняя ширина', 'code': 'F'},
            {'key': 'innerDepth', 'label': 'Внутренняя глубина', 'code': 'G'},
            {'key': 'rightDepth', 'label': 'Правая глубина', 'code': 'H'},
        ],
        'default_coefficient': Decimal('1.220'),
    },
}

UI_TO_DB_SHAPE = {value['ui_key']: key for key, value in SHAPE_DEFINITIONS.items()}


def decimal_string(value):
    return format(value, 'f')


def active_formula(shape):
    return Formula.objects.filter(shape=shape, status=PublishStatus.ACTIVE).order_by('id').first()


def shape_config(shape):
    definition = SHAPE_DEFINITIONS[shape]
    formula = active_formula(shape)
    coefficient = formula.coefficient if formula else definition['default_coefficient']
    minimum_price = formula.minimum_price if formula else DEFAULT_MINIMUM_PRICE
    seam_price_cm = formula.seam_price_cm if formula else Decimal('0.00')
    topstitch_price_cm = formula.topstitch_price_cm if formula else Decimal('0.00')
    edging_price_cm = formula.edging_price_cm if formula else Decimal('0.00')

    return {
        'key': definition['ui_key'],
        'dbShape': shape,
        'title': definition['title'],
        'sku': definition['sku'],
        'coefficient': decimal_string(coefficient),
        'minimumPrice': decimal_string(minimum_price),
        'seamPriceCm': decimal_string(seam_price_cm),
        'topstitchPriceCm': decimal_string(topstitch_price_cm),
        'edgingPriceCm': decimal_string(edging_price_cm),
        'minSize': formula.min_size_cm if formula else MIN_SIZE,
        'maxSize': formula.max_size_cm if formula else MAX_SIZE,
        'fields': definition['fields'],
        'image': definition['image'],
        'formulaCode': formula.code if formula else '',
    }


def constructor_config():
    return {
        'minSize': MIN_SIZE,
        'maxSize': MAX_SIZE,
        'shapes': [shape_config(shape) for shape in SHAPE_DEFINITIONS],
    }


def to_decimal(value, field_name):
    try:
        return Decimal(str(value).replace(',', '.'))
    except Exception as exc:
        raise ValidationError({field_name: 'Некорректное число.'}) from exc


def validate_dimensions(shape, dimensions):
    definition = SHAPE_DEFINITIONS[shape]
    values_by_key = {item.get('key'): item for item in dimensions or []}
    validated = []

    for field in definition['fields']:
        raw = values_by_key.get(field['key'], {}).get('value')
        value = to_decimal(raw, field['key'])

        if value != value.to_integral_value():
            raise ValidationError({field['key']: 'Укажите размер целым числом.'})

        if value < MIN_SIZE or value > MAX_SIZE:
            raise ValidationError({field['key']: f'Размер должен быть от {MIN_SIZE} до {MAX_SIZE} см.'})

        validated.append({**field, 'value': value})

    values = {item['key']: item['value'] for item in validated}

    if shape == CoverShape.WEDGE and values['highHeight'] < values['lowHeight']:
        raise ValidationError({'highHeight': 'Большая высота должна быть не меньше меньшей высоты.'})

    if shape == CoverShape.L_SHAPED:
        if values['innerLength'] >= values['backLength']:
            raise ValidationError({'innerLength': 'Внутренняя длина должна быть меньше задней длины.'})
        if values['innerDepth'] >= values['rightDepth']:
            raise ValidationError({'innerDepth': 'Внутренняя глубина должна быть меньше правой глубины.'})

    if shape == CoverShape.U_SHAPED:
        if values['leftFrontWidth'] + values['rightFrontWidth'] >= values['backWidth']:
            raise ValidationError({'leftFrontWidth': 'Сумма передних ширин должна быть меньше задней ширины.'})
        if values['innerDepth'] >= values['leftDepth']:
            raise ValidationError({'innerDepth': 'Внутренняя глубина должна быть меньше левой глубины.'})
        if values['rightDepth'] <= values['leftDepth'] - values['innerDepth']:
            raise ValidationError({'rightDepth': 'Правая глубина должна быть больше разницы B-G.'})

    return validated


def decimal_sqrt(value):
    return Decimal(str(math.sqrt(float(max(value, Decimal('0'))))))


def fabric_roll_width(fabric):
    return Decimal(str(fabric.roll_width_cm or DEFAULT_ROLL_WIDTH))


def extra_by_height(height, roll_width):
    if height <= roll_width:
        return Decimal('0')
    if height > roll_width * 2:
        return Decimal('3')
    return Decimal('2')


def calculation_metrics(shape, dimensions, fabric):
    values = {item['key']: item['value'] for item in dimensions}
    roll_width = fabric_roll_width(fabric)

    if shape == CoverShape.ROUND:
        a = values['diameter'] + values.get('reserve', Decimal('0')) * 2
        b = values['height']
        area_cm2 = PI * a / 2 * (2 * b + a / 2)
        seam_length = PI * a + b
        edging_length = PI * a
        extra_seams = extra_by_height(b, roll_width)
        extra_seam_length = PI * a

        return {
            'area': area_cm2 / Decimal('10000'),
            'seam_length': seam_length,
            'edging_length': edging_length,
            'extra_seams': extra_seams,
            'extra_seam_length': extra_seam_length,
        }

    if shape == CoverShape.OVAL:
        a = values['length']
        b = values['width']
        c = values['height']
        perimeter = PI * ((a + b) / 2)
        area_cm2 = PI * ((a * b) / 2) + perimeter * c
        extra_seams = extra_by_height(c, roll_width)

        return {
            'area': area_cm2 / Decimal('10000'),
            'seam_length': perimeter + c,
            'edging_length': perimeter,
            'extra_seams': extra_seams,
            'extra_seam_length': a,
        }

    if shape == CoverShape.WEDGE:
        a = values['length']
        b = values['lowHeight']
        c = values['depth']
        d = values['highHeight']
        slope = decimal_sqrt(((d - b) * (d - b)) + (c * c))
        area_cm2 = ((d + slope + b) * a) + (b * c * 2) + ((d - b) * c)
        extra_seams = Decimal('0') if a <= roll_width or (d + slope) <= roll_width else Decimal('2')

        return {
            'area': area_cm2 / Decimal('10000'),
            'seam_length': ((d + b + slope) * 2) + a,
            'edging_length': 2 * (a + c),
            'extra_seams': extra_seams,
            'extra_seam_length': a,
        }

    if shape == CoverShape.L_SHAPED:
        a = values['backLength']
        b = values['rightDepth']
        c = values['highHeight']
        d = values['lowHeight']
        e = values['leftDepth']
        f = values['frontLength']
        g = values['innerLength']
        h = values['innerDepth']
        slope = decimal_sqrt(((c - d) * (c - d)) + (e * e))
        top_area = (a * b) - (g * h)
        area_cm2 = (
            (Decimal('0.5') * (c + d) * e)
            + (Decimal('0.5') * (c + d) * f)
            + ((a + b) * c)
            + ((g + h) * d)
            + top_area
        )
        extra_seams = Decimal('0') if g <= roll_width or (c + slope) <= roll_width else Decimal('2')

        return {
            'area': area_cm2 / Decimal('10000'),
            'seam_length': ((c + d + slope) * 2) + a + b,
            'edging_length': a + b + f + h + g + e,
            'extra_seams': extra_seams,
            'extra_seam_length': c + d + f,
        }

    if shape == CoverShape.U_SHAPED:
        a = values['backWidth']
        b = values['leftDepth']
        c = values['highHeight']
        d = values['lowHeight']
        e = values['leftFrontWidth']
        f = values['rightFrontWidth']
        g = values['innerDepth']
        h = values['rightDepth']
        center_width = a - e - f
        right_inner_depth = h - (b - g)
        slope_left = decimal_sqrt(((c - d) * (c - d)) + (e * e))
        slope_center = decimal_sqrt(((c - d) * (c - d)) + ((b - g) * (b - g)))
        slope_right = decimal_sqrt(((c - d) * (c - d)) + (f * f))
        area_cm2 = (
            (Decimal('0.5') * (c + d) * e)
            + (Decimal('0.5') * (c + d) * f)
            + ((b + a + h) * c)
            + ((g + center_width + right_inner_depth) * d)
            + (((b + g) / 2) * slope_left)
            + (((a + center_width) / 2) * slope_center)
            + (((h + right_inner_depth) / 2) * slope_right)
        )
        extra_seams = Decimal('0') if g <= roll_width or (c + slope_left) <= roll_width else Decimal('2')

        return {
            'area': area_cm2 / Decimal('10000'),
            'seam_length': (
                c * 2
                + d * 4
                + slope_left
                + slope_right
                + a
                + b
                + h
                + g
                + right_inner_depth
                + center_width
            ),
            'edging_length': e + b + a + h + f + right_inner_depth + center_width,
            'extra_seams': extra_seams,
            'extra_seam_length': c + d + f,
        }

    a = values['width']
    b = values['depth']
    c = values['height']
    area_cm2 = a * b + 2 * (a + b) * c
    extra_seams = Decimal('0') if a <= roll_width or b <= roll_width else min(Decimal('3'), (min(a, b) / roll_width).to_integral_value(rounding=ROUND_FLOOR))

    return {
        'area': area_cm2 / Decimal('10000'),
        'seam_length': 4 * c + 2 * (a + b),
        'edging_length': 2 * (a + b),
        'extra_seams': extra_seams,
        'extra_seam_length': a,
    }


def area_for_shape(shape, dimensions, fabric=None):
    class DefaultFabric:
        roll_width_cm = DEFAULT_ROLL_WIDTH

    return calculation_metrics(shape, dimensions, fabric or DefaultFabric())['area']


def round_up_to_50(value):
    return (value / Decimal('50')).to_integral_value(rounding=ROUND_CEILING) * Decimal('50')


def build_sku(shape, fabric, color, fastener, dimensions):
    shape_code = SHAPE_DEFINITIONS[shape]['sku']
    size_code = 'x'.join(str(int(item['value'])) for item in dimensions)
    return f'DT-{shape_code}-F{fabric.id}-C{color.id}-K{fastener.id}-{size_code}'


def calculate_constructor_price(payload):
    shape_key = payload.get('shape') or 'rectangular'
    shape = UI_TO_DB_SHAPE.get(shape_key, shape_key)

    if shape not in SHAPE_DEFINITIONS:
        raise ValidationError({'shape': 'Неизвестная форма чехла.'})

    formula = active_formula(shape)
    coefficient = formula.coefficient if formula else SHAPE_DEFINITIONS[shape]['default_coefficient']
    minimum_price = formula.minimum_price if formula else DEFAULT_MINIMUM_PRICE
    seam_price_cm = formula.seam_price_cm if formula else Decimal('0.00')
    topstitch_price_cm = formula.topstitch_price_cm if formula else Decimal('0.00')
    edging_price_cm = formula.edging_price_cm if formula else Decimal('0.00')
    dimensions = validate_dimensions(shape, payload.get('dimensions'))
    fabric = Fabric.objects.get(pk=payload.get('fabricId'), status=PublishStatus.ACTIVE)
    color = Color.objects.get(pk=payload.get('colorId'), status=PublishStatus.ACTIVE, fabric=fabric)
    fastener = Fastener.objects.get(pk=payload.get('fastenerId'), status=PublishStatus.ACTIVE)
    accessory_id = payload.get('accessoryId')
    accessory = Accessory.objects.filter(pk=accessory_id, status=PublishStatus.ACTIVE).first() if accessory_id else None
    quantity = int(payload.get('quantity') or 1)

    if quantity < 1:
        raise ValidationError({'quantity': 'Количество должно быть больше нуля.'})

    metrics = calculation_metrics(shape, dimensions, fabric)
    area = metrics['area']
    material_price = area * fabric.price_per_square_meter
    seam_price = metrics['seam_length'] * seam_price_cm
    edging_price = metrics['edging_length'] * edging_price_cm
    extra_seams_price = metrics['extra_seams'] * ((seam_price_cm + topstitch_price_cm) * metrics['extra_seam_length'])
    formula_price = (material_price + seam_price + edging_price + extra_seams_price) * coefficient
    options_price = color_price(color) + fastener.price + (accessory.price if accessory else Decimal('0'))
    retail_unit_price = max(minimum_price, round_up_to_50(formula_price + options_price))
    discount = Decimal('0.90') if quantity >= 8 else Decimal('1.00')
    unit_price = round_up_to_50(retail_unit_price * discount)
    total_price = unit_price * quantity
    sku = build_sku(shape, fabric, color, fastener, dimensions)

    return {
        'shape': {
            'key': SHAPE_DEFINITIONS[shape]['ui_key'],
            'dbShape': shape,
            'title': SHAPE_DEFINITIONS[shape]['title'],
            'code': SHAPE_DEFINITIONS[shape]['sku'],
        },
        'dimensions': [
            {**item, 'value': int(item['value']) if item['value'] == item['value'].to_integral() else float(item['value'])}
            for item in dimensions
        ],
        'area': float(area),
        'pricing': {
            'area': float(area),
            'seamLength': float(metrics['seam_length']),
            'edgingLength': float(metrics['edging_length']),
            'extraSeams': int(metrics['extra_seams']),
            'extraSeamLength': float(metrics['extra_seam_length']),
            'materialPrice': float(material_price),
            'seamPrice': float(seam_price),
            'edgingPrice': float(edging_price),
            'extraSeamsPrice': float(extra_seams_price),
            'optionsPrice': float(options_price),
            'coefficient': float(coefficient),
            'minimumPrice': float(minimum_price),
        },
        'fabric': {'id': fabric.id, 'name': fabric.title, 'price': float(fabric.price_per_square_meter)},
        'color': {'id': color.id, 'name': color.title, 'price': float(color_price(color)), 'image': color.image.url if color.image else ''},
        'fastener': {'id': fastener.id, 'name': fastener.title, 'price': float(fastener.price)},
        'accessory': {'id': accessory.id, 'name': accessory.title, 'price': float(accessory.price)} if accessory else None,
        'quantity': quantity,
        'unitPrice': float(unit_price),
        'totalPrice': float(total_price),
        'sku': sku,
        'formulaCode': formula.code if formula else '',
        'comments': payload.get('comments', ''),
    }


def color_price(color):
    return Decimal('0.00')
