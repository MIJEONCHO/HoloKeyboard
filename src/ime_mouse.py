"""Keep Korean IME composition alive across clicks on the HUD's own keys.

The low-level mouse hook is the riskiest thing this program does, so it lives only
while it is useful: Korean composition protection is relevant AND the pointer is over
a HUD key. It is removed as soon as either stops being true, on minimize/close/error,
and it is held past that only while a swallowed press is waiting for its release
(force-released after MAX_HOLD). A watchdog reinstalls it if Windows silently drops it.
"""
import atexit
import ctypes as c
from time import monotonic
from types import SimpleNamespace

import win_native as n

HOOKPROC = c.WINFUNCTYPE(n.LPARAM, c.c_int, n.WPARAM, n.LPARAM)
WH_MOUSE_LL = 14
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202


class MouseMessage(c.Structure):
    _fields_ = [("point", n.w.POINT), ("data", n.w.DWORD), ("flags", n.w.DWORD),
                ("time", n.w.DWORD), ("extra", n.WPARAM)]


install = n.api(n.USER, "SetWindowsHookExW", n.w.HANDLE, c.c_int, HOOKPROC,
                n.w.HINSTANCE, n.w.DWORD)
remove = n.api(n.USER, "UnhookWindowsHookEx", n.w.BOOL, n.w.HANDLE)
forward = n.api(n.USER, "CallNextHookEx", n.LPARAM, n.w.HANDLE, c.c_int, n.WPARAM, n.LPARAM)
window_at = n.api(n.USER, "WindowFromPoint", n.w.HWND, n.w.POINT)
REAL_API = SimpleNamespace(install=install, remove=remove, forward=forward, window_at=window_at)


class KoreanMouseFilter:
    MAX_HOLD = 1.5   # seconds a swallowed press may wait for its release
    STALE_TICKS = 8  # consecutive polls with a moving pointer and a silent hook = dropped hook
    RETRY = 1.0      # pause after a failed install

    def __init__(self, driver, api=None, clock=monotonic):
        self.driver, self.api, self.clock = driver, api or REAL_API, clock
        self.callback = HOOKPROC(self._filter)
        self.handle = None
        self.held = False
        self.active = False        # a new press over a key may be taken
        self.held_since = 0.0
        self.last_seen = 0.0       # last time Windows called the hook
        self.silent = 0
        self.seen_mark = 0.0
        self.blocked_until = 0.0
        self.installs = self.reinstalls = self.forced_releases = 0
        self.closed = False
        atexit.register(self.close)

    def update(self, relevant, over_keys, moved=False):
        """Called from the 16 ms poll. Decides whether the hook exists right now."""
        now = self.clock()
        try:
            if self.closed:
                return self._unhook()
            if self.held:
                if now-self.held_since > self.MAX_HOLD:
                    self._force_release()
                return
            self.active = bool(relevant and over_keys)
            if not self.active:
                self.silent = 0
                return self._unhook()
            if not self.handle:
                if now >= self.blocked_until:
                    self._hook(now)
                return
            # A live hook sees every mouse move; moving without a single call means Windows dropped it.
            self.silent = self.silent+1 if moved and self.last_seen == self.seen_mark else 0
            self.seen_mark = self.last_seen
            if self.silent >= self.STALE_TICKS:
                self.reinstalls += 1
                self._unhook()
                self._hook(now)
        except Exception:
            self.blocked_until = now+self.RETRY
            self._drop()

    def suspend(self):
        """Minimized, hidden or no longer relevant: nothing may stay hooked or half-pressed."""
        self._drop()

    def close(self):
        self.closed = True
        self._drop()
        atexit.unregister(self.close)

    def _hook(self, now):
        handle = self.api.install(WH_MOUSE_LL, self.callback, self.driver.instance, 0)
        if handle:
            self.handle, self.last_seen, self.silent = handle, now, 0
            self.seen_mark = now
            self.installs += 1
        else:
            self.blocked_until = now+self.RETRY

    def _unhook(self):
        handle, self.handle, self.active = self.handle, None, False
        if handle:
            self.api.remove(handle)

    def _force_release(self):
        self.forced_releases += 1
        self._drop()

    def _drop(self):
        was_held, self.held = self.held, False
        self._unhook()
        if was_held:
            try:
                self.driver._queue_pointer("ime-mouse", None, False)
            except Exception:
                pass

    def _filter(self, code, message, data):
        # Runs inside Windows' mouse path: tiny, exception-proof, and it swallows a
        # release only for a press it swallowed.
        try:
            self.last_seen = self.clock()
            if code != 0 or message not in (WM_LBUTTONDOWN, WM_LBUTTONUP):
                return self.api.forward(None, code, message, data)
            event = c.cast(data, c.POINTER(MouseMessage)).contents
            if event.extra & 0xffffff00 == 0xff515700:
                return self.api.forward(None, code, message, data)  # touch/pen promotion
            if message == WM_LBUTTONDOWN:
                if self.held or not self.active:
                    return self.api.forward(None, code, message, data)
                key = self._key_at(event.point)
                if not key:
                    return self.api.forward(None, code, message, data)
                self.driver._queue_pointer("ime-mouse", key, True)
                self.held, self.held_since = True, self.clock()
                return 1
            if not self.held:
                return self.api.forward(None, code, message, data)
            self.held = False
            self.driver._queue_pointer("ime-mouse", self._key_at(event.point), False)
            return 1
        except Exception:
            was_held, self.held = self.held, False
            if was_held:
                try:
                    self.driver._queue_pointer("ime-mouse", None, False)
                except Exception:
                    pass
            try:
                return self.api.forward(None, code, message, data)
            except Exception:
                return 0

    def _key_at(self, point):
        if self.api.window_at(point) != self.driver.window:
            return None
        packed = (point.x & 0xffff) | ((point.y & 0xffff) << 16)
        key = self.driver._hit(self.driver.window, packed, screen=True)
        return None if key == "__resize__" else key
