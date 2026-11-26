"""Fail-closed target authorization for local keystroke display."""
import ctypes as c
import os
import threading
import time
from time import monotonic

import ime_state
import input_profiles as profiles
import win_native as n
from win_native import w

PASSWORD, PLAIN, NOT_WIN32, UNKNOWN = "password", "plain", "not-win32", "unknown"
WARMING = "warming"  # worker-internal: the browser has not exposed the focused element yet
VT_BOOL, VT_I4 = 11, 3
UIA_RUNTIME_ID, UIA_PID, UIA_FOCUS, UIA_PASSWORD = 30000, 30002, 30008, 30019
UIA_HWND = 30020
UIA_CONTROL_TYPE, UIA_FOCUSABLE = 30003, 30009
CTYPE_EDIT, CTYPE_WINDOW = 50004, 50032
ES_PASSWORD, EM_GETPASSWORDCHAR, SMTO_ABORTIFHUNG = 0x20, 0x00d2, 0x0002
# Keys that can move focus between fields without changing the window handle.
NAV_KEYS = frozenset({"Tab", "Enter", "NumpadEnter", "ArrowLeft", "ArrowRight",
                      "ArrowUp", "ArrowDown"})
_why = threading.local()
# Lock reasons after which the guard keeps asking again every RETRY seconds.
RETRY_REASONS = frozenset({"timeout", "unknown", "warming", "no-uia", "no-element",
                           "other-process", "unreadable"})
CLSID_UIA = profiles.guid("ff48dba4-60ef-4201-aa87-54103eef594e")
IID_UIA = profiles.guid("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee")
_oleaut = c.WinDLL("oleaut32")
_clear_variant = n.api(_oleaut, "VariantClear", c.c_long, c.c_void_p)
_array_dim = n.api(_oleaut, "SafeArrayGetDim", c.c_uint, c.c_void_p)
_array_lower = n.api(_oleaut, "SafeArrayGetLBound", c.c_long, c.c_void_p, c.c_uint, c.POINTER(c.c_long))
_array_upper = n.api(_oleaut, "SafeArrayGetUBound", c.c_long, c.c_void_p, c.c_uint, c.POINTER(c.c_long))
_array_data = n.api(_oleaut, "SafeArrayAccessData", c.c_long, c.c_void_p, c.POINTER(c.c_void_p))
_array_release = n.api(_oleaut, "SafeArrayUnaccessData", c.c_long, c.c_void_p)


def property_value(element, property_id, expected, *, cached=False):
    """Use the Ex getter so unsupported properties cannot look like explicit false."""
    # A native VARIANT is 24 bytes on 64-bit Windows and 16 bytes on 32-bit.
    raw = (c.c_uint64 * (3 if c.sizeof(c.c_void_p) == 8 else 2))()
    get = profiles.method(element, 13 if cached else 11, c.c_long, c.c_int,
                          w.BOOL, c.c_void_p)
    try:
        if get(element, property_id, True, c.byref(raw)) != 0 or raw[0] & 0xffff != expected:
            return None
        if expected == VT_BOOL:
            value = raw[1] & 0xffff
            return {0: False, 0xffff: True}.get(value)
        return c.c_int32(raw[1] & 0xffffffff).value
    finally:
        _clear_variant(c.byref(raw))


def runtime_identity(element):
    """Read only the cached numeric accessibility identity for safe resume."""
    raw = (c.c_uint64 * (3 if c.sizeof(c.c_void_p) == 8 else 2))()
    get = profiles.method(element, 13, c.c_long, c.c_int, w.BOOL, c.c_void_p)
    try:
        if get(element, UIA_RUNTIME_ID, True, c.byref(raw)) != 0 or raw[0] & 0xffff != 0x2003:
            return None
        array = raw[1]
        if not array or _array_dim(array) != 1:
            return None
        lo, hi = c.c_long(), c.c_long()
        if _array_lower(array, 1, c.byref(lo)) or _array_upper(array, 1, c.byref(hi)):
            return None
        size = hi.value - lo.value + 1
        data = c.c_void_p()
        if not 1 <= size <= 64 or _array_data(array, c.byref(data)) != 0:
            return None
        try:
            return tuple((c.c_int32 * size).from_address(data.value))
        finally:
            _array_release(array)
    finally:
        _clear_variant(c.byref(raw))


def new_guard_cache(automation):
    request = c.c_void_p()
    create = profiles.method(automation, 20, c.c_long, c.POINTER(c.c_void_p))
    if create(automation, c.byref(request)) != 0 or not request.value:
        return None
    add = profiles.method(request, 3, c.c_long, c.c_int)
    properties = (UIA_PID, UIA_PASSWORD, UIA_FOCUS, UIA_HWND, UIA_RUNTIME_ID,
                  UIA_CONTROL_TYPE, UIA_FOCUSABLE)
    if any(add(request, prop) != 0 for prop in properties):
        profiles.release(request)
        return None
    return request


def win32_password_state(hwnd, timeout_ms=20):
    """PASSWORD/PLAIN for a standard Win32 Edit or RichEdit, NOT_WIN32 for any other class."""
    name = c.create_unicode_buffer(64)
    if not hwnd or not n.class_name(hwnd, name, len(name)):
        return UNKNOWN
    if name.value != "Edit" and not name.value.lower().startswith("richedit"):
        return NOT_WIN32
    if n.get_style(hwnd, -16) & ES_PASSWORD:
        return PASSWORD
    answer = c.c_size_t()
    if not n.send_timeout(hwnd, EM_GETPASSWORDCHAR, 0, 0, SMTO_ABORTIFHUNG,
                          timeout_ms, c.byref(answer)):
        return UNKNOWN
    return PASSWORD if answer.value else PLAIN


def decide_element(password, has_focus):
    if password is True:
        return PASSWORD
    if password is not False or has_focus is None:
        return UNKNOWN
    if not has_focus:
        return WARMING
    return PLAIN


def _window_class(hwnd):
    name = c.create_unicode_buffer(64)
    return name.value if n.class_name(hwnd, name, len(name)) else ""


def hancom_body(target, ctype, hwnd, focusable):
    """The Hancom Hangul document canvas. It names itself a focusable Edit that is not a password but
    always answers HasKeyboardFocus=False; Win32 focus (checked by the caller) stands in for that.
    Measured on Hwp 2010. Its dialogs, including the password dialog, use other window classes."""
    return bool(ctype == CTYPE_EDIT and focusable is True and hwnd
                and (hwnd & 0xffffffff) == target.focus
                and _window_class(target.focus) == "HwpMainEditWnd"
                and _window_class(target.window).startswith("HwpApp")
                and ime_state.image_name(target.process) == "hwp.exe")


def refine_verdict(verdict, ctype, document_body):
    """A focused whole Window is not an identified text field: apps that draw their own fields (the
    Hancom password dialog) leave only the window element, which reports IsPassword=False."""
    if verdict == WARMING and document_body:
        return PLAIN
    if verdict == PLAIN and ctype in (None, CTYPE_WINDOW):
        return UNKNOWN
    return verdict


class UiaPasswordClient:
    """UI Automation FocusedElement.CurrentIsPassword on a worker thread (never the Tk thread)."""
    STUCK_AFTER, MAX_ABANDONED = 2.0, 3
    WARM_MAX, WARM_STEP = 1.6, .04  # a browser builds its tree on the first query (0.05 s to ~1.5 s)

    def __init__(self):
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._request = None
        self._results = {}
        self._details = {}
        self._thread = None
        self._generation = 0
        self._busy_since = None
        self._abandoned = 0  # abandoned worker threads that are still stuck inside a provider call
        self._closed = False

    def request(self, token, target):
        with self._lock:
            if self._closed:
                return
            self._request = (token, target)
            if self._thread and self._busy_since and monotonic()-self._busy_since > self.STUCK_AFTER:
                self._generation += 1  # abandon a thread stuck inside a provider
                self._thread, self._busy_since = None, None
                self._abandoned += 1
            if self._thread is None and self._abandoned <= self.MAX_ABANDONED:
                self._thread = threading.Thread(target=self._run, args=(self._generation,),
                                                name="holo-uia", daemon=True)
                self._thread.start()
        self._wake.set()

    def result(self, token):
        """None while pending; otherwise verdict and optional numeric element identity."""
        with self._lock:
            return self._results.pop(token, None)

    def detail(self, token):
        """Short reason of an UNKNOWN verdict (e.g. 'warming', 'no-uia'), or None."""
        with self._lock:
            return self._details.pop(token, None)

    def close(self):
        with self._lock:
            self._closed = True
            self._generation += 1
        self._wake.set()

    def _run(self, generation):
        initialized = profiles.CO_INIT(None, 0)  # multithreaded apartment for this worker only
        automation = c.c_void_p()
        try:
            while True:
                self._wake.wait(1.0)
                with self._lock:
                    if generation != self._generation:
                        return
                    self._wake.clear()
                    request, self._request = self._request, None
                    if request:
                        self._busy_since = monotonic()
                if not request:
                    continue
                _why.value = _why.proof = None
                try:
                    verdict = self._query_ready(automation, request[1], generation)
                except Exception:
                    verdict = UNKNOWN
                    _why.value = "unreadable"
                with self._lock:
                    if generation != self._generation:
                        self._abandoned = max(0, self._abandoned-1)  # the stuck call finally returned
                        return
                    self._busy_since = None
                    if generation == self._generation:
                        self._results[request[0]] = (verdict, _why.proof)
                        if verdict == UNKNOWN and getattr(_why, "value", None):
                            self._details[request[0]] = _why.value
                        for stale in sorted(self._results)[:-8]:
                            del self._results[stale]
                        for stale in sorted(self._details)[:-8]:
                            del self._details[stale]
        finally:
            cache = getattr(_why, "cache", None)
            if cache:
                profiles.release(cache)
                _why.cache = None
            if automation.value:
                profiles.release(automation)
            if initialized >= 0:
                profiles.CO_CLOSE()

    def _query_ready(self, automation, target, generation):
        """One verdict. While a browser has not finished building its accessibility tree (see
        _query), ask again every WARM_STEP for at most WARM_MAX; a newer request or close ends it."""
        end = monotonic()+self.WARM_MAX
        while True:
            verdict = self._query(automation, target)
            if verdict != WARMING:
                return verdict
            with self._lock:
                abandoned = generation != self._generation or self._request is not None
            if abandoned or monotonic() >= end:
                _why.value = "warming"  # the browser never exposed the focused element in time
                return UNKNOWN
            time.sleep(self.WARM_STEP)

    @staticmethod
    def _query(automation, target):
        """Verify the same focused edit using protection metadata only."""
        _why.value = None
        if not automation.value:
            made = profiles.CO_CREATE(c.byref(CLSID_UIA), None, 1, c.byref(IID_UIA),
                                      c.byref(automation))
            if made != 0 or not automation.value:
                _why.value = "no-uia"
                return UNKNOWN
        element = c.c_void_p()
        cache = getattr(_why, "cache", None)
        if not cache:
            _why.cache = cache = new_guard_cache(automation)
        if not cache:
            _why.value = "no-uia"
            return UNKNOWN
        focused = profiles.method(automation, 12, c.c_long, c.c_void_p, c.POINTER(c.c_void_p))
        if focused(automation, cache, c.byref(element)) != 0 or not element.value:
            _why.value = "no-element"
            return UNKNOWN
        try:
            if property_value(element, UIA_PID, VT_I4, cached=True) != target.process:
                _why.value = "other-process"
                return UNKNOWN  # focus moved to another process meanwhile
            password = property_value(element, UIA_PASSWORD, VT_BOOL, cached=True)
            if password is None or password:
                _why.value = "no-uia" if password is None else None
                return decide_element(password, None)
            info = n.GuiThread()
            info.size = c.sizeof(info)
            hwnd = property_value(element, UIA_HWND, VT_I4, cached=True)
            if (n.foreground() != target.window or not n.get_gui(target.thread, c.byref(info))
                    or info.focus != target.focus or (hwnd and (hwnd & 0xffffffff) != target.focus)):
                _why.value = "no-element"
                return UNKNOWN
            has_focus = property_value(element, UIA_FOCUS, VT_BOOL, cached=True)
            ctype = property_value(element, UIA_CONTROL_TYPE, VT_I4, cached=True)
            verdict = decide_element(password, has_focus)
            body = verdict == WARMING and hancom_body(
                target, ctype, hwnd,
                property_value(element, UIA_FOCUSABLE, VT_BOOL, cached=True))
            verdict = refine_verdict(verdict, ctype, body)
            if verdict == PLAIN:
                _why.proof = runtime_identity(element)
            elif verdict == UNKNOWN:
                _why.value = "unreadable"
            return verdict
        finally:
            profiles.release(element)


class MirrorGuard:
    """Decides whether local text may be assembled. `locked` is the fail-closed state."""
    UIA_PATIENCE, RECHECK, REFRESH_LEAD, RETRY = 3.0, .5, .20, .5

    def __init__(self, win32=win32_password_state, uia=None, clock=monotonic, pid=None,
                 root_of=None):
        self.win32, self._uia, self.clock = win32, uia, clock
        self.pid = pid if pid is not None else os.getpid()
        self.root_of = root_of or (lambda hwnd: n.get_ancestor(hwnd, 2) or hwnd)
        self.safe_windows = set()
        self.locked, self.reason = True, "no-target"
        self.identity = self.proof = None
        self.volatile = False  # state derived from UI Automation, which can change in place
        self.dirty = False
        self._pending = None
        self._rechecking = False  # the pending request can preserve this field's verified line
        self._token = 0
        self._retry_at = 0.0
        self._checked_at = 0.0

    # Registration is for windows of this process that never hold a password.
    def register_safe_control(self, hwnd):
        self.safe_windows.add(hwnd)
        self.identity = None

    def register_safe_window(self, hwnd):
        self.safe_windows.add(hwnd)
        try:
            self.safe_windows.add(self.root_of(hwnd))
        except Exception:
            pass
        self.identity = None

    def unregister_safe_window(self, hwnd):
        self.safe_windows.discard(hwnd)
        try:
            self.safe_windows.discard(self.root_of(hwnd))
        except Exception:
            pass
        self.identity = None

    def _registered(self, target):
        if target.window in self.safe_windows or target.focus in self.safe_windows:
            return True
        try:
            return self.root_of(target.focus) in self.safe_windows
        except Exception:
            return False

    def mark_dirty(self):
        """Revoke proof when navigation may have changed the logical input field."""
        self.dirty = True
        self.proof = None
        self._set(True, "navigating")

    @property
    def suspended(self):
        return self.locked and self._rechecking

    def can_accept(self):
        return not (self.dirty or self.locked or
                    (self.volatile and self.clock() >= self._checked_at + self.RECHECK))

    def update(self, target):
        now = self.clock()
        if target is None:
            self.identity = self.proof = self._pending = None
            self.volatile = self._rechecking = False
            return self._set(True, "no-target")
        identity = (target.window, target.focus, target.process, target.thread)
        if identity != self.identity or self.dirty:
            self.identity, self.dirty = identity, False
            return self._begin(target, now)
        if self._pending:
            return self._poll(now)
        if self.locked and self.reason in RETRY_REASONS and now >= self._retry_at:
            return self._begin(target, now)
        if self.volatile:
            lead = self.REFRESH_LEAD if not self.locked and self.proof is not None else 0
            if now >= self._checked_at + self.RECHECK - lead:
                return self._request(target, now, recheck=bool(lead))
        return self.locked

    def close(self):
        if self._uia is not None:
            self._uia.close()

    def _set(self, locked, reason):
        self.locked, self.reason = locked, reason
        return locked

    def _begin(self, target, now):
        self.proof = self._pending = None
        self.volatile = self._rechecking = False
        own = target.process == self.pid
        registered = own and self._registered(target)
        if own and not registered:
            return self._set(True, "own-window")
        kind = self.win32(target.focus)
        if kind == PASSWORD:
            return self._set(True, "password")
        if kind == PLAIN:
            return self._set(False, "win32-plain")
        if kind != NOT_WIN32:
            self._retry_at = now+self.RETRY
            return self._set(True, "unknown")
        if registered:
            return self._set(False, "registered")
        return self._request(target, now)

    def _request(self, target, now, recheck=False):
        if self._uia is None:
            self._uia = UiaPasswordClient()
        self._token += 1
        self._uia.request(self._token, target)
        self._pending = (self._token, now)
        self._rechecking = recheck
        if recheck and now < self._checked_at + self.RECHECK:
            return False
        return self._set(True, "pending")

    def _poll(self, now):
        token, started = self._pending
        result = self._uia.result(token)
        if now - started > self.UIA_PATIENCE:
            self.proof = self._pending = None
            self.volatile = self._rechecking = False
            self._retry_at = now + self.RETRY
            return self._set(True, "timeout")
        if result is None:
            if self._rechecking and now >= self._checked_at + self.RECHECK:
                return self._set(True, "pending")
            return self.locked
        verdict, self.proof = result
        self._pending, self._rechecking = None, False
        if verdict in (PLAIN, PASSWORD):
            self.volatile, self._checked_at = True, now
            return self._set(verdict == PASSWORD, "uia-password" if verdict == PASSWORD else "uia-plain")
        self.proof = None
        self.volatile = False
        self._retry_at = now + self.RETRY
        reason = self._uia.detail(token)
        return self._set(True, reason if reason in RETRY_REASONS else "unknown")
