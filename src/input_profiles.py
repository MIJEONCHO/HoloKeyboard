"""Read Windows keyboard profiles and derive key legends without changing keyboard state."""
import ctypes as c
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import win_native as n
from v8_layout import LAYOUTS

w = n.w


@dataclass(frozen=True)
class Profile:
    code: str
    layout_id: int
    name: str
    tip: tuple[str, str] | None = None


PROFILES = {p.code: p for p in (
    Profile("KR", 0x0412, "Korean (00000412) — Microsoft IME, modern Hangul scope",
            ("a028ae76-01b1-46c2-99c4-acd9858ae02f", "b5fe1f02-d5f2-4445-9c03-c568f23c99a1")),
    Profile("EN", 0x0409, "US QWERTY (00000409)"),
    Profile("JP", 0x0411, "Microsoft Japanese IME — Romaji scope",
            ("03b5835f-f03c-411b-9ce2-aa23e1171e36", "a76c93d9-5523-4e90-aafa-4db112f9ac76")),
    Profile("CN", 0x0804, "Microsoft Pinyin — Simplified Chinese, US base",
            ("81d4e9c9-1d3b-41bc-9e6c-4b40bf79e35e", "fa550b04-5ad7-411f-a5ac-ca038ec515d7")),
    Profile("VN", 0x042a, "Vietnamese (0000042A)"),
    Profile("TH", 0x041e, "Thai Kedmanee (0000041E)"),
    Profile("ES", 0x040a, "Spanish — Spain (0000040A)"),
    Profile("FR", 0x040c, "French — Legacy AZERTY (0000040C)"),
    Profile("DE", 0x0407, "German (00000407)"),
    Profile("RU", 0x0419, "Russian (00000419)"),
    Profile("AR", 0x0401, "Arabic (101) (00000401)"),
)}
STANDARD = {p.layout_id: p for p in PROFILES.values() if p.tip is None}
IME = {p.layout_id: p for p in PROFILES.values() if p.tip}
GET_LAYOUTS = n.api(n.USER, "GetKeyboardLayoutList", c.c_int, c.c_int, c.POINTER(w.HANDLE))
GET_THREAD = n.api(n.KERNEL, "GetCurrentThreadId", w.DWORD)
LAYOUT_NAME = n.api(n.USER, "GetKeyboardLayoutNameW", w.BOOL, w.LPWSTR)
MAP_SCAN = n.api(n.USER, "MapVirtualKeyExW", w.UINT, w.UINT, w.UINT, w.HANDLE)
TO_UNICODE = n.api(n.USER, "ToUnicodeEx", c.c_int, w.UINT, w.UINT,
                   c.POINTER(c.c_ubyte), w.LPWSTR, c.c_int, w.UINT, w.HANDLE)
POST = n.api(n.USER, "PostMessageW", w.BOOL, w.HWND, w.UINT, n.WPARAM, n.LPARAM)


def available_layouts():
    count = GET_LAYOUTS(0, None)
    if count <= 0:
        return None
    items = (w.HANDLE*count)()
    received = GET_LAYOUTS(count, items)
    return tuple(items[:received]) if received else None


def installed_codes(layouts=None):
    """Exact profiles exposed by Windows. The English companion is a separate UI state."""
    layouts = available_layouts() if layouts is None else layouts
    if not layouts:
        return None
    codes = set()
    for hkl in layouts:
        hkl = int(hkl or 0)
        if korean_base(hkl):
            codes.add("KR")
        elif (profile := IME.get(hkl & 0xffff)):
            if profile.code not in codes and enabled_tip(profile) is True:
                codes.add(profile.code)
        elif (profile := active_standard(hkl, None)):
            codes.add(profile.code)
    return frozenset(codes)


def korean_base(hkl):
    return bool(hkl and hkl & 0xffffffff == 0x04120412)


def standard_profile(hkl, exact_klid=None):
    if not hkl:
        return None
    if exact_klid is not None:
        return STANDARD.get(exact_klid)
    # For the built-in base layouts the high word is the base layout ID.
    # Dynamic/substituted handles (E/Fxxx) are deliberately not aliased.
    return STANDARD.get((hkl >> 16) & 0xffff)


def local_layout_id(hkl):
    if not hkl or hkl != n.get_layout(0):
        return None
    text = c.create_unicode_buffer(9)
    return int(text.value, 16) if LAYOUT_NAME(text) and len(text.value) == 8 else None


# Only three small TSF queries; no profile registration, enabling or activation.
class Guid(c.Structure):
    _fields_ = [("a", w.DWORD), ("b", w.WORD), ("d", w.WORD), ("e", c.c_ubyte*8)]


def guid(value):
    return Guid.from_buffer_copy(UUID(value).bytes_le)


class TipInfo(c.Structure):
    _fields_ = [("kind", w.DWORD), ("lang", w.WORD), ("clsid", Guid), ("profile", Guid),
                ("category", Guid), ("substitute", w.HANDLE), ("caps", w.DWORD),
                ("hkl", w.HANDLE), ("flags", w.DWORD)]


CLSID = guid("33c53a50-f456-4884-b049-85fd643ecfed")
IID = guid("71c6e74c-0f28-11d8-a82a-00065b84435c")
KEYBOARD = guid("34745c63-b2f0-4784-8b67-5e12c8701a31")
COM = c.WinDLL("ole32")
CO_INIT = n.api(COM, "CoInitializeEx", c.c_long, c.c_void_p, w.DWORD)
CO_CLOSE = n.api(COM, "CoUninitialize", None)
CO_CREATE = n.api(COM, "CoCreateInstance", c.c_long, c.POINTER(Guid), c.c_void_p,
                  w.DWORD, c.POINTER(Guid), c.POINTER(c.c_void_p))


def method(pointer, slot, result, *args):
    table = c.cast(pointer, c.POINTER(c.POINTER(c.c_void_p)))[0]
    return c.WINFUNCTYPE(result, c.c_void_p, *args)(table[slot])


def release(pointer):
    method(pointer, 2, w.ULONG)(pointer)


@contextmanager
def profile_manager():
    initialized = CO_INIT(None, 2)
    if initialized < 0 and initialized & 0xffffffff != 0x80010106:
        yield None
        return
    pointer = c.c_void_p()
    try:
        result = CO_CREATE(c.byref(CLSID), None, 1, c.byref(IID), c.byref(pointer))
        yield pointer if result == 0 and pointer.value else None
    finally:
        if pointer.value:
            release(pointer)
        if initialized >= 0:
            CO_CLOSE()


def matches_tip(info, profile):
    actual = (str(UUID(bytes_le=bytes(info.clsid))), str(UUID(bytes_le=bytes(info.profile))))
    return info.kind == 1 and info.lang == profile.layout_id and actual == profile.tip


def own_active_tip(hkl, thread):
    profile = IME.get((hkl or 0) & 0xffff)
    if not profile or thread != GET_THREAD() or hkl != n.get_layout(0):
        return None
    with profile_manager() as manager:
        if manager is None:
            return None
        info = TipInfo()
        query = method(manager, 10, c.c_long, c.POINTER(Guid), c.POINTER(TipInfo))
        if query(manager, c.byref(KEYBOARD), c.byref(info)) == 0 and matches_tip(info, profile):
            return profile


def enabled_tip(profile):
    """True/False only for a successful TSF enumeration; None means unobservable."""
    with profile_manager() as manager:
        if manager is None:
            return None
        pointer = c.c_void_p()
        enum = method(manager, 6, c.c_long, w.WORD, c.POINTER(c.c_void_p))
        if enum(manager, profile.layout_id, c.byref(pointer)) != 0 or not pointer.value:
            return None
        try:
            read = method(pointer, 4, c.c_long, w.ULONG, c.POINTER(TipInfo), c.POINTER(w.ULONG))
            while True:
                info, count = TipInfo(), w.ULONG()
                code = read(pointer, 1, c.byref(info), c.byref(count))
                if code == 1:
                    return False
                if code != 0 or count.value != 1:
                    return None
                if matches_tip(info, profile):
                    return bool(info.flags & 2)
        finally:
            release(pointer)


def ime_available(profile, layouts):
    if profile.code == "KR" and layouts and any(map(korean_base, layouts)):
        return True
    return enabled_tip(profile)


def availability():
    layouts = available_layouts()
    active = None if layouts is None else {p.code for h in layouts
                                            if (p := active_standard(h, None))}
    return {code: (ime_available(profile, layouts) if profile.tip
                   else None if active is None else code in active)
            for code, profile in PROFILES.items()}


def active_standard(hkl, thread):
    if not hkl or n.is_ime(hkl):
        return None
    return standard_profile(hkl, local_layout_id(hkl) if thread == GET_THREAD() else None)


@lru_cache(maxsize=1024)
def legend(hkl, scan, shift=False, caps=False, altgr=False):
    vk = MAP_SCAN(scan, 3, hkl)
    if not vk:
        return None
    state = (c.c_ubyte*256)()
    if shift:
        state[0x10] = state[0xa0] = 0x80
    if caps:
        state[0x14] = 1
    if altgr:
        state[0x11] = state[0xa2] = state[0x12] = state[0xa5] = 0x80
    buffer = c.create_unicode_buffer(16)
    count = TO_UNICODE(vk, scan & 0xff, state, buffer, len(buffer), 4, hkl)
    if not count:
        return None
    if count < 0:
        count = 1  # Show the spacing accent; Windows owns the pending dead key.
    value = buffer[:min(count, len(buffer))]
    return value if value and all(ch.isprintable() for ch in value) else None


@lru_cache(maxsize=16)
def has_altgr(hkl, scans):
    return any((modified := legend(hkl, scan, False, False, True)) and
               modified != legend(hkl, scan) for scan in scans)


def key_caption(hkl, scan, key, mode, shift, caps, altgr):
    if mode == "KR" and key.code in LAYOUTS["KR"]:
        return LAYOUTS["KR"][key.code][int(shift)]
    if not hkl or not scan or key.special:
        return key.normal
    # A blank translation stays blank; a US glyph would mislabel this key.
    return legend(hkl, scan, shift, caps, altgr) or "—"


def request_layout(hwnd, hkl):
    return bool(POST(hwnd, 0x0050, 0, c.c_ssize_t(hkl).value))
