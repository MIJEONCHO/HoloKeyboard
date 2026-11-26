"""`HoloKeyboard.exe --diagnose[=SECONDS]`: a short report on where the key mirror stops in a given app.

For every second it records the facts of each stage, separately:
  1 raw input   how many physical key events reached the HUD, and how many of them found the mirror locked
  2 focus       foreground program, top/focus window classes, keyboard layout
  3 IME         the open/conversion answer at the focus window and the HUD's Korean/English verdict
  4 security    the local preview protection verdict and the manual glow lock
No typed text, no window titles, no element names and no key identities are recorded (counts only).
The report is written to the Desktop (HoloKeyboard-diagnose.txt) and is plain text.
"""
import ctypes as c
import os
import time
from pathlib import Path

import ime_state
import win_native as n
import keyboard_state as wi

def report_path():
    override = os.environ.get("HOLO_DIAG_PATH")
    if override:
        return Path(override)
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    return (desktop if desktop.is_dir() else Path.home()) / "HoloKeyboard-diagnose.txt"


def process_elevation(pid):
    """'admin' / 'normal' for a process, or 'unreadable (higher privilege?)' when Windows refuses the query.
    Windows (UIPI) keeps hardware key events and window messages of an elevated program away from a normal one."""
    try:
        kernel, advapi = c.WinDLL("kernel32", use_last_error=True), c.WinDLL("advapi32", use_last_error=True)
        kernel.OpenProcess.restype = c.c_void_p
        kernel.OpenProcess.argtypes = (c.c_ulong, c.c_int, c.c_ulong)
        advapi.OpenProcessToken.argtypes = (c.c_void_p, c.c_ulong, c.POINTER(c.c_void_p))
        advapi.GetTokenInformation.argtypes = (c.c_void_p, c.c_int, c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong))
        kernel.CloseHandle.argtypes = (c.c_void_p,)
        process = kernel.OpenProcess(0x1000, False, pid)           # PROCESS_QUERY_LIMITED_INFORMATION
        if not process:
            return "unreadable (higher privilege?)"
        token = c.c_void_p()
        try:
            if not advapi.OpenProcessToken(process, 0x0008, c.byref(token)):   # TOKEN_QUERY
                return "unreadable (higher privilege?)"
            elevated, size = c.c_ulong(), c.c_ulong()
            if advapi.GetTokenInformation(token, 20, c.byref(elevated), c.sizeof(elevated), c.byref(size)):  # TokenElevation
                return "admin" if elevated.value else "normal"
            return "unreadable"
        finally:
            if token.value:
                kernel.CloseHandle(token)
            kernel.CloseHandle(process)
    except Exception:
        return "unreadable"


def _class(hwnd):
    buffer = c.create_unicode_buffer(96)
    n.class_name(hwnd, buffer, 96)
    return buffer.value


class Diagnose:
    def __init__(self, hud, seconds=90):
        self.hud, self.root = hud, hud.root
        self.seconds = max(3, int(seconds))
        self.path = report_path()
        self.started = time.monotonic()
        hud.diag = {"raw": 0, "raw_locked": 0}
        self.seen = {"raw": 0, "raw_locked": 0}
        self.lines = [
            "HoloKeyboard diagnostic report (no typed text, titles or key identities are recorded)",
            f"started {time.strftime('%Y-%m-%d %H:%M:%S')}  duration {self.seconds}s  HoloKeyboard itself: {process_elevation(os.getpid())}",
            "note: a program shown as [admin] (or [unreadable (higher privilege?)]) is elevated; Windows then hides its keys and IME state from a normal HoloKeyboard",
            "columns: t | program | top / focus class | layout | IMM(focus) | IME verdict | lock | lock reason | raw keys (locked)",
        ]
        self.root.after(1000, self._tick)

    def _tick(self):
        hud = self.hud
        try:
            d = hud.diag
            raw, locked_raw = d["raw"] - self.seen["raw"], d["raw_locked"] - self.seen["raw_locked"]
            self.seen = dict(d)
            t = wi.focused_target()
            if t is None:
                program, classes, layout, imm, verdict = "-", "-", "-", "-", "-"
            else:
                program = f"{ime_state.image_name(t.process) or '?'} [{process_elevation(t.process)}]"
                classes = f"{_class(t.window)} / {_class(t.focus)}"
                layout = f"{t.layout & 0xffff:#06x}" if t.layout else "-"
                reading = ime_state.read_imm(t.focus, 30)
                imm = "-" if reading is None else f"open={reading[0]} mode={reading[1]:#x}"
                verdict = wi.language_state(t)
            self.lines.append(
                f"{time.monotonic()-self.started:5.0f}s | {program} | {classes} | {layout} | {imm} | {verdict} | "
                f"{'INPUT-LOCKED' if hud.mirror_locked else 'glow-open'} | "
                f"local display guard: {'blocked' if hud.guard_verdict[0] else 'allowed'}/{hud.guard_verdict[1] or '-'} | "
                f"{raw} ({locked_raw})")
        except Exception as exc:  # noqa: BLE001
            self.lines.append(f"(tick error {type(exc).__name__})")
        if time.monotonic() - self.started >= self.seconds:
            self.finish()
        else:
            self.root.after(1000, self._tick)

    def finish(self):
        self.lines.append("end of report")
        try:
            self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
            message = f"HoloKeyboard diagnostic finished.\n\nReport: {self.path}"
        except OSError as exc:
            message = f"Could not write the report: {exc}"
        if os.environ.get("HOLO_DIAG_QUIET") != "1":
            try:
                c.windll.user32.MessageBoxW(0, message, "HoloKeyboard", 0x40)
            except Exception:
                pass
        self.hud.close()
