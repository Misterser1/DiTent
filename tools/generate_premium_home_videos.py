from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "assets" / "video"
SOURCE_DIR = VIDEO_DIR / "source"
OVERLAY_DIR = VIDEO_DIR / "overlays"
POSTER_DIR = VIDEO_DIR / "posters"

WIDTH = 1920
HEIGHT = 1080


def font_path(name: str) -> str:
    candidates = [
        Path("C:/Windows/Fonts") / name,
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("No suitable system font found")


FONT_REGULAR = font_path("segoeui.ttf")
FONT_MEDIUM = font_path("seguisb.ttf")
FONT_BOLD = font_path("segoeuib.ttf")


def f(size: int, bold: bool = False, medium: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_MEDIUM if medium else FONT_REGULAR, size)


def rounded(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], radius: int, fill, outline=None, width: int = 1) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, size: int, fill, bold: bool = False, medium: bool = False) -> None:
    draw.text(xy, value, font=f(size, bold=bold, medium=medium), fill=fill)


def shadowed_card(base: Image.Image, box: tuple[int, int, int, int], radius: int = 22, fill=(255, 255, 255, 218)) -> ImageDraw.ImageDraw:
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(box, radius=radius, fill=(0, 0, 0, 72))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    base.alpha_composite(shadow)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(box, radius=radius, fill=fill)
    return draw


def base_overlay(strength: int = 135) -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    px = img.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            left = max(0, int(strength * (1 - x / 980)))
            bottom = max(0, int(72 * (y / HEIGHT) ** 2))
            px[x, y] = (5, 9, 12, max(left, bottom))
    return img


def save_title_overlay(path: Path, eyebrow: str, title: str, subtitle: str, steps: list[str] | None = None) -> None:
    img = base_overlay(155)
    draw = ImageDraw.Draw(img)
    text(draw, (118, 112), "DiTent", 32, (255, 255, 255, 225), bold=True)
    draw.line((118, 162, 215, 162), fill=(108, 175, 216, 255), width=5)
    text(draw, (118, 676), eyebrow.upper(), 24, (108, 175, 216, 255), medium=True)
    text(draw, (116, 720), title, 74, (255, 255, 255, 248), medium=True)
    text(draw, (122, 820), subtitle, 34, (255, 255, 255, 220))

    if steps:
        x = 120
        y = 904
        for index, step in enumerate(steps, start=1):
            rounded(draw, (x, y, x + 50, y + 50), 25, (108, 175, 216, 235))
            text(draw, (x + 17, y + 10), str(index), 24, (255, 255, 255, 255), bold=True)
            text(draw, (x + 66, y + 11), step, 24, (255, 255, 255, 230), medium=True)
            x += 285
    img.save(path)


def save_order_overlay(path: Path) -> None:
    img = base_overlay(105)
    draw = ImageDraw.Draw(img)
    text(draw, (118, 112), "DiTent", 32, (255, 255, 255, 225), bold=True)
    text(draw, (118, 692), "Путь заказа", 26, (108, 175, 216, 255), medium=True)
    text(draw, (116, 736), "От заявки до готового изделия", 66, (255, 255, 255, 248), medium=True)
    text(draw, (122, 830), "Форма, расчет, подтверждение менеджером и производство.", 31, (255, 255, 255, 220))

    draw = shadowed_card(img, (1090, 164, 1710, 850), radius=28, fill=(255, 255, 255, 232))
    text(draw, (1142, 218), "Заказ по размерам", 34, (18, 18, 18, 255), medium=True)
    text(draw, (1142, 278), "Калькулятор", 22, (120, 120, 120, 255))
    items = [
        ("Форма", "П-образная"),
        ("Размеры", "A 320  B 180  H 210"),
        ("Материал", "ПВХ 650 г/м2"),
        ("Статус", "На проверке"),
    ]
    y = 336
    for label, value in items:
        rounded(draw, (1142, y, 1658, y + 66), 16, (246, 248, 250, 255))
        text(draw, (1170, y + 17), label, 22, (112, 112, 112, 255))
        text(draw, (1372, y + 17), value, 22, (16, 16, 16, 255), medium=True)
        y += 84
    rounded(draw, (1142, 724, 1512, 790), 18, (18, 18, 18, 255))
    text(draw, (1182, 741), "Отправить на расчет", 24, (255, 255, 255, 255), medium=True)
    rounded(draw, (1528, 724, 1658, 790), 18, (108, 175, 216, 255))
    text(draw, (1569, 741), "OK", 24, (255, 255, 255, 255), bold=True)
    img.save(path)


def save_detail_overlay(path: Path) -> None:
    img = base_overlay(118)
    draw = ImageDraw.Draw(img)
    text(draw, (118, 112), "DiTent", 32, (255, 255, 255, 225), bold=True)
    text(draw, (118, 708), "Материал и пошив", 26, (108, 175, 216, 255), medium=True)
    text(draw, (116, 752), "Акцент на детали", 70, (255, 255, 255, 248), medium=True)
    text(draw, (122, 846), "Крупные планы, фактура ткани, аккуратная строчка.", 32, (255, 255, 255, 220))

    x = 122
    y = 918
    for value in ["плотная ткань", "усиленный шов", "индивидуальный размер"]:
        w = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(value, font=f(24, medium=True))) + 48
        rounded(draw, (x, y, x + w, y + 48), 24, (255, 255, 255, 42), outline=(255, 255, 255, 90))
        text(draw, (x + 24, y + 10), value, 24, (255, 255, 255, 230), medium=True)
        x += w + 18
    img.save(path)


@dataclass(frozen=True)
class Scene:
    source: str
    start: float
    duration: float


@dataclass(frozen=True)
class VideoSpec:
    name: str
    title: str
    scenes: list[Scene]
    overlays: list[tuple[str, float, float]]


def run(command: list[str]) -> None:
    print(" ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)


def video_filter(index: int, scene: Scene) -> str:
    return (
        f"[{index}:v]trim=start={scene.start}:duration={scene.duration},"
        "setpts=PTS-STARTPTS,"
        "scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,fps=30,setsar=1,"
        "eq=contrast=1.08:saturation=0.88:brightness=-0.025,"
        "unsharp=5:5:0.45:3:3:0.18,format=yuv420p"
        f"[v{index}]"
    )


def build_video(spec: VideoSpec) -> None:
    output = VIDEO_DIR / f"{spec.name}.mp4"
    poster = POSTER_DIR / f"{spec.name}.jpg"
    input_args: list[str] = []
    for scene in spec.scenes:
        input_args.extend(["-i", str(SOURCE_DIR / scene.source)])
    for overlay_name, _, _ in spec.overlays:
        input_args.extend(["-loop", "1", "-i", str(OVERLAY_DIR / overlay_name)])

    filters: list[str] = [video_filter(i, scene) for i, scene in enumerate(spec.scenes)]
    previous = "[v0]"
    elapsed = spec.scenes[0].duration
    for i in range(1, len(spec.scenes)):
        offset = elapsed - 0.42
        output_label = f"[x{i}]"
        filters.append(f"{previous}[v{i}]xfade=transition=fade:duration=0.42:offset={offset:.2f}{output_label}")
        previous = output_label
        elapsed = elapsed + spec.scenes[i].duration - 0.42

    overlay_input_start = len(spec.scenes)
    for i, (_, start, end) in enumerate(spec.overlays):
        filters.append(f"[{overlay_input_start + i}:v]format=rgba[ov{i}]")
        output_label = f"[o{i}]"
        filters.append(f"{previous}[ov{i}]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'{output_label}")
        previous = output_label

    duration = min(elapsed, max((end for _, _, end in spec.overlays), default=elapsed))
    command = [
        "ffmpeg",
        "-y",
        *input_args,
        "-filter_complex",
        ";".join(filters),
        "-map",
        previous,
        "-t",
        f"{duration:.2f}",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    run(command)
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "00:00:03.000",
            "-i",
            str(output),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(poster),
        ]
    )


def main() -> None:
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    POSTER_DIR.mkdir(parents=True, exist_ok=True)

    save_title_overlay(
        OVERLAY_DIR / "premium-craft-title.png",
        "Производство",
        "Чехлы и тенты под размер",
        "Живой процесс: расчет, раскрой, пошив и проверка деталей.",
        ["заявка", "размеры", "пошив", "готово"],
    )
    save_order_overlay(OVERLAY_DIR / "premium-order-flow.png")
    save_detail_overlay(OVERLAY_DIR / "premium-detail.png")

    specs = [
        VideoSpec(
            name="home-hero-craft",
            title="Hero фон без титров",
            scenes=[
                Scene("sewing-machine.mp4", 0.8, 4.2),
                Scene("hand-sewing.mp4", 2.3, 4.2),
                Scene("woman-sewing.mp4", 3.0, 4.2),
                Scene("sewing-closeup.mp4", 7.0, 4.2),
            ],
            overlays=[],
        ),
        VideoSpec(
            name="home-premium-craft",
            title="Производство и пошив",
            scenes=[
                Scene("sewing-machine.mp4", 0.8, 4.2),
                Scene("hand-sewing.mp4", 2.3, 4.2),
                Scene("woman-sewing.mp4", 3.0, 4.2),
                Scene("sewing-closeup.mp4", 7.0, 4.2),
            ],
            overlays=[("premium-craft-title.png", 0.0, 14.8)],
        ),
        VideoSpec(
            name="home-premium-order-flow",
            title="Заказ по размерам",
            scenes=[
                Scene("woman-sewing.mp4", 1.0, 4.4),
                Scene("sewing-machine.mp4", 2.2, 4.4),
                Scene("hand-sewing.mp4", 5.5, 4.4),
            ],
            overlays=[("premium-order-flow.png", 0.0, 12.4)],
        ),
        VideoSpec(
            name="home-premium-detail",
            title="Материал крупным планом",
            scenes=[
                Scene("sewing-closeup.mp4", 2.8, 4.2),
                Scene("hand-sewing.mp4", 6.0, 4.2),
                Scene("sewing-machine.mp4", 5.8, 4.2),
            ],
            overlays=[("premium-detail.png", 0.0, 12.0)],
        ),
    ]

    for spec in specs:
        build_video(spec)


if __name__ == "__main__":
    main()
