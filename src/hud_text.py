"""Single-color Win32 text masks for a color-keyed Canvas."""
import ctypes as c
import struct
import tkinter as tk
import zlib
from ctypes import wintypes as w
from functools import lru_cache

gdi = c.WinDLL("gdi32", use_last_error=True)
user = c.WinDLL("user32", use_last_error=True)


def bind(module, name, result, *arguments):
    function = getattr(module, name)
    function.restype, function.argtypes = result, arguments
    return function


create_dc = bind(gdi, "CreateCompatibleDC", w.HDC, w.HDC)
delete_dc = bind(gdi, "DeleteDC", w.BOOL, w.HDC)
select = bind(gdi, "SelectObject", w.HANDLE, w.HDC, w.HANDLE)
delete = bind(gdi, "DeleteObject", w.BOOL, w.HANDLE)
font = bind(gdi, "CreateFontW", w.HANDLE, *([c.c_int]*5), *([w.DWORD]*8), w.LPCWSTR)
dib = bind(gdi, "CreateDIBSection", w.HANDLE, w.HDC, c.c_void_p, w.UINT,
           c.POINTER(c.c_void_p), w.HANDLE, w.DWORD)
black = bind(gdi, "PatBlt", w.BOOL, w.HDC, c.c_int, c.c_int, c.c_int, c.c_int, w.DWORD)
set_color = bind(gdi, "SetTextColor", w.DWORD, w.HDC, w.DWORD)
set_background = bind(gdi, "SetBkMode", c.c_int, w.HDC, c.c_int)
draw = bind(user, "DrawTextW", c.c_int, w.HDC, w.LPCWSTR, c.c_int,
            c.POINTER(w.RECT), w.UINT)


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag+data))


@lru_cache(maxsize=256)
def label_image(root, text, size, color, weight=400, max_width=None, contrast_outline=False):
    rgb = bytes.fromhex(color[1:])
    dc = create_dc(None)
    # NONANTIALIASED_QUALITY keeps every visible pixel the chosen color.
    face = font(-size, 0, 0, 0, weight, 0, 0, 0, 1, 0, 0, 3, 0, "Malgun Gothic")
    if not (dc and face):
        if face:
            delete(face)
        if dc:
            delete_dc(dc)
        raise OSError("Could not create a HUD font or drawing context")
    original_font = select(dc, face)
    bitmap = old_bitmap = None
    try:
        mode = 0x820  # DT_NOPREFIX | DT_SINGLELINE
        bounds = w.RECT()
        draw(dc, text, -1, c.byref(bounds), mode | 0x400)
        width, height = max(1, bounds.right+4), max(1, bounds.bottom+2)
        if max_width and width > max_width:
            width = max_width
            mode |= 0x8000  # DT_END_ELLIPSIS
        info = c.create_string_buffer(struct.pack("<IiiHHIIiiII", 40, width, -height, 1,
                                                  32, 0, 0, 0, 0, 0, 0))
        pixels = c.c_void_p()
        bitmap = dib(dc, info, 0, c.byref(pixels), None, 0)
        if not bitmap:
            raise OSError("Could not create a HUD text mask")
        old_bitmap = select(dc, bitmap)
        black(dc, 0, 0, width, height, 0x42)
        set_color(dc, 0xffffff)
        set_background(dc, 1)
        bounds = w.RECT(2, 1, width-2, height)
        draw(dc, text, -1, c.byref(bounds), mode)
        gdi.GdiFlush()
        mask = c.string_at(pixels, width*height*4)
    finally:
        if old_bitmap:
            select(dc, old_bitmap)
        if bitmap:
            delete(bitmap)
        select(dc, original_font)
        delete(face)
        delete_dc(dc)
    transparent, ink, edge = b"\0"*4, rgb+b"\xff", b"\x10\x10\x10\xff"
    # Only the pixels bordering the white glyph receive a dark outline.
    glyph = mask[::4]
    pixels_rgba = bytearray()
    for y in range(height):
        pixels_rgba.append(0)
        for x in range(width):
            pos = y*width+x
            if glyph[pos] >= 128:
                pixels_rgba.extend(ink)
            elif contrast_outline and any(
                glyph[ny*width+nx] >= 128
                for ny in range(max(0, y-1), min(height, y+2))
                for nx in range(max(0, x-1), min(width, x+2))
            ):
                pixels_rgba.extend(edge)
            else:
                pixels_rgba.extend(transparent)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", header)+
           chunk(b"IDAT", zlib.compress(pixels_rgba))+chunk(b"IEND", b""))
    return tk.PhotoImage(master=root, data=png, format="png")
