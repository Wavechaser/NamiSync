"""Explicit artwork maintenance only; review the ICO before committing it.

Requires resvg-py and Pillow. Never called by builds or tests.
"""

from io import BytesIO
from pathlib import Path

from PIL import Image
from resvg_py import svg_to_bytes


if __name__ == "__main__":
    branding = Path(__file__).resolve().parents[2] / "namisync/interfaces/branding"
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    frames = [Image.open(BytesIO(svg_to_bytes(
        svg_path=str(branding / "namisync_icon_color.svg"),
        width=size, height=size,
    ))).convert("RGBA") for size in sizes]
    frames[-1].save(
        branding / "namisync.ico", sizes=[(n, n) for n in sizes],
        append_images=frames[:-1],
    )
