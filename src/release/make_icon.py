"""Generates src/assets/holokeyboard.ico (a plain keyboard glyph in the HUD's cyan-on-navy colors).

Pure standard library (zlib + struct); run once, the .ico is committed:
    python -B src/release/make_icon.py
"""
import struct
import zlib
from pathlib import Path

NAVY, CYAN, DIM = (10, 17, 24, 255), (0, 216, 255, 255), (0, 130, 170, 255)
CLEAR = (0, 0, 0, 0)


def render(size):
    """size x size RGBA: rounded navy plate with a 3-row keyboard drawn as double-bordered keys."""
    px = [[CLEAR] * size for _ in range(size)]
    s = size / 64.0
    radius = max(2, round(10 * s))

    def inside_plate(x, y):
        cx = min(max(x, radius), size - 1 - radius)
        cy = min(max(y, radius), size - 1 - radius)
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius

    for y in range(size):
        for x in range(size):
            if inside_plate(x, y):
                px[y][x] = NAVY

    def rect(x0, y0, x1, y1, color, fill=False):
        x0, y0, x1, y1 = (round(v * s) for v in (x0, y0, x1, y1))
        x1, y1 = max(x1, x0 + 1), max(y1, y0 + 1)
        for y in range(y0, min(y1, size)):
            for x in range(x0, min(x1, size)):
                edge = x in (x0, x1 - 1) or y in (y0, y1 - 1)
                if fill or edge:
                    px[y][x] = color

    rows = ((13, 6), (22, 5), (31, 5))            # (top, keys per row)
    key_w, key_h, gap = 6.0, 6.5, 1.6
    for top, count in rows:
        total = count * key_w + (count - 1) * gap
        x = (64 - total) / 2
        for _ in range(count):
            rect(x, top, x + key_w, top + key_h, CYAN)
            if size >= 32:
                rect(x + 1.4, top + 1.4, x + key_w - 1.4, top + key_h - 1.4, DIM)
            x += key_w + gap
    rect(14, 41, 50, 48, CYAN)                    # space bar
    if size >= 32:
        rect(15.4, 42.4, 48.6, 46.6, DIM)
    return px


def png(px, size):
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in px)

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    sizes = (16, 24, 32, 48, 64, 256)
    images = [png(render(n), n) for n in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for n, data in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    out = Path(__file__).resolve().parent.parent / "assets" / "holokeyboard.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(header + entries + b"".join(images))
    print("wrote", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
