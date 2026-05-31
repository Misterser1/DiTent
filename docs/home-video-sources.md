# Источники видео для главной

Собранные ролики лежат в `assets/video/`:

- `home-hero-craft.mp4` - чистая версия для hero-фона без встроенных титров.
- `home-premium-craft.mp4` - производство и пошив.
- `home-premium-order-flow.mp4` - заказ по размерам.
- `home-premium-detail.mp4` - материал и детали.

Исходные фрагменты лежат в `assets/video/source/`. Для монтажа использованы бесплатные видео Pexels:

- Sewing machine close-up: https://www.pexels.com/video/close-up-of-a-person-using-a-sewing-machine-7998316/
- Woman sewing a fabric: https://www.pexels.com/video/woman-sewing-a-fabric-7204571/
- Hand sewing source file: https://videos.pexels.com/video-files/7292560/7292560-hd_1920_1080_24fps.mp4
- Textile close-up source file: https://videos.pexels.com/video-files/11716399/11716399-hd_1920_1080_24fps.mp4

Лицензия Pexels: https://www.pexels.com/license/

Сборка роликов воспроизводится командой:

```powershell
python tools\generate_premium_home_videos.py
```
