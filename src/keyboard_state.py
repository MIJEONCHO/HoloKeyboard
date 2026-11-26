"""Foreground identity and asynchronous Windows layout/IME state."""
import ctypes as c
import os
import threading
from collections import deque
from dataclasses import dataclass
from time import monotonic

import ime_state
import win_native as n
from win_native import w

CLASS_NAME = n.api(n.USER, "GetClassNameW", c.c_int, w.HWND, w.LPWSTR, c.c_int)


@dataclass(frozen=True)
class Target:
    window: int
    focus: int
    thread: int
    process: int

    @property
    def layout(self):
        return n.get_layout(self.thread)


def focused_target():
    window = n.foreground()
    if not window:
        return None
    context = n.GuiThread()
    context.size = c.sizeof(n.GuiThread)
    thread = n.window_thread(window, None)
    if not thread or not n.get_gui(thread, c.byref(context)) or not context.focus:
        return None
    pid = w.DWORD()
    thread = n.window_thread(context.focus, c.byref(pid))
    if not thread:
        return None
    return Target(window, context.focus, thread, pid.value)


EXTERNAL_IME_TTL, EXTERNAL_IME_TIMEOUT_MS, EXTERNAL_IME_BACKOFF = .08, 20, 1.0
IME_ANSWER_AGE = .30
IME_REFRESH_DELAYS = (0, .07, .18)
WNDENUM = c.WINFUNCTYPE(c.c_bool, w.HWND, w.LPARAM)
ENUM_CHILD = n.api(n.USER, "EnumChildWindows", w.BOOL, w.HWND, WNDENUM, w.LPARAM)


def _candidate_ime_windows(target):
    """Read the focus and then other distinct IME windows in the same application."""
    candidates = dict.fromkeys((target.focus, target.window))

    def visit(hwnd, _l):
        if len(candidates) >= 60:
            return False
        pid = w.DWORD()
        if n.window_thread(hwnd, c.byref(pid)) and pid.value == target.process:
            candidates[hwnd] = None
        return True

    ENUM_CHILD(target.window, WNDENUM(visit), 0)
    seen = set()
    for hwnd in candidates:
        ime = n.default_ime_window(hwnd)
        if ime and ime not in seen:
            seen.add(ime)
            yield hwnd, ime


class _Reader(threading.Thread):
    """Refresh results belong to one foreground activation and one request."""
    def __init__(self):
        super().__init__(daemon=True, name="holo-ime-reader")
        self.wake = threading.Event()
        self.wanted = self.reply = self.request = None
        self.scope = None
        self.started = 0
        self.verify = False
        self.delays = deque()
        self.next_at = 0
        self.answer, self.answer_at = None, 0
        self.sources = {}
        self.baseline = {}
        self.observed_scope = None

    def observe(self, scope, now, toggled=False):
        changed = scope != self.scope
        if changed or toggled:
            self.scope = scope
            self.request = self.wanted = None
            self.answer = None
            self.started = self.next_at = now
            self.verify = toggled
            self.delays = deque(IME_REFRESH_DELAYS)
        if scope is None:
            return None
        if self.request is not None and self.reply and self.reply[0] is self.request:
            answer = self.reply[1]
            if answer is not None:
                self.answer, self.answer_at = answer, now
            self.request = None
            if self.delays:
                self.next_at = self.started + self.delays[0]
            else:
                self.next_at = now + (EXTERNAL_IME_TTL if self.answer else EXTERNAL_IME_BACKOFF)
        if self.answer is not None and now - self.answer_at >= IME_ANSWER_AGE:
            self.answer = None
        if self.request is None and now >= self.next_at:
            if self.delays:
                initial = not self.verify and self.delays[0] == 0
                self.delays.popleft()
                phase = "verify" if self.verify else "initial" if initial else "poll"
            else:
                phase = "poll"
            self.request = self.wanted = (scope, phase)
            self.wake.set()
        return self.answer

    def run(self):
        while True:
            self.wake.wait()
            self.wake.clear()
            request = self.wanted
            if request is None or (self.reply and self.reply[0] is request):
                continue
            try:
                answer = self.read(request)
            except Exception:
                answer = None
            if self.wanted is request:
                self.reply = (request, answer)

    def read(self, request):
        scope, phase = request
        target, _layout = scope
        name = c.create_unicode_buffer(64)
        if not CLASS_NAME(target.focus, name, len(name)):
            return None
        if ime_state.trusted_window(name.value, target.process):
            reading = ime_state.read_imm(target.focus, EXTERNAL_IME_TIMEOUT_MS)
            return ime_state.korean_mode(reading) if reading else None
        source = self.sources.get(scope)
        if source:
            hwnd, ime = source
            if n.default_ime_window(hwnd) == ime:
                reading = ime_state.read_imm(hwnd, EXTERNAL_IME_TIMEOUT_MS)
                return ime_state.korean_mode(reading) if reading else None
            self.sources.pop(scope)
        if scope != self.observed_scope or phase == "initial":
            self.observed_scope, self.baseline = scope, {}
        # A live, open IME on the actual focus window supplies a conversion mode
        # directly. Closed/zero replies from unverified window types can be stubs.
        if phase != "verify":
            reading = ime_state.read_imm(target.focus, EXTERNAL_IME_TIMEOUT_MS)
            if self.wanted is not request:
                return None
            if reading and reading[0]:
                key = (target.focus, n.default_ime_window(target.focus))
                self.baseline[key] = (reading[0], reading[1] & 1)
                return ime_state.korean_mode(reading)
        if phase == "poll" and self.baseline:
            candidates = ((target.focus, n.default_ime_window(target.focus)),)
        else:
            candidates = _candidate_ime_windows(target)
        for hwnd, ime in candidates:
            if self.wanted is not request:
                return None
            reading = ime_state.read_imm(hwnd, EXTERNAL_IME_TIMEOUT_MS) if ime else None
            if self.wanted is not request:
                return None
            if reading is None:
                continue
            mark = (reading[0], reading[1] & 1)
            key = (hwnd, ime)
            before = self.baseline.get(key)
            if phase != "verify" or before is None:
                self.baseline[key] = mark
            elif before != mark:
                if len(self.sources) >= 16:
                    self.sources.pop(next(iter(self.sources)))
                self.sources[scope] = key
                return ime_state.korean_mode(reading)
        return None


_reader = None


def language_state(target, *, toggled=False, layout=None):
    global _reader
    if layout is None and target:
        layout = target.layout
    primary_language = (layout or 0) & 0x3ff
    external = bool(target and primary_language == 0x12 and target.process != os.getpid())
    if external and _reader is None:
        _reader = _Reader()
        _reader.start()
    if _reader is not None:
        state = _reader.observe((target, layout) if external else None, monotonic(), toggled and external)
        if external:
            return state or "IME ?"
    if primary_language == 9 and not n.is_ime(layout):
        return "EN"
    if primary_language != 0x12:
        return "IME ?"
    context = n.ime_context(target.focus)
    if not context:
        return "IME ?"
    try:
        mode = w.DWORD()
        if not n.ime_conversion(context, c.byref(mode), None):
            return "IME ?"
        return "KR" if n.ime_open(context) and mode.value & 1 else "EN"
    finally:
        n.ime_release(target.focus, context)


