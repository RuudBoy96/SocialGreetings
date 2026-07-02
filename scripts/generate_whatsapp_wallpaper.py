"""Generate a soft, barely-cream WhatsApp-style wallpaper preview."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "img" / "whatsapp-wallpaper.png"
PREVIEW = ROOT / "static" / "img" / "whatsapp-wallpaper-preview.png"
COMPARISON = ROOT / "static" / "img" / "whatsapp-wallpaper-comparison.png"

SRC_LUM_MIN = 222.0
SRC_LUM_MAX = 253.0

# Whisper of cream — warm white base, soft bright line tones
OUT_BG = (254, 253, 250)
OUT_LINE = (218, 215, 208)

# Push mids toward background so fewer pixels read as line (thinner look)
LINE_CURVE = 1.42
LINE_FLOOR = 0.26


def luminance(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def line_strength(r: int, g: int, b: int) -> float:
    span = SRC_LUM_MAX - SRC_LUM_MIN
    t = max(0.0, min(1.0, (luminance(r, g, b) - SRC_LUM_MIN) / span))
    t = t**LINE_CURVE
    strength = 1.0 - t
    if strength <= LINE_FLOOR:
        return 0.0
    return min(1.0, (strength - LINE_FLOOR) / (1.0 - LINE_FLOOR))


def blend_cream(strength: float) -> tuple[int, int, int]:
    s = max(0.0, min(1.0, strength))
    return (
        int(OUT_BG[0] + s * (OUT_LINE[0] - OUT_BG[0])),
        int(OUT_BG[1] + s * (OUT_LINE[1] - OUT_BG[1])),
        int(OUT_BG[2] + s * (OUT_LINE[2] - OUT_BG[2])),
    )


def thin_strength_map(strengths: list[float], size: tuple[int, int]) -> list[float]:
    """Erode line regions slightly so doodles read a touch finer."""
    w, h = size
    mask = Image.new("L", size)
    mask.putdata([int(round(s * 255)) for s in strengths])
    mask = mask.filter(ImageFilter.MinFilter(3))
    thinned = [v / 255.0 for v in mask.getdata()]
    # Blend back a little so lines do not disappear entirely
    return [s * 0.82 + t * 0.18 for s, t in zip(strengths, thinned)]


def recolor_image(img: Image.Image) -> Image.Image:
    src = img.convert("RGB")
    size = src.size
    strengths = [line_strength(*px) for px in src.getdata()]
    strengths = thin_strength_map(strengths, size)
    out = Image.new("RGB", size)
    out.putdata([blend_cream(s) for s in strengths])
    return out


def make_comparison(before: Image.Image, after: Image.Image) -> Image.Image:
    w, h = before.size
    strip = Image.new("RGB", (w * 2 + 24, h + 40), (255, 255, 255))
    strip.paste(before, (0, 40))
    strip.paste(after, (w + 24, 40))
    return strip


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing source wallpaper: {SRC}")

    img = Image.open(SRC)
    preview = recolor_image(img)
    preview.save(PREVIEW, optimize=True)
    make_comparison(img.convert("RGB"), preview).save(COMPARISON, optimize=True)
    print(f"Preview saved: {PREVIEW}")
    print(f"Comparison saved: {COMPARISON}")
    print(f"BG {OUT_BG}  lines {OUT_LINE}")


if __name__ == "__main__":
    main()
