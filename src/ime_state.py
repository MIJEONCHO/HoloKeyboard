"""Read-only Korean IME state of another process's focus window.

Measured during development: the thread's default IME window answers
WM_IME_CONTROL for classic Win32 Edit controls AND for Chrome page inputs (Chrome syncs its TSF
state into the IMM default context). TSF global compartments are empty here, so they are not used.
Nothing here changes IME state; replies are bounded by short SendMessageTimeout calls."""
import ctypes as c

import win_native as n
from win_native import w

IMC_GETCONVERSIONMODE, IMC_GETOPENSTATUS = 1, 5
# Win32 defines conversion flags through IME_CMODE_FIXED (0x800).
# Bit 0x4 and bits outside the documented conversion flags are reserved.
CONVERSION_FLAGS = 0x0ffb
# Classes whose IMM answer was compared with real typed output (Hangul vs Latin) on this PC.
EDIT_CLASSES = ("Edit",)
# Chromium-based windows (Chrome, Edge and Electron apps such as the Claude and ChatGPT desktop apps)
# share one engine and the same window classes. Measured: the answer follows the Hangul key in the
# Claude desktop app (claude.exe, focus class Chrome_WidgetWin_1) and in Chrome.
CHROMIUM_PREFIX = "Chrome_"
QUERY_LIMITED = 0x1000
OPEN_PROCESS = n.api(n.KERNEL, "OpenProcess", w.HANDLE, w.DWORD, w.BOOL, w.DWORD)
CLOSE_HANDLE = n.api(n.KERNEL, "CloseHandle", w.BOOL, w.HANDLE)
IMAGE_NAME = n.api(n.KERNEL, "QueryFullProcessImageNameW", w.BOOL, w.HANDLE, w.DWORD,
                   w.LPWSTR, c.POINTER(w.DWORD))
_images = {}  # pid -> lower-case exe name ("" when unknown)


def image_name(pid):
    if pid not in _images:
        if len(_images) > 64:
            _images.clear()
        name = ""
        handle = OPEN_PROCESS(QUERY_LIMITED, False, pid)
        if handle:
            try:
                buffer, size = c.create_unicode_buffer(520), w.DWORD(520)
                if IMAGE_NAME(handle, 0, buffer, c.byref(size)):
                    name = buffer.value.rsplit("\\", 1)[-1].lower()
            finally:
                CLOSE_HANDLE(handle)
        _images[pid] = name
    return _images[pid]


# (exe, focus class) pairs whose answer was measured to follow the Hangul key press by press on this
# PC: Windows Notepad (WinUI text box), PowerPoint 2010 (edit pane), Word 2010 (document pane) and
# Excel 2010 (cell selection EXCEL7, in-cell editor EXCEL6, formula bar EXCEL<).
MEASURED = {("notepad.exe", "RichEditD2DPT"), ("powerpnt.exe", "paneClassDC"), ("winword.exe", "_WwG"),
            ("excel.exe", "EXCEL7"), ("excel.exe", "EXCEL6"), ("excel.exe", "EXCEL<")}
def trusted_window(class_name, pid):
    """True only for window kinds whose IME answers were verified against real typing or learned."""
    if class_name in EDIT_CLASSES or class_name.startswith(CHROMIUM_PREFIX):
        return True
    key = (image_name(pid), class_name)
    return key in MEASURED


def read_imm(focus, timeout_ms=20):
    """(open, conversion mode) from the focus thread's default IME window, or None."""
    ime = n.default_ime_window(focus)
    opened, mode = c.c_size_t(), c.c_size_t()
    if (ime and n.send_timeout(ime, 0x0283, IMC_GETOPENSTATUS, 0, 0x2, timeout_ms, c.byref(opened))
            and n.send_timeout(ime, 0x0283, IMC_GETCONVERSIONMODE, 0, 0x2, timeout_ms, c.byref(mode))
            and opened.value <= 1 and not mode.value & ~CONVERSION_FLAGS):
        return int(opened.value), int(mode.value)
    return None


def korean_mode(reading):
    """Hangul mode means the IME is open AND in native (Hangul) conversion."""
    opened, mode = reading
    return "KR" if opened and mode & 1 else "EN"
