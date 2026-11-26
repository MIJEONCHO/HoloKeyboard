"""Input driver. Reuses the design's key IDs and never derives preview text from scans."""
import ctypes as c
from time import monotonic
from collections import deque

import win_native as n
import input_profiles as profiles
from ime_mouse import KoreanMouseFilter
from keyboard_state import focused_target, language_state
from key_glow import KeyGlow
from key_preview import LocalPreview
from mirror_guard import NAV_KEYS
from raw_keyboard import RawKeyboard
from win_native import w

# Windows Set 1 make codes for the fixed ANSI key IDs.
SCAN = {
    "Backquote": 0x29, "Minus": 0x0c, "Equal": 0x0d, "Backspace": 0x0e,
    "Tab": 0x0f, "BracketLeft": 0x1a, "BracketRight": 0x1b, "Backslash": 0x2b,
    "CapsLock": 0x3a, "Semicolon": 0x27, "Quote": 0x28, "Enter": 0x1c,
    "ShiftLeft": 0x2a, "ShiftRight": 0x36, "Comma": 0x33, "Period": 0x34,
    "Slash": 0x35, "Space": 0x39, "ArrowLeft": 0xe04b, "ArrowRight": 0xe04d,
}
SCAN.update({f"Digit{k}": i for i, k in enumerate("1234567890", 0x02)})
for letters, start in (("QWERTYUIOP", 0x10), ("ASDFGHJKL", 0x1e), ("ZXCVBNM", 0x2c)):
    SCAN.update({f"Key{k}": i for i, k in enumerate(letters, start)})
# Full layout keys. 0xe000 marks the extended (E0) prefix; SendInput gets it as a flag.
SCAN.update({
    "Escape": 0x01, "NumLock": 0xe045, "ScrollLock": 0x46, "PrintScreen": 0xe037,
    "CtrlLeft": 0x1d, "CtrlRight": 0xe01d, "AltLeft": 0x38, "AltRight": 0xe038,
    "WinLeft": 0xe05b, "WinRight": 0xe05c, "Menu": 0xe05d,
    "Insert": 0xe052, "Home": 0xe047, "PageUp": 0xe049, "Delete": 0xe053,
    "End": 0xe04f, "PageDown": 0xe051, "ArrowUp": 0xe048, "ArrowDown": 0xe050,
    "NumpadDivide": 0xe035, "NumpadMultiply": 0x37, "NumpadSubtract": 0x4a,
    "NumpadAdd": 0x4e, "NumpadEnter": 0xe01c, "NumpadDecimal": 0x53, "Numpad0": 0x52,
})
SCAN.update({f"F{i}": 0x3a+i for i in range(1, 11)})
SCAN.update({"F11": 0x57, "F12": 0x58})
SCAN.update({f"Numpad{d}": s for d, s in zip("789456123", (0x47, 0x48, 0x49, 0x4b, 0x4c, 0x4d,
                                                        0x4f, 0x50, 0x51))})
KEY_ID = {v: k for k, v in SCAN.items()}
KEY_ID[0x45] = "NumLock"  # Raw Input reports NumLock without the E0 prefix
# Windows ignores a bare scancode for NumLock (verified); it needs the virtual key.
VK_ONLY = {"NumLock": 0x90}
ALTGR_SCAN = 0xe038
# Sticky one-shot modifiers: key code -> (family, virtual key used to see a physical hold).
MODIFIERS = {"ShiftLeft": ("shift", 0x10), "ShiftRight": ("shift", 0x10),
             "CtrlLeft": ("ctrl", 0x11), "CtrlRight": ("ctrl", 0x11),
             "AltLeft": ("alt", 0x12), "AltRight": ("alt", 0x12),
             "WinLeft": ("win", 0x5b), "WinRight": ("win", 0x5c)}
MOD_ORDER = ("ctrl", "alt", "win", "shift")  # press order; release is the reverse
PRINTABLE_SCANS = tuple(scan for key, scan in SCAN.items() if
                        key.startswith(("Key", "Digit")) or key in
                        ("Backquote", "Minus", "Equal", "BracketLeft", "BracketRight",
                         "Backslash", "Semicolon", "Quote", "Comma", "Period", "Slash"))
ASYNC_STATE = n.api(n.USER, "GetAsyncKeyState", c.c_short, c.c_int)
KEY_STATE = n.api(n.USER, "GetKeyState", c.c_short, c.c_int)
GET_CURSOR = n.api(n.USER, "GetCursorPos", w.BOOL, c.POINTER(w.POINT))
WINDOW_FROM_POINT = n.api(n.USER, "WindowFromPoint", w.HWND, w.POINT)


class LiveInput:
    """Owns native subscriptions, an invisible key-only hit window, and focus gating."""
    def __init__(self, ui):
        self.ui, self.root = ui, ui.root
        self.preview = LocalPreview()
        self.raw = RawKeyboard(KEY_ID)
        self.key_glow = KeyGlow()
        self.root.update_idletasks()
        self.hud_window = n.checked(n.get_ancestor(self.root.winfo_id(), 2))
        self.instance = n.checked(n.module_handle(None))
        self.class_name = f"HoloKeyboardInput_{id(self):x}"
        self.callback = n.PROC(self._window_proc)
        self.window = None
        self.job = None
        self.closed = False
        self.scene = None
        self.events = deque()
        self.pointers = {}
        self.mouse_up_checks = 0
        self.resize_mouse = False
        self.resize_up_checks = 0
        self.shift = None
        self.altgr = False
        self.cursor, self.cursor_moved, self.buttons = None, False, False
        self.armed_shown = frozenset()
        self.ime_up_checks = 0
        self.active_hkl = None
        self.profile = None
        self.profile_probe = (None, 0, None)
        self.layout_view = None
        self.pending_layout = None
        self.error = None
        self.saved_style = n.get_style(self.hud_window, -20)
        self.proc_error = None
        self.old_target = None
        self.ime_toggle_target = None
        self.rects = ()
        self.mouse_filter = KoreanMouseFilter(self)
        wc = n.WindowClass(proc=self.callback, instance=self.instance, name=self.class_name)
        n.checked(n.register_class(c.byref(wc)))
        try:
            self._create_surface()
            self.ui.input_driver = self
            self.root.bind("<Configure>", self._move_event, add="+")
            self.root.bind("<Unmap>", self._move_event, add="+")
            self.root.bind("<Map>", self._move_event, add="+")
            self.set_mirror(self.ui.mirror)
            self._poll()
        except Exception:
            self.close()
            raise

    def _create_surface(self):
        """The invisible key-only hit window, owned by the HUD's native top-level window."""
        self.hud_window = n.checked(n.get_ancestor(self.root.winfo_id(), 2))
        self.saved_style = n.get_style(self.hud_window, -20)
        # No redirection bitmap: hit testing without painting over the design.
        styles = 0x08000000 | 0x00200000 | 0x00000080
        self.window = n.checked(n.create_window(styles, self.class_name, "", 0x80000000,
                                                 0, 0, 0, 0, self.hud_window, None,
                                                 self.instance, None))
        n.set_style(self.hud_window, -20, self.saved_style | 0x08000000)

    def _surface_current(self):
        return (n.is_window(self.window) and
                n.get_ancestor(self.root.winfo_id(), 2) == self.hud_window)

    def _recreate_surface(self):
        """Minimize/restore makes Tk replace the native HUD window, which destroys the owned
        hit window (and with it the Raw Input target). Rebuild both so keys keep working."""
        self._cancel_pointers()
        self.mouse_filter.suspend()
        if n.is_window(self.window):
            n.destroy_window(self.window)
        enabled, self.raw.enabled = self.raw.enabled, False
        self._create_surface()
        self.scene, self.rects = None, ()
        self.set_mirror(enabled)

    @property
    def sticky(self):
        """Armed Ctrl/Alt/Win by family (Shift stays in self.shift)."""
        return self.__dict__.setdefault("_sticky", {})

    def refresh(self):
        if self.closed:
            return
        target = focused_target()
        layout = target.layout if target else None
        toggled = self.ime_toggle_target is not None and self.ime_toggle_target == target
        self.ime_toggle_target = None
        language = language_state(target, toggled=toggled, layout=layout)
        show = self.ui.input_visible and bool(self.root.winfo_viewable())
        enabled = show and not self.ui.input_locked
        protected = self.ui.guard.update(target if enabled else None)
        self.ui.guard_verdict = protected, self.ui.guard.reason
        fallback = language not in ("KR", "EN") and self.ui.local_mode in ("KR", "EN")
        mode = self.ui.local_mode if fallback else language
        suspended = self.ui.guard.suspended
        scope = ((target, layout, mode, self.ui.guard.proof, fallback)
                 if enabled and target and (not protected or suspended) else None)
        self.preview.set_target(scope, suspended)
        self._update_mouse_filter(bool(self.scene and layout and layout & 0x3ff == 0x12
                                       and language != "EN"
                                       and target.window not in (self.window, self.hud_window)))
        changed_target = target != self.old_target
        if changed_target or layout != self.active_hkl:
            self.old_target = target
            self.active_hkl = layout
            self.shift = None
            self.sticky.clear()
            self._sync_armed()
            self.altgr = False
            self.error = None
            self._cancel_pointers()
            if changed_target and not self.pending_layout:
                self.ui.set_profile_notice(None, None)
        status, text = "", ""
        if show:
            if self.ui.input_locked:
                status = "입력 잠김"
            elif self.error:
                status = self.error
            else:
                status, text = self.preview.display()
        self.ui.set_live_status(language, status, text)
        self._refresh_layout(target, layout, language)
        self._check_layout_request(target, layout)

    def _refresh_layout(self, target, hkl, mode):
        thread = target.thread if target else None
        identity, checked_at, profile = self.profile_probe
        if (thread, hkl) != identity or monotonic()-checked_at > 1:
            profile = profiles.active_standard(hkl, thread)
            if not profile and profiles.korean_base(hkl):
                profile = profiles.PROFILES["KR"]
            elif not profile and hkl and hkl & 0xffff in profiles.IME:
                profile = profiles.own_active_tip(hkl, thread)
            self.profile_probe = ((thread, hkl), monotonic(), profile)
        if profile != self.profile and not self.pending_layout:
            self.ui.set_profile_notice(None, None)
        self.profile = profile
        caps = bool(KEY_STATE(0x14) & 1)
        shift = bool(self.shift or ASYNC_STATE(0x10) & 0x8000)
        can_altgr = bool(profile and not profile.tip and profiles.has_altgr(hkl, PRINTABLE_SCANS))
        altgr = bool(can_altgr and (self.altgr or ASYNC_STATE(0xa5) & 0x8000))
        state = (hkl, profile.code if profile else None, mode, shift, caps, can_altgr, altgr)
        if state == self.layout_view:
            return
        self.layout_view = state
        # A confirmed Korean conversion mode is read only from the target context.
        # An unobservable IME shows base key engravings, not invented composition.
        captions = {key.code: profiles.key_caption(hkl, SCAN.get(key.code), key, mode,
                                                    shift, caps, altgr)
                    for key in self.ui.keys if not key.special}
        self.ui.set_profile_view(profile.code if profile else None, captions, caps,
                                 can_altgr, altgr, bool(hkl and n.is_ime(hkl)))

    def select_layout(self, code):
        requested = profiles.PROFILES.get(code)
        if not requested:
            return
        target = focused_target()
        if not target or target.window in (self.window, self.hud_window):
            self.ui.set_profile_notice(code, "대상 창 없음")
            return
        if (target == self.old_target and target.layout == self.active_hkl
                and self.profile and self.profile.code == code):
            self.ui.set_profile_notice(code, "활성")
            return
        if requested.tip:
            enabled = profiles.ime_available(requested, profiles.available_layouts() if code == "KR" else None)
            self.ui.set_profile_notice(code, "Windows에 없음" if enabled is False else "Win+Space")
            return
        layouts = profiles.available_layouts()
        if layouts is None:
            self.ui.set_profile_notice(code, "확인 불가")
            return
        match = next((h for h in layouts if profiles.active_standard(h, None) == requested), None)
        if not match:
            self.ui.set_profile_notice(code, "Windows에 없음")
            return
        if target.layout == match:
            self.ui.set_profile_notice(code, "활성")
            return
        if focused_target() != target or not profiles.request_layout(target.focus, match):
            self.ui.set_profile_notice(code, "Win+Space")
            return
        self.pending_layout = (target, match, code, monotonic()+1.0)
        self.ui.set_profile_notice(code, "전환 확인 중")

    def _check_layout_request(self, target, hkl):
        if not self.pending_layout:
            return
        recipient, requested, code, deadline = self.pending_layout
        if target == recipient and hkl == requested:
            self.ui.set_profile_notice(code, "활성")
        elif target != recipient or monotonic() >= deadline:
            self.ui.set_profile_notice(code, "Win+Space")
        else:
            return
        self.pending_layout = None

    def profile_availability(self):
        return profiles.availability()

    def _poll(self):
        self._sync_surface()
        self._watch_pointer()
        self.refresh()
        self._drain_native()
        if self.resize_mouse:
            point = w.POINT()
            if ASYNC_STATE(1) & 0x8000:
                self.resize_up_checks = 0
                if GET_CURSOR(c.byref(point)):
                    self.ui.move_resize(point.x)
            else:
                self.resize_up_checks += 1
                if self.resize_up_checks >= 4:
                    self.resize_mouse = False
                    self.ui.end_resize()
        # A nonactivated window cannot retain mouse capture across every app.
        if "mouse" in self.pointers and not ASYNC_STATE(1) & 0x8000:
            self.mouse_up_checks += 1
            if self.mouse_up_checks >= 4:
                self._cancel_pointers(mouse_only=True)
        else:
            self.mouse_up_checks = 0
        if "ime-mouse" in self.pointers and not self.mouse_filter.held:
            self.ime_up_checks = getattr(self, "ime_up_checks", 0)+1
            if self.ime_up_checks >= 4:  # hook lost its release; never leave a key stuck
                self._cancel_pointers_named("ime-mouse")
        else:
            self.ime_up_checks = 0
        self.job = self.root.after(16, self._poll)

    def _cancel_pointers_named(self, identifier):
        held = self.pointers.pop(identifier, None)
        if held:
            self._paint(held[0])

    def _watch_pointer(self):
        """Cursor movement and button edges anywhere may mean the focus moved inside a window.
        Edges over the HUD itself do not (it never takes focus)."""
        point = w.POINT()
        if not GET_CURSOR(c.byref(point)):
            return
        moved = (point.x, point.y) != self.cursor
        self.cursor = (point.x, point.y)
        buttons = bool((ASYNC_STATE(1) | ASYNC_STATE(2) | ASYNC_STATE(4)) & 0x8000)
        if buttons != self.buttons:
            self.buttons = buttons
            if not self._over_hud(point):
                self._invalidate_preview()
        self.cursor_moved = moved

    def _over_hud(self, point):
        hwnd = WINDOW_FROM_POINT(point)
        if not hwnd:
            return False
        root = n.get_ancestor(hwnd, 2) or hwnd
        return root in (self.window, self.hud_window, n.get_ancestor(self.ui.menu.winfo_id(), 2))

    def _update_mouse_filter(self, relevant):
        over = False
        if relevant:
            point = w.POINT()
            if GET_CURSOR(c.byref(point)):
                packed = (point.x & 0xffff) | ((point.y & 0xffff) << 16)
                key = self._hit(self.window, packed, screen=True)
                over = bool(key and key != "__resize__")
        self.mouse_filter.update(relevant, over, getattr(self, "cursor_moved", False))

    def _sync_armed(self):
        ui = self.__dict__.get("ui")
        armed = frozenset(code for code in (self.shift, *self.sticky.values()) if code)
        if ui is not None and armed != self.__dict__.get("armed_shown", frozenset()):
            self.armed_shown = armed
            ui.set_armed(armed)

    def layout_changed(self):
        """The HUD switched between Compact and Full: key rectangles and captions are stale."""
        self.layout_view, self.rects, self.scene = None, (), None
        self.shift, self.altgr = None, False
        self.sticky.clear()
        self._cancel_pointers()
        self._sync_armed()

    def _drain_native(self):
        # Tk must never be entered from a ctypes callback inside its Win32 message pump.
        while self.events:
            handler, args = self.events.popleft()
            handler(*args)

    def _move_event(self, event):
        if event.widget is self.root and not self.closed:
            self._sync_surface()

    def _sync_surface(self):
        mapped = self.root.winfo_viewable() and self.root.state() == "normal"
        if not mapped:
            self.mouse_filter.suspend()
            if self.scene is not None:
                n.show_window(self.window, 0)
                self.scene = None
                self._cancel_pointers()
                self.reset_glow()
                self.resize_mouse = False
                self.ui.end_resize()
            return
        if not self._surface_current():
            self._recreate_surface()
        scene = (self.root.winfo_rootx(), self.root.winfo_rooty(), self.root.winfo_width(),
                 self.root.winfo_height(), self.ui.scale)
        if scene == self.scene:
            return
        self.scene = scene
        x, y, width, height, scale = scene
        if not self.rects or self.rects[0] != scale:
            boxes = tuple((key.code, tuple(round(p*scale) for p in key.bounds))
                          for key in self.ui.keys) + (
                              ("__resize__", tuple(round(p*scale) for p in self.ui.resize_bounds)),
                          )
            full_region = n.checked(n.make_region(0, 0, 0, 0))
            try:
                for _, coords in boxes:
                    part = n.checked(n.make_region(*coords))
                    try:
                        n.checked(n.merge_region(full_region, full_region, part, 2))
                    finally:
                        n.delete_region(part)
                n.checked(n.set_region(self.window, full_region, True))
                full_region = None  # Win32 now owns this region.
            finally:
                if full_region:
                    n.delete_region(full_region)
            self.rects = (scale, boxes)
        n.checked(n.set_pos(self.window, -1, x, y, width, height, 0x50))

    def set_mirror(self, enabled):
        if not self.raw.set_enabled(enabled, self.window):
            return
        if not enabled:
            self.preview.set_target(None)
            self.events = deque(event for event in self.events if event[0] != self._transition)
            self.reset_glow()
        for code, _ in self.pointers.values():
            self._paint(code)

    def reset_glow(self):
        for code in self.key_glow.clear():
            self._paint(code)

    def _invalidate_preview(self):
        self.preview.set_target(None)
        self.ui.guard.mark_dirty()

    def _preview_key(self, code, *, shift=None, shortcut=None):
        if (not self.ui.input_visible or self.ui.input_locked or self.preview.token is None
                or not self.ui.guard.can_accept()):
            return
        target, layout, *_ = self.preview.scope
        current = focused_target()
        if (current != target or current.layout != layout or
                (self.ui.guard.reason == "win32-plain" and self.ui.guard.win32(target.focus) != "plain")):
            self._invalidate_preview()
            return
        if shortcut is None:
            shortcut = any(ASYNC_STATE(vk) & 0x8000 for vk in (0x11, 0x12, 0x5b, 0x5c))
        if shortcut or code in NAV_KEYS:
            self._invalidate_preview()
            return
        if shift is None:
            shift = bool(ASYNC_STATE(0x10) & 0x8000)
        self.preview.key(code, SCAN.get(code), shift, bool(KEY_STATE(0x14) & 1))

    def _transition(self, key, verified_token):
        if not self.raw.enabled:
            return
        if key.down:
            if key.code == "LangToggle":
                self.ime_toggle_target = self.old_target
            if self.ui.diag is not None:
                self.ui.diag["raw"] += 1
                if self.ui.input_locked:
                    self.ui.diag["raw_locked"] += 1
        if not self.ui.input_locked:
            released = self.key_glow.update(key)
            self._paint(key.code)
            if released:
                self.ui.release_glow(key.code)
        if key.down:
            if key.code in NAV_KEYS:
                self._invalidate_preview()
            elif verified_token is not None and verified_token is self.preview.token:
                self._preview_key(key.code)

    def _remove_device(self, device):
        for code in self.key_glow.remove(device):
            self._paint(code)

    def _paint(self, code):
        physical = self.key_glow.active(code)
        down = physical or any(code == held for held, _ in self.pointers.values())
        self.ui.paint_live_key(code, down, physical=physical)

    def _hit(self, hwnd, packed, screen=False):
        point = w.POINT(c.c_short(packed & 0xffff).value, c.c_short((packed >> 16)&0xffff).value)
        if screen and not n.screen_to_client(hwnd, c.byref(point)):
            return None
        for code, (x0, y0, x1, y1) in self.rects[1] if self.rects else ():
            if x0 <= point.x < x1 and y0 <= point.y < y1:
                return code
        return None

    def _pointer(self, identifier, code, down, target=None):
        if code == "__resize__":
            code = None
        if down:
            if (code and identifier not in self.pointers and target and
                    focused_target() == target and
                    target.window not in (self.window, self.hud_window)):
                self.pointers[identifier] = (code, target)
                if identifier == "mouse":
                    self.mouse_up_checks = 0
                self._paint(code)
        else:
            held = self.pointers.pop(identifier, None)
            if held:
                key, target = held
                self._paint(key)
                if key == code:
                    self._deliver(key, target)

    def _queue_pointer(self, identifier, code, down):
        target = focused_target() if down else None
        self.events.append((self._pointer, (identifier, code, down, target)))

    def _cancel_pointers(self, mouse_only=False):
        for pointer in tuple(self.pointers):
            if not mouse_only or pointer == "mouse":
                code, _ = self.pointers.pop(pointer)
                self._paint(code)

    def _deliver(self, code, target):
        if (self.closed or self.pending_layout or focused_target() != target
                or target.layout != self.active_hkl):
            return
        if code in MODIFIERS:
            # Shift/Ctrl/Alt/Win are sticky one-shot: the next key carries them.
            family = MODIFIERS[code][0]
            if family == "shift":
                self.shift = None if self.shift == code else code
            elif self.sticky.get(family) == code:
                del self.sticky[family]
            else:
                self.sticky[family] = code
            self._sync_armed()
            return
        if code == "Delete" and "ctrl" in self.sticky and "alt" in self.sticky:
            # Windows reserves Ctrl+Alt+Del (Secure Attention Sequence); it cannot be sent.
            self.sticky.clear()
            self.error = "Ctrl+Alt+Del 불가"
            self._sync_armed()
            return
        if code == "LangToggle":
            if self.layout_view and self.layout_view[5]:
                self.altgr = not self.altgr
                return
            if not target.layout or target.layout & 0x3ff != 0x12:
                return
            events = [n.scan_event(0, vk=0x15), n.scan_event(0, up=True, vk=0x15)]
        else:
            scan = SCAN.get(code)
            if scan is None:
                return
            ext, vk = scan > 0xff, VK_ONLY.get(code, 0)
            events = [n.scan_event(scan & 0xff, extended=ext, vk=vk),
                      n.scan_event(scan & 0xff, up=True, extended=ext, vk=vk)]
        armed = {"shift": self.shift, **self.sticky}
        if code not in ("CapsLock", "LangToggle"):
            # Innermost wrap first, so presses go out Ctrl, Alt, Win, Shift and release in reverse.
            for family in reversed(MOD_ORDER):
                held = armed.get(family)
                if held and not ASYNC_STATE(MODIFIERS[held][1]) & 0x8000:
                    scan, ext = SCAN[held] & 0xff, SCAN[held] > 0xff
                    events = [n.scan_event(scan, extended=ext), *events,
                              n.scan_event(scan, up=True, extended=ext)]
        if self.shift or self.sticky:
            self.shift = None
            self.sticky.clear()
            self._sync_armed()
        if self.altgr and code not in ("CapsLock", "LangToggle"):
            if not ASYNC_STATE(0xa5) & 0x8000:
                events = [n.scan_event(ALTGR_SCAN & 0xff, extended=True), *events,
                          n.scan_event(ALTGR_SCAN & 0xff, up=True, extended=True)]
            self.altgr = False
        count = n.send_events(events)
        if count != len(events):
            pending = {}
            for event in events[:count]:
                key = event.value.keyboard
                identity = (key.scan, bool(key.flags & 1), key.vk)
                if key.flags & 2:
                    pending.pop(identity, None)
                else:
                    pending[identity] = True
            if pending:
                n.send_events([n.scan_event(scan, True, ext, vk)
                               for scan, ext, vk in reversed(pending)])
            self.error = "Windows 입력 제한"
        else:
            self.error = None
            if code == "LangToggle":
                self.ime_toggle_target = target
            self._preview_key(code, shift=True if armed.get("shift") else None,
                              shortcut=True if set(armed) & {"ctrl", "alt", "win"} else None)

    def _window_proc(self, hwnd, message, wp, lp):
        try:
            if message in (0x21, 0x024b):  # WM_MOUSEACTIVATE / WM_POINTERACTIVATE
                return 3  # MA_NOACTIVATE / PA_NOACTIVATE
            if message == 0x00ff and self.raw.enabled:
                key = self.raw.read(lp)
                if key is not None:
                    self.events.append((self._transition, (key, self.preview.token)))
            elif message == 0x00fe and wp == 2:
                self.events.append((self._remove_device, (lp,)))
            elif message in (0x0201, 0x0202):
                if n.message_extra() & 0xffffff00 == 0xff515700:
                    return 0  # Windows can also promote touch/pen to mouse.
                down = message == 0x0201
                hit = self._hit(hwnd, lp)
                if down and hit == "__resize__":
                    point = w.POINT()
                    if GET_CURSOR(c.byref(point)):
                        self.resize_mouse = True
                        self.resize_up_checks = 0
                        self.events.append((self.ui.begin_resize, (point.x,)))
                        n.capture(hwnd)
                    return 0
                if not down and self.resize_mouse:
                    point = w.POINT()
                    if GET_CURSOR(c.byref(point)):
                        self.events.append((self.ui.move_resize, (point.x,)))
                    self.events.append((self.ui.end_resize, ()))
                    self.resize_mouse = False
                    n.release_capture()
                    return 0
                if down:
                    n.capture(hwnd)
                self._queue_pointer("mouse", hit, down)
                if not down:
                    n.release_capture()
                return 0
            elif message == 0x0215:
                self.events.append((self._cancel_pointers, (True,)))
            elif message in (0x0246, 0x0247, 0x024c):
                pointer = wp & 0xffff
                if message == 0x024c:
                    self._queue_pointer(pointer, None, False)
                else:
                    kind = w.UINT()
                    if n.pointer_type(pointer, c.byref(kind)) and kind.value in (2, 3):
                        self._queue_pointer(pointer, self._hit(hwnd, lp, True), message == 0x0246)
                        return 0
        except Exception as exc:
            self.proc_error = type(exc).__name__
        return n.def_window(hwnd, message, wp, lp)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.preview.set_target(None)
        self.mouse_filter.close()
        self.ui.guard.close()
        if self.job:
            self.root.after_cancel(self.job)
        try:
            self.set_mirror(False)
        finally:
            if self.window:
                n.destroy_window(self.window)
            n.unregister_class(self.class_name, self.instance)
            n.set_style(self.hud_window, -20, self.saved_style)
            self.events.clear()

