import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / 'assets' / 'image'
VIDEO_DIR = ROOT / 'assets' / 'video'
WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 8
FRAMES = FPS * DURATION


def font(size, bold=False):
    candidates = [
        Path('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf'),
        Path('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf'),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


FONT_HERO = font(92, True)
FONT_H2 = font(56, True)
FONT_BODY = font(34)
FONT_SMALL = font(26)
FONT_TINY = font(21)
FONT_BUTTON = font(28, True)


def ease(x):
    x = max(0, min(1, x))
    return x * x * (3 - 2 * x)


def pulse(t, start, end):
    if t <= start:
        return 0
    if t >= end:
        return 1
    return ease((t - start) / (end - start))


def cover_image(path, size, zoom=1.0, offset=(0, 0)):
    img = Image.open(path).convert('RGB')
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height) * zoom
    resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    x = (target_w - resized.width) // 2 + int(offset[0])
    y = (target_h - resized.height) // 2 + int(offset[1])
    canvas = Image.new('RGB', size, '#111111')
    canvas.paste(resized, (x, y))
    return canvas


def contain_image(path, size):
    img = Image.open(path).convert('RGBA')
    img.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', size, (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return canvas


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, fnt, fill, anchor='la', spacing=8):
    draw.multiline_text(xy, value, font=fnt, fill=fill, anchor=anchor, spacing=spacing)


def alpha_layer():
    return Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))


def alpha_paste(base, layer, alpha=1):
    if alpha < 1:
        a = layer.getchannel('A').point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    base.alpha_composite(layer)


def draw_scan_lines(draw, opacity=42):
    for x in range(0, WIDTH, 160):
        draw.line((x, 0, x, HEIGHT), fill=(255, 255, 255, opacity), width=1)
    for y in range(0, HEIGHT, 120):
        draw.line((0, y, WIDTH, y), fill=(255, 255, 255, opacity // 2), width=1)


def draw_header_badge(draw, label, t):
    y = 64 - int((1 - pulse(t, 0, 0.7)) * 22)
    text_box = draw.textbbox((0, 0), label, font=FONT_SMALL)
    width = max(275, text_box[2] - text_box[0] + 58)
    rounded(draw, (80, y, 80 + width, y + 58), 18, (255, 255, 255, 232))
    draw.text((108, y + 17), label, font=FONT_SMALL, fill=(18, 18, 18, 255))


def line_art_image(path, size, color=(255, 255, 255, 235)):
    img = Image.open(path).convert('RGBA')
    img.thumbnail(size, Image.Resampling.LANCZOS)
    pixels = img.load()

    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            darkness = 255 - int((r + g + b) / 3)
            if darkness > 18 and a > 0:
                pixels[x, y] = (color[0], color[1], color[2], min(color[3], int(darkness * 2.6)))
            else:
                pixels[x, y] = (0, 0, 0, 0)

    output = Image.new('RGBA', size, (0, 0, 0, 0))
    output.alpha_composite(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return output


def draw_step(draw, x, y, number, title, subtitle, active):
    fill = (255, 255, 255, int(170 + active * 70))
    rounded(draw, (x, y, x + 330, y + 128), 22, fill)
    rounded(draw, (x + 24, y + 24, x + 78, y + 78), 18, (108, 175, 216, int(120 + active * 120)))
    draw.text((x + 42, y + 38), number, font=FONT_TINY, fill=(18, 18, 18, 255))
    draw.text((x + 96, y + 28), title, font=FONT_SMALL, fill=(18, 18, 18, 255))
    draw.text((x + 96, y + 69), subtitle, font=FONT_TINY, fill=(94, 94, 94, 255))


def write_video(name, frame_func):
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    output = VIDEO_DIR / name
    cmd = [
        'ffmpeg',
        '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{WIDTH}x{HEIGHT}',
        '-pix_fmt', 'rgb24',
        '-r', str(FPS),
        '-i', '-',
        '-an',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '20',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        str(output),
    ]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for frame in range(FRAMES):
            t = frame / (FRAMES - 1)
            img = frame_func(t).convert('RGB')
            process.stdin.write(img.tobytes())
    finally:
        process.stdin.close()
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f'ffmpeg failed for {output}')
    return output


def workshop_frame(t):
    bg = cover_image(IMAGE_DIR / 'main-img.png', (WIDTH, HEIGHT), zoom=1.05 + t * 0.12, offset=(-80 * t, 0))
    bg = ImageEnhance.Brightness(bg).enhance(0.46)
    frame = bg.convert('RGBA')
    overlay = alpha_layer()
    d = ImageDraw.Draw(overlay)
    draw_scan_lines(d, 28)
    draw_header_badge(d, 'DiTent / процесс', t)

    title_alpha = pulse(t, 0.02, 0.18)
    title_layer = alpha_layer()
    td = ImageDraw.Draw(title_layer)
    text(td, (80, 180), 'От замера\nдо готового чехла', FONT_HERO, (255, 255, 255, 255))
    text(td, (84, 398), 'Понятный путь заказа: заявка, расчет, пошив и доставка.', FONT_BODY, (235, 235, 235, 255))
    alpha_paste(overlay, title_layer, title_alpha)

    line_progress = pulse(t, 0.22, 0.64)
    d.line((955, 285, 955 + int(700 * line_progress), 285), fill=(108, 175, 216, 220), width=5)
    d.line((955, 545, 955 + int(585 * line_progress), 545), fill=(255, 255, 255, 180), width=3)
    for x, y, label in [(955, 245, 'A'), (1655, 245, 'B'), (1540, 505, 'H')]:
        rounded(d, (x - 24, y - 24, x + 24, y + 24), 14, (255, 255, 255, int(170 + 60 * line_progress)))
        d.text((x - 8, y - 14), label, font=FONT_TINY, fill=(18, 18, 18, 255))

    cover = alpha_layer()
    cd = ImageDraw.Draw(cover)
    x = 1100 + int(math.sin(t * math.pi * 2) * 8)
    y = 375 - int(pulse(t, 0.35, 0.68) * 28)
    cd.rounded_rectangle((x, y, x + 390, y + 270), radius=58, fill=(108, 175, 216, 76), outline=(255, 255, 255, 170), width=4)
    cd.arc((x + 25, y - 35, x + 365, y + 160), 180, 360, fill=(255, 255, 255, 175), width=4)
    cd.line((x + 54, y + 188, x + 338, y + 188), fill=(255, 255, 255, 155), width=3)
    alpha_paste(overlay, cover, pulse(t, 0.24, 0.42))

    base_y = 812
    steps = [
        ('01', 'Заявка', 'размеры и форма'),
        ('02', 'Расчет', 'материал и цена'),
        ('03', 'Пошив', 'изготовление'),
        ('04', 'Доставка', 'готовый заказ'),
    ]
    for i, item in enumerate(steps):
        active = pulse(t, 0.18 + i * 0.13, 0.33 + i * 0.13)
        draw_step(d, 80 + i * 360, base_y, *item, active)
    alpha_paste(frame, overlay)
    return frame


def order_frame(t):
    frame = Image.new('RGBA', (WIDTH, HEIGHT), '#edf4f7')
    d = ImageDraw.Draw(frame)
    for i in range(5):
        x = int((i * 340 - t * 150) % (WIDTH + 220)) - 120
        y = 130 + i % 3 * 150
        if x < 1160:
            d.rounded_rectangle((x, y, x + 170, y + 104), radius=26, fill=(255, 255, 255, 70))

    browser = alpha_layer()
    bd = ImageDraw.Draw(browser)
    bx, by, bw, bh = 115, 130, 1080, 720
    rounded(bd, (bx, by, bx + bw, by + bh), 28, (255, 255, 255, 255))
    rounded(bd, (bx, by, bx + bw, by + 78), 28, (247, 247, 247, 255))
    for i, color in enumerate([(238, 98, 98), (238, 184, 90), (86, 178, 116)]):
        bd.ellipse((bx + 36 + i * 34, by + 28, bx + 52 + i * 34, by + 44), fill=color)
    bd.text((bx + 64, by + 112), 'Конструктор чехла', font=FONT_H2, fill=(18, 18, 18, 255))
    shape = contain_image(IMAGE_DIR / 'item-img-1.png', (390, 280))
    browser.alpha_composite(shape, (bx + 56, by + 260))

    fill = pulse(t, 0.1, 0.76)
    fields = [('Ширина A', '120'), ('Глубина B', '90'), ('Высота H', '70')]
    for i, (label, value) in enumerate(fields):
        fy = by + 230 + i * 100
        bd.text((bx + 520, fy), label, font=FONT_TINY, fill=(90, 90, 90, 255))
        rounded(bd, (bx + 520, fy + 36, bx + 940, fy + 88), 14, (245, 245, 245, 255))
        bd.text((bx + 548, fy + 49), value[:max(0, min(len(value), int((fill - i * .16) * 8)))], font=FONT_SMALL, fill=(18, 18, 18, 255))

    price_alpha = pulse(t, 0.52, 0.72)
    rounded(bd, (bx + 520, by + 565, bx + 940, by + 645), 18, (18, 18, 18, int(80 + 175 * price_alpha)))
    bd.text((bx + 565, by + 586), '4 850 руб.', font=FONT_BUTTON, fill=(255, 255, 255, int(255 * price_alpha)))
    alpha_paste(frame, browser)

    side = alpha_layer()
    sd = ImageDraw.Draw(side)
    text(sd, (1245, 154), 'Клиент видит\nрасчет сразу', font(82, True), (18, 18, 18, 255))
    text(sd, (1249, 360), 'После оформления менеджер\nпроверяет параметры и\nподтверждает оплату.', FONT_SMALL, (80, 80, 80, 255), spacing=8)
    steps = ['Форма', 'Материал', 'Цена', 'Заказ']
    for i, label in enumerate(steps):
        y = 600 + i * 76
        active = pulse(t, 0.18 + i * 0.14, 0.34 + i * 0.14)
        rounded(sd, (1245, y, 1665, y + 52), 16, (255, 255, 255, 230))
        sd.rectangle((1245, y, 1245 + int(420 * active), y + 52), fill=(108, 175, 216, 130))
        sd.text((1270, y + 12), label, font=FONT_SMALL, fill=(18, 18, 18, 255))
    alpha_paste(frame, side)
    cursor_x = 770 + int(math.sin(t * math.pi * 2) * 45)
    cursor_y = 690 - int(pulse(t, 0.54, 0.7) * 95)
    d.ellipse((cursor_x, cursor_y, cursor_x + 32, cursor_y + 32), fill=(108, 175, 216, 255))
    return frame


def blueprint_frame(t):
    frame = Image.new('RGBA', (WIDTH, HEIGHT), '#101820')
    d = ImageDraw.Draw(frame)
    for x in range(0, WIDTH, 48):
        d.line((x, 0, x, HEIGHT), fill=(255, 255, 255, 20), width=1)
    for y in range(0, HEIGHT, 48):
        d.line((0, y, WIDTH, y), fill=(255, 255, 255, 20), width=1)
    draw_header_badge(d, 'индивидуальный расчет', t)
    text(d, (80, 170), 'Чертеж превращается\nв готовый чехол', FONT_HERO, (255, 255, 255, 255))

    panel = alpha_layer()
    pd = ImageDraw.Draw(panel)
    rounded(pd, (92, 470, 850, 900), 28, (255, 255, 255, 22), (108, 175, 216, 150), 2)
    drawing = line_art_image(IMAGE_DIR / 'item-img-5.png', (640, 320))
    panel.alpha_composite(drawing, (150, 535))
    alpha_paste(frame, panel, pulse(t, 0.08, 0.28))

    measures = [('A 240 см', 205, 500, .22), ('B 150 см', 650, 610, .34), ('H 80 см', 355, 850, .46)]
    for label, x, y, start in measures:
        a = pulse(t, start, start + .16)
        tag = alpha_layer()
        td = ImageDraw.Draw(tag)
        rounded(td, (x, y, x + 180, y + 52), 18, (108, 175, 216, int(70 + 160 * a)), (255, 255, 255, int(160 * a)), 2)
        td.text((x + 24, y + 14), label, font=FONT_TINY, fill=(255, 255, 255, int(255 * a)))
        alpha_paste(frame, tag)

    right = alpha_layer()
    rd = ImageDraw.Draw(right)
    rx = 1060
    rounded(rd, (rx, 250, 1740, 845), 28, (255, 255, 255, 245))
    img = cover_image(IMAGE_DIR / 'review-img.png', (610, 300), zoom=1.08 + t * .03)
    right.alpha_composite(img.convert('RGBA'), (rx + 35, 290))
    rd.text((rx + 52, 640), 'Готовое изделие', font=FONT_H2, fill=(18, 18, 18, 255))
    rd.text((rx + 56, 710), 'точная посадка по размерам', font=FONT_BODY, fill=(90, 90, 90, 255))
    alpha_paste(frame, right, pulse(t, 0.58, 0.78))
    return frame


def material_frame(t):
    bg = Image.new('RGBA', (WIDTH, HEIGHT), '#f3f1ee')
    d = ImageDraw.Draw(bg)
    d.rectangle((0, 0, WIDTH, HEIGHT), fill=(243, 241, 238, 255))
    text(d, (80, 98), 'Материал, швы\nи чистая посадка', FONT_HERO, (18, 18, 18, 255))
    text(d, (84, 316), 'Видео с акцентом на качество изготовления и фактуру ткани.', FONT_BODY, (82, 82, 82, 255))

    roll = cover_image(IMAGE_DIR / 'material-img-3.png', (640, 620), zoom=1.35, offset=(int(t * 90), 0)).convert('RGBA')
    mask = Image.new('L', (640, 620), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, 640, 620), radius=34, fill=255)
    roll.putalpha(mask)
    bg.alpha_composite(roll, (80, 405))

    cut = alpha_layer()
    cd = ImageDraw.Draw(cut)
    cx, cy = 830, 360
    offset = int((1 - pulse(t, .18, .42)) * -160)
    polygon = [(cx + offset, cy + 70), (cx + 640 + offset, cy + 30), (cx + 575 + offset, cy + 475), (cx + 75 + offset, cy + 430)]
    cd.polygon(polygon, fill=(56, 63, 69, 250))
    cd.line(polygon + [polygon[0]], fill=(255, 255, 255, 155), width=4)
    for i in range(13):
        x = cx + 88 + i * 39 + offset
        cd.line((x, cy + 440, x + 22, cy + 440), fill=(108, 175, 216, 230), width=6)
    alpha_paste(bg, cut)

    ready = alpha_layer()
    rd = ImageDraw.Draw(ready)
    rr = pulse(t, .56, .78)
    rounded(rd, (1230, 130, 1780, 520), 32, (255, 255, 255, int(245 * rr)))
    photo = cover_image(IMAGE_DIR / 'catalog-img-1.png', (490, 250), zoom=1.06).convert('RGBA')
    ready.alpha_composite(photo, (1260, 160))
    rd.text((1260, 438), 'Готово к отправке', font=FONT_H2, fill=(18, 18, 18, int(255 * rr)))
    alpha_paste(bg, ready)

    tags = ['Влагостойкая ткань', 'Усиленный шов', 'Размер в размер']
    for i, label in enumerate(tags):
        a = pulse(t, .3 + i * .12, .48 + i * .12)
        x = 900 + i * 285
        y = 860
        rounded(d, (x, y, x + 250, y + 72), 18, (255, 255, 255, int(245 * a)))
        d.text((x + 24, y + 21), label, font=FONT_TINY, fill=(18, 18, 18, int(255 * a)))
    return bg


def main():
    outputs = [
        write_video('home-process-workshop.mp4', workshop_frame),
        write_video('home-process-order.mp4', order_frame),
        write_video('home-process-blueprint.mp4', blueprint_frame),
        write_video('home-process-material.mp4', material_frame),
    ]
    for output in outputs:
        print(output.relative_to(ROOT))


if __name__ == '__main__':
    main()
