"""
Génère les icônes PNG de la PWA (bouclier SafeRoad) sans dépendance : python scripts/make_icons.py
Sortie : public/icons/icon-192.png, icon-512.png, maskable-512.png, apple-touch-icon.png
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "public" / "icons"
BG = (42, 120, 214)       # --accent-strong
PAGE = (13, 17, 23)       # --page
WHITE = (240, 239, 236)   # --ink


def png(path: Path, size: int, pixels) -> None:
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in pixels)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(data)


def inside_shield(x: float, y: float) -> bool:
    """Bouclier dans le carré unité (0..1), pointe en bas."""
    if y < 0.12 or y > 0.9:
        return False
    if y <= 0.55:
        half = 0.33 - 0.06 * max(0.0, (0.2 - y)) / 0.08
        return abs(x - 0.5) <= half
    # partie basse : se resserre jusqu'à la pointe
    t = (y - 0.55) / 0.35
    return abs(x - 0.5) <= 0.33 * (1 - t ** 1.6)


def inside_cross(x: float, y: float) -> bool:
    return (abs(x - 0.5) <= 0.045 and 0.3 <= y <= 0.66) or (abs(y - 0.5) <= 0.045 and 0.37 <= x <= 0.63)


def render(size: int, maskable: bool = False):
    radius = 0 if maskable else 0.22
    scale = 0.62 if maskable else 0.8  # zone de sécurité des icônes « maskable »
    rows = []
    ss = 3  # suréchantillonnage pour lisser les bords
    for j in range(size):
        row = []
        for i in range(size):
            acc = [0, 0, 0, 0]
            for sj in range(ss):
                for si in range(ss):
                    u, v = (i + (si + .5) / ss) / size, (j + (sj + .5) / ss) / size
                    # coin arrondi du fond
                    dx, dy = max(radius - u, 0, u - (1 - radius)), max(radius - v, 0, v - (1 - radius))
                    if radius and dx * dx + dy * dy > radius * radius:
                        continue
                    sx, sy = (u - 0.5) / scale + 0.5, (v - 0.5) / scale + 0.5
                    if inside_cross(sx, sy) and inside_shield(sx, sy):
                        color = BG
                    elif inside_shield(sx, sy):
                        color = WHITE
                    else:
                        color = BG if not maskable else BG
                    acc[0] += color[0]; acc[1] += color[1]; acc[2] += color[2]; acc[3] += 255
            n = ss * ss
            row.append((acc[0] // n, acc[1] // n, acc[2] // n, acc[3] // n) if acc[3] else (*PAGE, 0))
        rows.append(row)
    return rows


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, mask in [("icon-192.png", 192, False), ("icon-512.png", 512, False),
                             ("maskable-512.png", 512, True), ("apple-touch-icon.png", 180, True)]:
        png(OUT / name, size, render(size, mask))
        print(OUT / name)
