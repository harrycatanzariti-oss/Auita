"""Draws Aiuta's icon (a white microphone on a green rounded square).

Run once when the design changes:  python installer/make_icon.py
Needs: pip install pillow
"""
from pathlib import Path

from PIL import Image, ImageDraw

GREEN = (29, 107, 87, 255)
WHITE = (255, 255, 255, 255)
HERE = Path(__file__).resolve().parent


def draw(size: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 24  # draw on a 24-unit grid, like the microphone in the app
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(5 * s), fill=GREEN)
    w = max(2, int(1.9 * s))
    d.rounded_rectangle([9 * s, 3.5 * s, 15 * s, 14 * s], radius=int(3 * s), fill=WHITE)
    d.arc([5.5 * s, 5 * s, 18.5 * s, 17 * s], start=0, end=180, fill=WHITE, width=w)
    d.line([12 * s, 17 * s, 12 * s, 20.2 * s], fill=WHITE, width=w)
    d.rounded_rectangle([8.5 * s, 19.6 * s, 15.5 * s, 19.6 * s + w], radius=w // 2, fill=WHITE)
    return img


if __name__ == "__main__":
    big = draw()
    big.save(HERE / "aiuta.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                       (128, 128), (256, 256)])
    big.resize((256, 256), Image.LANCZOS).save(HERE.parent / "aiuta" / "web" / "icon.png")
    print("Wrote installer/aiuta.ico and aiuta/web/icon.png")
