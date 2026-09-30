from __future__ import annotations

from PIL import Image

_BORDER_THRESHOLD = 16


def trim_borders(image: Image.Image) -> Image.Image:
    """Crops near-black letterbox/pillarbox bars so the same clip hashes alike across platforms."""
    gray = image.convert("L")
    bbox = gray.point(lambda p: 255 if p > _BORDER_THRESHOLD else 0).getbbox()

    if not bbox:
        return image

    return image.crop(bbox)


def dhash(
    image: Image.Image,
    hash_size: int = 8,
) -> str:
    """Difference hash: hash_size² bits as hex. Robust to rescaling and recompression, not to crops/overlays."""
    gray = trim_borders(image).convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(gray.tobytes())
    bits = 0

    for row in range(hash_size):
        for col in range(hash_size):
            left = pixels[row * (hash_size + 1) + col]
            right = pixels[row * (hash_size + 1) + col + 1]
            bits = (bits << 1) | int(left > right)

    return f"{bits:0{hash_size * hash_size // 4}x}"
