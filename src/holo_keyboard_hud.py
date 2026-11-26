"""Design-stage Windows HUD based on the v8 palette, legends and Canvas."""
import colorsys
import ctypes
import re
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import hud_i18n
import input_profiles as profiles
import win_native as win
from full_layout import FN_ROW_GAP, FULL_ROW_COUNT, FULL_UNITS, full_specs
from hud_help import open_help, translate
from hud_text import label_image
from hud_tooltip import Tooltip
from mirror_guard import MirrorGuard
from product import BRAND, PASSWORD_WARNING, PRODUCT, SupportSettings, show_about, show_support
from v8_layout import COLOR_THEMES, KEY_ROWS, LANG_TOGGLE_LABELS, LAYOUTS, LANG_LIST

# V1: the key glow is stopped only by the manual Input Lock. The automatic password/field guard keeps running
# for text reading (one-line preview, input linking) but does not gate the glow. Setting this to True restores
# the earlier automatic echo lock (kept for the planned "automatic password detection" improvement).
CHROMA = "#010203"
MENU_BG = "#101923"
WIDTH, HEIGHT = 729, 374
KEY_TOP, PITCH, GAP, KEY_HEIGHT = 113, 47, 4.25, 39.75
MENU_TOP, MENU_HEIGHT = 31, 76
COLLAPSED_OFFSET = 82
RING_INSET = 2.5
INNER_BRIGHTNESS = .6
PHYSICAL_GLOW_MS, PASSWORD_WARNING_HEIGHT = 240, 21
KEY_MARGIN = (WIDTH-15*PITCH+GAP)/2
INPUT_BOX = (KEY_MARGIN, 336, WIDTH-KEY_MARGIN, 366)
RESIZE_BOX = (691, 344, 713, 364)
# Full layout: wider by the navigation block and keypad, taller by one function row.
FULL_WIDTH = round(FULL_UNITS*PITCH-GAP+2*KEY_MARGIN)
FULL_KEY_BOTTOM = KEY_TOP+(FULL_ROW_COUNT-1+FN_ROW_GAP)*(KEY_HEIGHT+GAP)+KEY_HEIGHT
FULL_HEIGHT = round(FULL_KEY_BOTTOM+7.25+30+8)
FULL_INPUT_BOX = (KEY_MARGIN, FULL_HEIGHT-38, FULL_WIDTH-KEY_MARGIN, FULL_HEIGHT-8)
FULL_RESIZE_BOX = (FULL_WIDTH-38, FULL_HEIGHT-30, FULL_WIDTH-16, FULL_HEIGHT-10)
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
INPUT_COLORS = {"자동": "#ffffff", "검정": "#181818", "흰색": "#ffffff", "테마색": None}
SPECIAL_WIDTHS = {
    "Backspace": 2, "Tab": 1.5, "Backslash": 1.5, "CapsLock": 1.75,
    "Enter": 2.25, "ShiftLeft": 2.25, "ShiftRight": 2.75,
    "LangToggle": 1.5, "Space": 6.25, "ArrowLeft": 1, "ArrowRight": 1,
}


@dataclass(frozen=True)
class Key:
    code: str
    normal: str
    shifted: str
    special: str | None
    bounds: tuple[float, float, float, float]


def make_keys():
    keys = []
    for index, row in enumerate(KEY_ROWS):
        widths = [SPECIAL_WIDTHS.get(code, width) for code, _, _, width, _ in row]
        x = (WIDTH - sum(widths) * PITCH + GAP) / 2
        y = KEY_TOP + index * (KEY_HEIGHT + GAP)
        for (code, normal, shifted, _, special), units in zip(row, widths):
            right = x + units * PITCH - GAP
            keys.append(Key(code, normal, shifted, special, (x, y, right, y + KEY_HEIGHT)))
            x += units * PITCH
    return keys


def make_full_keys():
    """Every key of the standard Full layout, placed on the same pitch/gap/size as Compact."""
    keys = []
    for code, normal, shifted, special, x, row, units, tall in full_specs(SPECIAL_WIDTHS):
        left = KEY_MARGIN+x*PITCH
        top = KEY_TOP+(row+(FN_ROW_GAP if row else 0))*(KEY_HEIGHT+GAP)
        keys.append(Key(code, normal, shifted, special,
                        (left, top, left+units*PITCH-GAP,
                         top+(tall-1)*(KEY_HEIGHT+GAP)+KEY_HEIGHT)))
    return keys


def dim_color(color, factor):
    return "#" + "".join(f"{round(channel*factor):02x}" for channel in bytes.fromhex(color[1:]))


CAPS_AMBER, CAPS_PINK = "#ffb000", "#ff2d95"


def mix_color(first, second, amount):
    a = bytes.fromhex(first.lstrip("#"))
    b = bytes.fromhex(second.lstrip("#"))
    return "#" + bytes(round(x+(y-x)*amount) for x, y in zip(a, b)).hex()


def caps_color(theme):
    """Caps Lock ON glow: fixed amber, or hot pink on themes whose own glow is amber/lime-like.
    Never equal to the theme glow used for ordinary key presses."""
    hue = colorsys.rgb_to_hsv(*(v/255 for v in bytes.fromhex(theme["highlight"][1:])))[0]*360
    return CAPS_PINK if abs(hue-41) < 50 else CAPS_AMBER


class HoloKeyboardHUD:
    def __init__(self, root: tk.Tk, *, support_settings=None):
        self.root = root
        self.support_settings = support_settings if support_settings is not None else SupportSettings()
        self.guard_verdict = (False, "")  # the field guard's answer for the local display
        self.product_dialog = None
        self.keys = make_keys()
        self.layout_mode = "compact"
        self.width, self.height = WIDTH, HEIGHT
        self.input_box = INPUT_BOX
        self.guard = MirrorGuard()
        # No driver, no external echo. LiveInput's first refresh arms the guard (fail closed).
        self.mirror_locked, self.lock_reason = False, ""
        self.armed = frozenset()
        self.render_hooks = []
        self.key_glow = {}
        self.glow_applied = set()
        self.notice_text, self.notice_job = "", None
        self.theme_name, self.language = "blue", "KR"
        self.ui_language = "EN"
        self.help_window = None
        self.diagnostics = None
        self.opacity, self.thickness, self.scale = 1.0, 1.0, 1.0
        self.mirror = True
        self.caps_on = False
        self.glow_mode = "realtime"
        self.last_key = None
        self.physical_pressed = set()
        self.last_physical = False
        self.resize_bounds = RESIZE_BOX
        self.input_driver = None
        self.input_locked = False
        self.release_jobs = {}
        self.tips = {"header": {}, "details": {}, "main": {}}  # box -> tooltip key, filled by render
        self.tooltip = Tooltip(root)
        self._installed = (0.0, None)  # (checked at, installed profile codes)
        self._settings_tips = ()
        self._tail_fonts = {}
        self.live_language = None
        self.profile_code = None
        self.country_profile = None
        self.layout_captions = None
        self.layout_is_ime = False
        self.altgr_available = self.altgr_on = False
        self.profile_notice = (None, None)
        self.live_status = ""
        self.live_text = ""
        self.live_image = None
        self.input_visible = True
        self.local_mode = "자동"
        self.input_sample = ""
        self.correction_preview = self.follow_preview = False
        self.input_color = "자동"
        self.menu_target, self.menu_fraction = 1.0, 1.0
        self.menu_job = None
        self.menu_values = {}
        self.controls = {}
        self.header_controls = {}
        self.header_offset = 0
        self.details_controls = {}
        self.key_items = {}
        self.pressed = set()
        self.drag = None
        self.adjustment = None
        self.minimized = False
        self.diag = None             # --diagnose only: raw key counters (counts, never key identities)
        self.popup_open = False
        self.docked = False          # embedded under the typing-practice window (header/grip hidden)
        self._dock_saved = None

        root.title(f"{PRODUCT} — {BRAND}")
        root.configure(bg=CHROMA)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.wm_attributes("-transparentcolor", CHROMA)
        work = win.primary_work_area()
        left, top, right = (work.left, work.top, work.right) if work else (0, 0, root.winfo_screenwidth())
        x = left + max(0, (right - left - round(self.width * self.scale)) // 2)
        root.geometry(f"{x:+d}{top:+d}")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Map>", self._restore, add="+")
        self._set_icon()
        self._taskbar_button()

        self.main = self._canvas(root)
        self.main.pack(fill="both", expand=True)
        # The key window keeps its color key and opacity slider. The menu has
        # its own opaque surface, so the slider cannot fade its controls.
        self.menu = tk.Toplevel(root, bg=MENU_BG)
        self.menu.withdraw()
        self.menu.overrideredirect(True)
        self.menu.transient(root)
        self.menu.attributes("-topmost", True)
        self.header = self._canvas(self.menu, MENU_BG)
        self.settings_menu = tk.Menu(self.menu, tearoff=False)
        self.settings_menu.bind("<<MenuSelect>>", self._settings_hover, add="+")
        self.menu_clip = tk.Frame(self.menu, bg=MENU_BG, bd=0, highlightthickness=0)
        self.details = self._canvas(self.menu_clip, MENU_BG)
        self._bind_pointer(self.main, self.controls)
        self._bind_pointer(self.header, self.header_controls)
        self._bind_pointer(self.details, self.details_controls)
        for canvas, bucket in ((self.main, "main"), (self.header, "header"), (self.details, "details")):
            canvas.bind("<Motion>", lambda event, name=bucket: self._hover(event, name), add="+")
            canvas.bind("<Leave>", lambda _event: self.tooltip.hide(), add="+")
            canvas.bind("<ButtonPress>", lambda _event: self.tooltip.hide(), add="+")
        for sequence in ("<Configure>", "<Map>", "<Unmap>"):
            root.bind(sequence, self._track_menu, add="+")
        self.render()

    @staticmethod
    def _canvas(parent, background=CHROMA):
        canvas = tk.Canvas(parent, bg=background, bd=0, highlightthickness=0)
        canvas.label_images = []
        return canvas

    def _bind_pointer(self, canvas, controls):
        canvas.bind("<ButtonPress-1>", lambda event: self._pointer_down(event, controls))
        canvas.bind("<B1-Motion>", self._pointer_move)
        canvas.bind("<ButtonRelease-1>", self._pointer_up)

    @property
    def theme(self):
        return COLOR_THEMES[self.theme_name]

    def tr(self, text):
        return translate(self.ui_language, text)

    # ---- program display language: one accessor for every module (typing practice included) ----
    @property
    def ui_lang(self):
        """'EN' or 'KO': the program's display language (never the keyboard input language)."""
        return "KO" if self.ui_language == "KO" else "EN"

    def t(self, en, ko):
        """The English or Korean variant of a text for the current UI language."""
        return hud_i18n.pick(self.ui_lang, en, ko)

    # ---- tooltips ------------------------------------------------------------------------------
    def _hover(self, event, bucket):
        if self.drag or self.adjustment:
            self.tooltip.hide()
            return
        x, y = event.x/self.scale, event.y/self.scale
        key = next((k for (x0, y0, x1, y1), k in self.tips[bucket].items()
                    if x0 <= x <= x1 and y0 <= y <= y1), None)
        self.tooltip.hover(key, lambda k=key: self.tip_text(k), event.x_root, event.y_root)

    def tip_text(self, key):
        lang = self.ui_lang
        if key.startswith("lang:"):
            code = key[5:]
            profile = profiles.PROFILES.get(code)
            state = self.language_states().get(code)
            installed = self.installed_languages()
            status = (hud_i18n.pick(lang, "Current input language", "현재 입력 언어") if state == "current" else
                      hud_i18n.pick(lang, "English companion indicator; a separate US layout requires its own Windows profile.",
                                    "영문 동반 표시입니다. 별도 미국식 자판은 Windows 프로필이 필요합니다.")
                      if code == "EN" and state == "selected" else
                      hud_i18n.pick(lang, "Selected", "선택됨") if state == "selected" else
                      hud_i18n.pick(lang, "Availability unknown", "사용 가능 여부 확인 불가") if installed is None else
                      hud_i18n.pick(lang, "Profile unavailable", "프로필 사용 불가")
                      if installed is not None and code not in installed else
                      hud_i18n.pick(lang, "Installed", "설치됨"))
            return f"{code} — {profile.name if profile else code}\n{status}\n{hud_i18n.pick(lang, *hud_i18n.LANG_TIP)}"
        if key.startswith("theme:"):
            return hud_i18n.pick(lang, f"Color theme: {key[6:]}", f"색 테마: {key[6:]}")
        text = hud_i18n.tip_text(lang, key)
        if key == "status" and self.mirror and self.mirror_locked:
            why = hud_i18n.LOCK_EXPLAIN.get(self.lock_reason)
            if why:
                text += "\n" + hud_i18n.pick(lang, *why)
        return text

    def _settings_hover(self, _event):
        """Tooltip for the highlighted ⚙ menu entry (Windows sends <<MenuSelect>> while it moves)."""
        try:
            index = self.settings_menu.index("active")
        except tk.TclError:
            index = None
        if not isinstance(index, int) or not 0 <= index < len(self._settings_tips):
            self.tooltip.hide()
            return
        key = self._settings_tips[index]
        x, y = self.root.winfo_pointerxy()
        self.tooltip.hover(key, lambda: self.tip_text(key), x+150, y)

    def show_help(self):
        if self.help_window and self.help_window.winfo_exists():
            self.help_window.lift()
            return
        availability = self.input_driver.profile_availability() if self.input_driver else {}
        self.help_window = open_help(self.root, self.ui_language, availability)

    def show_settings(self):
        self.settings_menu.delete(0, "end")
        self.settings_menu.add_command(label=self.tr("키보드 진단"), command=self.open_diagnostics,
                                       state="normal" if self.input_driver else "disabled")
        self.settings_menu.add_command(
            label=self.tr("Compact 배열로 전환" if self.layout_mode == "full" else "Full 배열로 전환"),
            command=self.toggle_layout)
        self.settings_menu.add_command(label=self.tr("동화 타자 연습"), command=self.open_story_typing)
        self.settings_menu.add_command(label=self.input_lock_label(),
                                       command=self.toggle_input_lock,
                                       state="normal" if self.input_driver else "disabled")
        self.settings_menu.add_command(label=self.t("Donate", "후원"), command=self.open_support)
        self.settings_menu.add_command(label=self.t("About", "제품 정보"), command=self.open_about)
        self._settings_tips = ("set:diag", "set:layout", "set:story", "set:lock", "set:donate", "set:about")
        self.tooltip.hide()
        self.popup_open = True  # a redraw during the popup must not raise the top bar over it
        try:
            self.settings_menu.tk_popup(self.header.winfo_rootx()+round(96*self.scale),
                                        self.header.winfo_rooty()+self.header.winfo_height())
        finally:
            self.popup_open = False
            self.settings_menu.grab_release()
            self.tooltip.hide()

    def open_about(self):
        self._show_product_dialog(lambda: show_about(self.root, self.t))

    def open_support(self):
        self._show_product_dialog(lambda: show_support(self.root, self.t, self.support_settings,
                                                       self._apply_support_styles))

    def _show_product_dialog(self, open_dialog):
        if self.product_dialog is not None and self.product_dialog.winfo_exists():
            self.product_dialog.destroy()
        self.product_dialog = open_dialog()
        self.product_dialog.lift()

    def _apply_support_styles(self):
        if not self.support_settings.confirmed:
            self.theme_name, self.thickness = "blue", 1.0
            self.menu_values.pop("thickness", None)
        self.render()

    def open_diagnostics(self):
        if not self.input_driver or self.input_driver.closed:
            return
        if self.diagnostics is None or not self.diagnostics.window.winfo_exists():
            from keyboard_diagnostics import KeyboardDiagnostics
            self.diagnostics = KeyboardDiagnostics(self.root, self.input_driver, physical=True)
        self.diagnostics.focus(self.diagnostics.normal)

    def open_story_typing(self):
        """Lazy hook for the separate typing-practice module; absent module is not an error.
        Used by both the option-row 'Typing Practice' button and the ⚙ 'Story Typing' entry."""
        try:
            import typing_practice
            typing_practice.open(self)
        except ImportError:
            self.notice("타자 모듈 없음")
        except Exception:  # a broken practice module must not take the keyboard down
            self.notice("타자 모듈 오류")

    def input_lock_label(self):
        return f"{self.tr('입력 잠금')}: {'ON' if self.input_locked else 'OFF'}"

    def toggle_input_lock(self):
        self.input_locked = not self.input_locked
        if self.input_locked:
            self.live_text = ""
        self.sync_input_lock()
        if self.input_driver:
            self.input_driver.refresh()
        self.render()

    def status_label(self):
        """The text of the header status slot (profile, manual lock or a notice)."""
        code, note = self.profile_notice
        if self.notice_text:
            return self.tr(self.notice_text)
        if note:
            return f"{code}: {self.tr(note)}"
        if self.mirror and self.mirror_locked:
            return hud_i18n.lock_label(self.ui_lang, self.lock_reason)
        return self.profile_code or self.tr("프로필 확인 불가")

    def installed_languages(self):
        """Exact profile codes usable on this Windows, cached for a few seconds.
        None when Windows cannot list them."""
        checked, codes = self._installed
        if monotonic()-checked > 5.0:
            try:
                codes = profiles.installed_codes()
            except Exception:
                codes = None
            self._installed = (monotonic(), codes)
        return codes

    def language_states(self):
        """{code: 'current' | 'selected'} for the language buttons. A selected country layout lights
        itself and EN; the language really being typed (live Hangul/English state) is 'current'
        (drawn brighter). Languages that are not installed on this Windows are never lit."""
        chosen = self.profile_code if self.input_driver else self.language
        if chosen == "EN" and self.input_driver and self.country_profile:
            chosen = self.country_profile
        if not chosen:
            return {}
        states = {chosen: "selected", "EN": "selected"}
        if self.input_driver:
            live = self.live_language if self.live_language in ("KR", "EN") else None
            current = live or (chosen if chosen != "KR" else None)
            if current:
                states[current] = "current"
        installed = self.installed_languages()
        if self.input_driver:
            if installed is not None:
                states = {code: state for code, state in states.items() if code in installed or
                          (code == "EN" and chosen in installed)}
            elif chosen != self.profile_code and self.profile_code == "EN":
                states.pop(chosen, None)
        return states

    def fit_tail(self, text, suffix=""):
        """The end of `text` (where typing happens) that fits the one-line display together with
        `suffix`; a leading ellipsis marks what was cut. Never touches the label cache."""
        import tkinter.font as tkfont
        px = max(8, round(16*self.scale))
        font = self._tail_fonts.get(px)
        if font is None:
            font = self._tail_fonts[px] = tkfont.Font(root=self.root, family="Malgun Gothic",
                                                      size=-px, weight="bold")
        room = (round((self.resize_bounds[0]-self.input_box[0]-18)*self.scale)-8)*.94
        if font.measure(text+suffix) <= room:
            return text
        low, high = 0, len(text)
        while low < high:  # longest tail that fits behind "…"
            mid = (low+high+1)//2
            if font.measure("…"+text[-mid:]+suffix) <= room:
                low = mid
            else:
                high = mid-1
        return "…"+text[-low:] if low else "…"

    def notice(self, text, seconds=4):
        """Short message in the header status slot. Never holds user input."""
        if self.notice_job is not None:
            self.root.after_cancel(self.notice_job)
        self.notice_text = text
        self.notice_job = self.root.after(round(seconds*1000), self._clear_notice)
        self._render_header()
    def _clear_notice(self):
        self.notice_text, self.notice_job = "", None
        self._render_header()

    def register_safe_window(self, hwnd):
        """A window of this process that never holds a password may echo keys (typing practice)."""
        self.guard.register_safe_window(hwnd)

    def unregister_safe_window(self, hwnd):
        self.guard.unregister_safe_window(hwnd)

    def set_key_glow(self, code, color):
        """Persistent glow-band color for one key, independent of the mirror lock; None removes it."""
        if color is None:
            self.key_glow.pop(code, None)
        elif isinstance(color, str) and HEX_COLOR.match(color):
            self.key_glow[code] = color.lower()
        else:
            raise ValueError("glow color must be '#rrggbb' or None")
        if code in self.key_items:
            self._paint_pressed(code)

    def toggle_layout(self):
        self.set_layout("compact" if self.layout_mode == "full" else "full")

    def set_layout(self, mode):
        if mode not in ("compact", "full") or mode == self.layout_mode:
            return
        full = mode == "full"
        self.layout_mode = mode
        self.keys = make_full_keys() if full else make_keys()
        self.width, self.height = (FULL_WIDTH, FULL_HEIGHT) if full else (WIDTH, HEIGHT)
        self.input_box = FULL_INPUT_BOX if full else INPUT_BOX
        self.resize_bounds = FULL_RESIZE_BOX if full else RESIZE_BOX
        self.pressed.clear()
        self.last_key = None
        self.menu_values.clear()
        if full:  # keep the wider window on screen
            self.scale = min(self.scale, max(.72, (self.root.winfo_screenwidth()-40)/self.width))
        if self.input_driver:
            self.input_driver.layout_changed()
        self.render()
        self.root.update_idletasks()
        overflow = self.root.winfo_rootx()+self.root.winfo_width()-self.root.winfo_screenwidth()
        if overflow > 0:
            self.root.geometry(f"+{max(0, self.root.winfo_rootx()-overflow)}+{self.root.winfo_rooty()}")

    def set_docked(self, docked, scale=None):
        """Typing practice embeds the Compact keys under its own window: header menu, one-line
        display and resize grip are hidden, the window is forced Compact, and everything the user
        had (layout, size, display, menu state, position) comes back on undock."""
        docked = bool(docked)
        if docked == self.docked:
            if docked and scale is not None and abs(scale-self.scale) > .001:
                self.scale = scale
                self.render()
            return
        if docked:
            self._dock_saved = (self.layout_mode, self.scale, self.input_visible, self.resize_bounds)
            self.docked = True
            if self.layout_mode != "compact":
                self.set_layout("compact")
            self.input_visible = False
            self.resize_bounds = (0, 0, 0, 0)
            if scale is not None:
                self.scale = scale
        else:
            mode, saved_scale, visible, _bounds = self._dock_saved or ("compact", self.scale, True, RESIZE_BOX)
            self.docked = False
            self.input_visible = visible
            self.scale = saved_scale
            self.resize_bounds = FULL_RESIZE_BOX if self.layout_mode == "full" else RESIZE_BOX
            self._dock_saved = None
            if mode != self.layout_mode:
                self.set_layout(mode)
        self.render()

    def set_armed(self, codes):
        """Sticky modifiers waiting for their key stay visibly lit."""
        changed = self.armed ^ frozenset(codes)
        self.armed = frozenset(codes)
        for code in changed:
            self._paint_pressed(code)

    def sync_input_lock(self):
        """Manual key-glow lock, independent of field authorization."""
        locked = self.input_locked
        reason = "user" if locked else ""
        changed_reason = reason != self.lock_reason
        self.lock_reason = reason
        if locked == self.mirror_locked:
            if locked and changed_reason and self.mirror:
                self._render_header()  # the status text names the reason
            return
        self.mirror_locked = locked
        if locked:
            if self.input_driver:
                self.input_driver.reset_glow()
            shown = (*self.pressed, self.last_key, *self.release_jobs)
            self.clear_release_glow()
            self.pressed.clear()
            self.physical_pressed.clear()
            self.last_key = None
            for code in shown:
                if code:
                    self._paint_pressed(code)
        self._render_header()

    def toggle_ui_language(self):
        self.ui_language = "KO" if self.ui_language == "EN" else "EN"
        if self.help_window and self.help_window.winfo_exists():
            self.help_window.destroy()
            self.show_help()
        self.render()

    def toggle_glow_mode(self):
        self.glow_mode = "last" if self.glow_mode == "realtime" else "realtime"
        self.last_key = None
        self.clear_release_glow()
        self.render()

    def pixels(self, *coords):
        return tuple(round(value * self.scale, 2) for value in coords)

    def _label(self, canvas, x, y, text, size=12, *, color=None, weight=400,
               max_width=None, contrast_outline=False, cache=True, **options):
        available = round(max_width*self.scale) if max_width is not None else None
        # Live strings never become keys or values in the static glyph cache.
        draw_label = label_image if cache else label_image.__wrapped__
        image = draw_label(self.root, text, max(8, round(size*self.scale)),
                           color or self.theme["border"], weight, available, contrast_outline)
        if cache:
            canvas.label_images.append(image)
        else:
            self.live_image = image
        return canvas.create_image(*self.pixels(x, y), image=image, **options)

    def _bucket(self, canvas):
        return "header" if canvas is self.header else "details" if canvas is self.details else "main"

    def _button(self, canvas, controls, box, label, action, selected=False, tip=None, strong=False,
                dim=False, accent=None):
        """`strong`: the language being typed right now, drawn brighter than a merely selected button
        (double highlight line and highlight-colored legend)."""
        highlight = self.theme["highlight"]
        highlight = accent or highlight
        color = "#667785" if dim else highlight if selected or strong else self.theme["border"]
        fill = dim_color(highlight, .22 if strong else .13) if selected or strong else ""
        canvas.create_rectangle(*self.pixels(*box), outline=color, fill=fill,
                                width=max(1, round(self.scale * (1.6 if strong else 1))))
        x0, y0, x1, y1 = box
        if strong:
            canvas.create_rectangle(*self.pixels(x0+2.5, y0+2.5, x1-2.5, y1-2.5),
                                    outline=highlight, width=max(1, self.scale))
        self._label(canvas, (x0 + x1) / 2, (y0 + y1) / 2, label, 12,
                    color=color, weight=700 if strong else 400)
        controls[box] = action
        if tip:
            self.tips[self._bucket(canvas)][box] = tip

    def _slider(self, label, field, x, low, high):
        canvas = self.details
        self.tips["details"][(x-2, 31, x+144, 47)] = {"opacity": "opacity", "thickness": "width",
                                                      "scale": "size"}[field]
        locked = (field == "thickness" and self.input_driver and not self.support_settings.confirmed)
        self._label(canvas, x, 39, self.tr(label), anchor="w", color="#8796a3" if locked else None)
        x0, x1, y = x + (52 if label == "투명" and self.ui_language == "EN" else 37), x + 139, 39
        value = self.menu_values.get(field, getattr(self, field))
        thumb = x0 + (x1 - x0) * (value - low) / (high - low)
        canvas.create_line(*self.pixels(x0, y, x1, y), fill=self.theme["fg"],
                           width=max(2, 3 * self.scale), capstyle="round")
        canvas.create_oval(*self.pixels(thumb-4, y-4, thumb+4, y+4),
                           fill="#8796a3" if locked else self.theme["highlight"], outline="")
        if locked:
            self.tips["details"][(x-2, 31, x+144, 47)] = "locked:style"
            return
        self.details_controls[(x0-5, y-8, x1+5, y+8)] = (
            "slider", field, x0, x1, low, high
        )

    def window_height(self):
        return self.height + (PASSWORD_WARNING_HEIGHT if self.input_driver and not self.docked else 0)

    def render(self):
        self.root.geometry(f"{round(self.width*self.scale)}x{round(self.window_height()*self.scale)}")
        self.main.delete("all")
        self.live_image = None
        self.main.label_images.clear()
        self.controls.clear()
        self.tips["main"].clear()
        self.key_items.clear()
        self.tooltip.hide()
        self._render_header()
        for key in self.keys:
            self._draw_key(key)

        self._draw_input_preview()
        if self.input_driver and not self.docked and not self.input_locked:
            self._label(self.main, self.width/2, self.height+7, self.t(*PASSWORD_WARNING),
                        13, color="#f56a42", weight=700, contrast_outline=True, tags=("password-warning",))
        left, top, right, bottom = self.resize_bounds
        for offset in (0, 6) if not self.docked else ():
            self.main.create_line(*self.pixels(left+5+offset, bottom-4, right-5, top+4+offset),
                                  fill=self.theme["border"], width=max(1, self.scale))
        if not self.docked:
            self.controls[self.resize_bounds] = "resize"
            self.tips["main"][self.resize_bounds] = "grip"
        if self.input_visible:
            self.tips["main"][self.input_box] = "preview"
        self._draw_details()
        self._place_menu()
        for hook in tuple(self.render_hooks):
            try:
                hook()
            except Exception:  # an external overlay must never break the keyboard
                pass

    def _render_header(self):
        self.header.delete("all")
        self.header.label_images.clear()
        self.header_controls.clear()
        self.tips["header"].clear()
        shift = self.width-WIDTH  # window controls follow the right edge in Full
        header, controls = self.header, self.header_controls
        self._button(header, controls, (15, 5, 41, 26), "⋮⋮", "drag", tip="drag")
        header_language = (self.live_language or self.language)
        if self.input_driver and not self.layout_is_ime:
            header_language = self.profile_code or "—"
        self._button(header, controls, (47, 5, 86, 26), header_language,
                     self.toggle_menu, tip="lang")
        self._button(header, controls, (96, 5, 125, 26), "⚙", self.show_settings, tip="gear")
        code, note = self.profile_notice
        if self.notice_text or note or self.input_driver:
            # Lock reason and link state use only the approved status slot (no moved controls).
            self._label(header, 131, 16, self.status_label(), 11, anchor="w", max_width=112)
        self.tips["header"][(129, 5, 243, 26)] = "status"
        self._button(header, controls, (245, 5, 305, 26),
                     self.t("UI EN", "UI KR"), self.toggle_ui_language, tip="ui")
        mode = self.tr("실시간" if self.glow_mode == "realtime" else "마지막 키")
        self._button(header, controls, (314, 5, 437, 26), mode, self.toggle_glow_mode,
                     True, tip="mode", accent="#dec384" if self.glow_mode == "last" else None)
        self._button(header, controls, (456, 5, 483, 26), "?", self.show_help, tip="help")
        self._button(header, controls, (493, 5, 573, 26),
                     f"{self.tr('미러')}: {'ON' if self.mirror else 'OFF'}",
                     self.toggle_mirror, self.mirror, tip="mirror", dim=not self.mirror)
        self._button(header, controls, (579, 5, 650, 26),
                     ("▲ " if self.menu_target else "▼ ")+self.tr("메뉴"), self.toggle_menu, tip="menu")
        self._button(header, controls, (656+shift, 5, 682+shift, 26), "−", self.minimize, tip="min")
        self._button(header, controls, (688+shift, 5, 714+shift, 26), "×", self.close, tip="close")

    def _draw_details(self):
        canvas = self.details
        canvas.delete("all")
        canvas.label_images.clear()
        self.details_controls.clear()
        self.tips["details"].clear()
        states = self.language_states()
        installed = self.installed_languages() if self.input_driver else None
        for index, language in enumerate(LANG_LIST):
            left = 15 + index * 64
            state = states.get(language)
            self._button(canvas, self.details_controls, (left, 3, left+59, 24),
                         language, lambda lang=language: self.select_language(lang),
                         state is not None, tip=f"lang:{language}", strong=state == "current",
                         dim=state is None and installed is not None and language not in installed)
        for index, (name, palette) in enumerate(COLOR_THEMES.items()):
            x = 23 + index * 30
            locked = self.input_driver and name != "blue" and not self.support_settings.confirmed
            canvas.create_oval(*self.pixels(x-8, 32, x+8, 46),
                               outline="#8796a3" if locked else palette["border"],
                               width=max(1, self.scale),
                               fill=palette["border"] if name == self.theme_name else "")
            if not locked:
                self.details_controls[(x-10, 29, x+10, 49)] = lambda theme=name: self.select_theme(theme)
            self.tips["details"][(x-10, 29, x+10, 49)] = "locked:style" if locked else f"theme:{name}"
        self._slider("투명", "opacity", 177, .25, 1)
        self._slider("두께", "thickness", 360, .75, 2.25)
        self._slider("크기", "scale", 543, .72, 1.45)
        # Keep the existing option slots and align the controls with the keyboard.
        options = (
            (0, "입력표시", self.input_visible, "input_visible", "input"),
            (1, "조합", self.local_mode, "local_mode", "local-mode"),
            (2, "글자색", self.input_color, "input_color", "color"),
        )
        for slot, label, value, field, tip in options:
            left = 15 + slot*141
            state = ("ON" if value else "OFF") if isinstance(value, bool) else self.tr(value)
            self._button(canvas, self.details_controls, (left, 53, left+135, 73),
                         f"{self.tr(label)}: {state}", lambda option=field: self._change_option(option),
                         value is True, tip=tip, dim=field == "input_visible" and not value)
        left = 15 + 3*141
        self._button(canvas, self.details_controls, (left, 53, left+135, 73), self.tr("타자 연습"),
                     self.open_story_typing, tip="practice")
        if self.input_driver:
            left = 15 + 4*141
            self._button(canvas, self.details_controls, (left, 53, left+135, 73),
                         self.input_lock_label(), self.toggle_input_lock, self.input_locked,
                         tip="set:lock", accent="#ff9c85" if self.input_locked else None)

    def _change_option(self, field):
        if field == "input_color":
            colors = tuple(INPUT_COLORS)
            self.input_color = colors[(colors.index(self.input_color)+1) % len(colors)]
        elif field == "local_mode":
            modes = ("자동", "EN", "KR")
            self.local_mode = modes[(modes.index(self.local_mode) + 1) % len(modes)]
        else:
            setattr(self, field, not getattr(self, field))
        if self.input_driver and field in ("input_visible", "local_mode"):
            self.input_driver.refresh()
        self.render()

    def _draw_input_preview(self):
        if not self.input_visible:
            return
        x0, y0, x1, y1 = self.input_box
        self.main.create_rectangle(*self.pixels(*self.input_box), fill="",
                                   outline=self.theme["border"], width=max(1, self.scale),
                                   tags=("input-preview",))
        if self.input_driver:
            sample = self.fit_tail(self.live_text) if self.live_text else self.tr(self.live_status or "키 입력")
        else:
            sample = self.input_sample
        self._label(self.main, x0+11, (y0+y1)/2, sample or "입력 동기화",
                    16, color=INPUT_COLORS[self.input_color], weight=600,
                    contrast_outline=self.input_color == "자동",
                    max_width=self.resize_bounds[0]-x0-18, cache=not self.input_driver,
                    anchor="w", tags=("input-preview",))

    def set_live_status(self, language, status, text):
        if (language, status, text) == (self.live_language, self.live_status, self.live_text):
            return
        redraw_keys = language != self.live_language
        self.live_language, self.live_status, self.live_text = language, status, text
        if redraw_keys:
            self.render()
        else:
            self.main.delete("input-preview")
            self.live_image = None
            self._draw_input_preview()

    def set_caps_state(self, enabled):
        if self.caps_on != enabled:
            self.caps_on = enabled
            self.render()

    def set_profile_notice(self, code, notice):
        state = (code, notice)
        if state != self.profile_notice:
            self.profile_notice = state
            self.render()

    def set_profile_view(self, code, captions, caps, altgr_available, altgr, is_ime):
        self.profile_code, self.layout_captions = code, captions
        if code and code != "EN":
            self.country_profile = code
        self.caps_on = caps
        self.altgr_available, self.altgr_on = altgr_available, altgr
        self.layout_is_ime = is_ime
        self.render()

    def set_synthetic_text(self, raw):
        """Supply a synthetic sample for the design fixture."""
        self.input_sample = " ".join(raw.split())[:200]
        self.render()

    def _draw_key(self, key):
        canvas = self.main
        x0, y0, x1, y1 = key.bounds
        inset = RING_INSET
        ix0, iy0, ix1, iy1 = x0+inset, y0+inset, x1-inset, y1-inset
        bands = ((x0, y0, x1, iy0), (x0, iy1, x1, y1),
                 (x0, iy0, ix0, iy1), (ix1, iy0, x1, iy1))
        ring = [canvas.create_rectangle(*self.pixels(*rect), outline="",
                                         fill=self.theme["highlight"], state="hidden")
                for rect in bands]
        outer_width = min(max(2, 1.6*self.thickness*self.scale),
                          max(2, 1.2*inset*self.scale))
        inner_width = max(1, min(.65*outer_width, outer_width-1))
        outer = canvas.create_rectangle(*self.pixels(*key.bounds), fill="",
                                        outline=self.theme["border"],
                                        width=outer_width)
        inner = canvas.create_rectangle(*self.pixels(ix0, iy0, ix1, iy1), fill="",
                                        outline=dim_color(self.theme["border"], INNER_BRIGHTNESS),
                                        width=inner_width)
        language = self.live_language if self.live_language in ("KR", "EN") else self.language
        layout = LAYOUTS.get(language) or {}
        if key.special == "lang":
            if self.altgr_available:
                glyph = "AltGr"
            elif self.input_driver and not self.layout_is_ime:
                glyph = "—"
            elif self.live_language in ("KR", "EN"):
                glyph = self.live_language
            elif self.input_driver:
                glyph = "IME ?" if self.profile_code in (None, "KR") else self.profile_code
            else:
                glyph = LANG_TOGGLE_LABELS.get(language, "한/영")
        elif key.code == "CapsLock" and self.caps_on:
            glyph = "Caps ON"
        elif key.special == "space":
            if self.input_driver:
                language = (self.live_language if self.live_language in ("KR", "EN") else
                            None if self.layout_is_ime and self.profile_code in (None, "KR")
                            else self.profile_code)
            glyph = f"{language} · Space" if language else "Space"
        else:
            glyph = (self.layout_captions.get(key.code, key.normal)
                     if self.layout_captions is not None
                     else layout.get(key.code, (key.normal, key.shifted))[0])
        size = 15
        if self.layout_mode == "full":  # narrow Full keys: shrink long legends until they fit
            room = x1-x0-8
            while size > 10 and sum(size*(.58 if ord(ch) < 128 else 1.05) for ch in glyph) > room:
                size -= 1
        label = self._label(canvas, (x0+x1)/2, (y0+y1)/2, glyph, size, weight=600)
        self.key_items[key.code] = (outer, inner, label, *ring)
        self.glow_applied.discard(key.code)
        self._paint_pressed(key.code)

    def _indicator_color(self, code):
        """Persistent state-indicator glow: Caps Lock ON (distinct colour) or the Hangul mode of the
        foreground app (KR = theme glow, EN = dimmed glow). None = no indicator."""
        if code == "CapsLock" and self.caps_on:
            return caps_color(self.theme)
        if (code == "LangToggle" and not self.altgr_on and self.live_language in ("KR", "EN")
                and (self.layout_is_ime or not self.input_driver)):
            glow = self.theme["highlight"]
            return glow if self.live_language == "KR" else dim_color(glow, .5)
        return None

    def _paint_pressed(self, code):
        items = self.key_items.get(code)
        if items:
            indicator = self._indicator_color(code)
            active = indicator is not None or code in self.armed or (
                code == "LangToggle" and self.altgr_on)
            ordinary = code not in ("CapsLock", "LangToggle")
            shown = (code in self.pressed if self.glow_mode == "realtime" or not ordinary
                     else code == self.last_key)
            shown = shown or (self.glow_mode == "realtime" and code in self.release_jobs)
            state = "normal" if shown or active else "hidden"
            # Programmatic glow and state indicators are always visible and ignore the mirror
            # lock: they show a state (Caps Lock, Hangul mode), never which key was typed.
            fill = self.key_glow.get(code) or indicator
            physical = (code in self.physical_pressed or code in self.release_jobs
                        or self.glow_mode == "last" and code == self.last_key and self.last_physical)
            if self.input_locked:
                state, fill = "hidden", None
            elif shown and self.input_driver and (not fill or physical and code == "LangToggle"):
                glow = self.theme["highlight"]
                lightness = (.37 if code not in self.release_jobs else .17) if physical else .27
                fill = mix_color(glow, "#ffffff", lightness)
            if code == "CapsLock":  # inner line joins the band so the ON state is unmistakable
                self.main.itemconfigure(items[1], outline=indicator or dim_color(
                    self.theme["border"], INNER_BRIGHTNESS))
            elif code != "LangToggle":
                outline = (mix_color(self.theme["highlight"], "#ffffff", .58)
                           if physical and shown and not self.input_locked
                           else dim_color(self.theme["border"], INNER_BRIGHTNESS))
                self.main.itemconfigure(items[1], outline=outline)
            if fill:
                state = "normal"
                self.glow_applied.add(code)
            elif code in self.glow_applied:
                fill = self.theme["highlight"]
                self.glow_applied.discard(code)
            for item in items[3:]:
                if fill:
                    self.main.itemconfigure(item, state=state, fill=fill)
                else:
                    self.main.itemconfigure(item, state=state)

    def set_synthetic_key(self, code, down):
        """Test-only entry point. Receives a key ID, never a character stream."""
        self.paint_live_key(code, down and self.mirror)

    def paint_live_key(self, code, down, *, physical=False):
        if code not in self.key_items:
            return
        if down and self.mirror_locked:
            return  # password/unknown focus: no echo, no Last Key memory
        if down:
            if physical:
                self.physical_pressed.add(code)
            else:
                self.physical_pressed.discard(code)
            job = self.release_jobs.pop(code, None)
            if job is not None:
                self.root.after_cancel(job)
            if (code not in self.pressed and self.glow_mode == "last"
                    and code not in ("CapsLock", "LangToggle")):
                previous, self.last_key = self.last_key, code
                self.last_physical = physical
                if previous and previous != code:
                    self._paint_pressed(previous)
            self.pressed.add(code)
        else:
            self.pressed.discard(code)
            self.physical_pressed.discard(code)
        self._paint_pressed(code)

    def release_glow(self, code):
        if (self.mirror_locked or not self.mirror or self.glow_mode != "realtime"
                or code in self.pressed or code not in self.key_items
                or code in ("CapsLock", "LangToggle")):
            return
        job = self.release_jobs.pop(code, None)
        if job is not None:
            self.root.after_cancel(job)
        self.release_jobs[code] = self.root.after(PHYSICAL_GLOW_MS, self._expire_release_glow, code)
        self._paint_pressed(code)

    def _expire_release_glow(self, code):
        self.release_jobs.pop(code, None)
        self._paint_pressed(code)

    def clear_release_glow(self):
        for job in self.release_jobs.values():
            self.root.after_cancel(job)
        self.release_jobs.clear()

    def toggle_mirror(self):
        if self.input_driver:
            self.input_driver.set_mirror(not self.mirror)
        else:
            self.pressed.clear()
        self.mirror = not self.mirror
        if not self.mirror:
            self.last_key = None
            self.clear_release_glow()
        self.render()

    def select_language(self, language):
        if self.input_driver:
            self.input_driver.select_layout(language)
            return
        self.language = language
        self.render()

    def select_theme(self, theme):
        if self.input_driver and theme != "blue" and not self.support_settings.confirmed:
            return
        self.theme_name = theme
        self.render()

    def toggle_menu(self):
        self.menu_target = 0.0 if self.menu_target else 1.0
        self.render()
        if self.menu_job is None:
            self._animate_menu()

    def _animate_menu(self):
        delta = self.menu_target - self.menu_fraction
        if abs(delta) <= .125:
            self.menu_fraction = self.menu_target
            self.menu_job = None
        else:
            self.menu_fraction += .125 if delta > 0 else -.125
            self.menu_job = self.root.after(16, self._animate_menu)
        self._place_menu()

    def _place_menu(self):
        y = round(COLLAPSED_OFFSET*(1-self.menu_fraction)*self.scale)
        self.header_offset = y
        if self.minimized or self.docked or not self.root.winfo_ismapped():
            self.menu.withdraw()
            return
        w = round(self.width*self.scale)
        top = round(MENU_TOP*self.scale)
        full = round(MENU_HEIGHT*self.scale)
        visible = round(full*self.menu_fraction)
        self.header.place(x=0, y=0, width=w, height=top)
        if visible:
            self.menu_clip.place(x=0, y=top, width=w, height=visible)
            self.details.place(x=0, y=visible-full, width=w, height=full)
        else:
            self.menu_clip.place_forget()

        size = f"{w}x{top+visible}"
        if self.menu.geometry().split("+", 1)[0].split("-")[0] != size:
            self.menu.geometry(size)
        hwnd = win.get_ancestor(self.menu.winfo_id(), 2)
        if hwnd:
            style = win.get_style(hwnd, -20)
            if not style & 0x08000000:  # WS_EX_NOACTIVATE
                win.set_style(hwnd, -20, style | 0x08000000)
            win.set_pos(hwnd, -1, self.root.winfo_rootx(), self.root.winfo_rooty()+y,
                        w, top+visible,  # HWND_TOPMOST | SWP_NOACTIVATE (SWP_NOZORDER under a popup)
                        0x14 if self.popup_open else 0x10)
        if self.menu.state() == "withdrawn":
            self.menu.deiconify()

    def _track_menu(self, event):
        if event.widget is self.root:
            self._place_menu()

    def _start_drag(self, event):
        self.drag = (event.x_root-self.root.winfo_rootx(),
                     event.y_root-self.root.winfo_rooty())

    def _pointer_down(self, event, controls):
        self.tooltip.hide()
        x, y = event.x/self.scale, event.y/self.scale
        for (x0, y0, x1, y1), action in controls.items():
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue
            if action == "drag":
                self._start_drag(event)
            elif action == "resize":
                self.begin_resize(event.x_root)
            elif isinstance(action, tuple):
                _, field, left, right, low, high = action
                self.adjustment = (field, event.widget.winfo_rootx()+left*self.scale,
                                   (right-left)*self.scale, low, high)
                self._pointer_move(event)
            else:
                action()
            return
        if event.widget in (self.header, self.details):
            self._start_drag(event)

    def _pointer_move(self, event):
        if self.drag:
            dx, dy = self.drag
            hwnd = win.get_ancestor(self.root.winfo_id(), 2)
            win.set_pos(hwnd, None, event.x_root-dx, event.y_root-dy, 0, 0, 0x15)
        elif self.adjustment:
            field, *values = self.adjustment
            if field == "grip":
                self.move_resize(event.x_root)
                return
            left, span, low, high = values
            ratio = min(1, max(0, (event.x_root-left)/span))
            value = low+(high-low)*ratio
            if field == "scale":
                self.menu_values[field] = value
                self._draw_details()
            elif field == "opacity":
                self.opacity = value
                self.root.attributes("-alpha", value)
                self._draw_details()
            else:
                self.thickness = value
                self.render()

    def begin_resize(self, screen_x):
        self.adjustment = ("grip", screen_x, self.scale)

    def move_resize(self, screen_x):
        if not self.adjustment or self.adjustment[0] != "grip":
            return
        _, origin, baseline = self.adjustment
        scale = min(1.45, max(.72, baseline+(screen_x-origin)/self.width))
        if abs(self.scale-scale) >= .002:
            self.scale = scale
            self.render()

    def end_resize(self):
        if self.adjustment and self.adjustment[0] == "grip":
            self.adjustment = None

    def _pointer_up(self, _event):
        self.drag = None
        self.adjustment = None
        if "scale" in self.menu_values:
            self.scale = self.menu_values.pop("scale")
            self.render()

    def _set_icon(self):
        """HoloKeyboard icon for every Tk window (HUD, practice, dialogs); a missing file is not an error."""
        try:
            icon = Path(__file__).resolve().parent / "assets" / "holokeyboard.ico"
            if icon.is_file():
                self.root.iconbitmap(default=str(icon))
        except Exception:
            pass

    def _taskbar_button(self):
        """The borderless HUD gets a taskbar button (WS_EX_APPWINDOW) and a minimize box so the taskbar
        can minimize and restore it. Shape, transparency and opacity are untouched."""
        try:
            # Own taskbar identity: not grouped under "Python" when run from source, icon from the window.
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AICompanionLab.HoloKeyboard.V1")
        except Exception:
            pass
        try:
            self.root.update_idletasks()
            self.root.withdraw()
            hwnd = win.get_ancestor(self.root.winfo_id(), 2)
            if hwnd:
                win.set_style(hwnd, -20, (win.get_style(hwnd, -20) | 0x00040000) & ~0x00000080)
                win.set_style(hwnd, -16, win.get_style(hwnd, -16) | 0x00020000)
        except Exception:
            pass
        finally:
            self.root.deiconify()

    def minimize(self):
        """Minimize through the window manager (taskbar button stays); the HUD keeps its borderless style."""
        if self.minimized:
            return
        self.minimized = True
        self.menu.withdraw()
        # Run from the event loop (after the click that asked for it has finished). The minimize is posted,
        # not sent, so Tk's own message loop handles it like a taskbar request.
        self.root.after(250, self._post_minimize)

    def _post_minimize(self, attempt=0):
        """Post SC_MINIMIZE; Windows ignores it while the mouse button that clicked '-' is still held,
        so retry until the window is really minimized and give up (restoring the menu) after ~3 s."""
        try:
            hwnd = ctypes.c_void_p(win.get_ancestor(self.root.winfo_id(), 2))
            if ctypes.windll.user32.IsIconic(hwnd):
                return
            if attempt >= 10:
                raise RuntimeError("minimize did not take effect")
            ctypes.windll.user32.PostMessageW(hwnd, 0x0112, 0xF020, 0)    # WM_SYSCOMMAND, SC_MINIMIZE
            self.root.after(300, self._post_minimize, attempt+1)
        except Exception:
            self.minimized = False
            self._place_menu()

    def _restore(self, event):
        if event.widget is self.root and self.minimized:
            self.minimized = False
            self.root.attributes("-topmost", True)

    def close(self):
        self.clear_release_glow()
        if self.input_driver:
            self.input_driver.close()
            self.live_text = ""
        else:
            self.guard.close()
        if self.diagnostics:
            self.diagnostics.close()
        self.tooltip.close()
        if self.notice_job is not None:
            self.root.after_cancel(self.notice_job)
        if self.menu_job is not None:
            self.root.after_cancel(self.menu_job)
        self.root.destroy()


def main():
    if sys.platform != "win32":
        raise SystemExit("HoloKeyboard requires Windows.")
    # Per-monitor DPI makes the Canvas and Windows screen coordinates agree.
    try:
        set_dpi = ctypes.windll.user32.SetProcessDpiAwarenessContext
        set_dpi.argtypes = (ctypes.c_void_p,)
        set_dpi(ctypes.c_void_p(-4))
    except AttributeError:
        pass
    root = tk.Tk()
    from windows_input import LiveInput
    hud = HoloKeyboardHUD(root)
    if sys.argv[1:] == ["--release-smoke"]:
        # The package verifier opens only owned windows and imports no live input driver.
        import json
        import tempfile
        from typing_practice.stories import load_stories
        try:
            # Bundled content: exactly the 8 original stories/guides, two per language.
            bundled = load_stories(release_only=True, user_directory=None)
            assert len(bundled) == 8, len(bundled)
            assert sorted({s.lang for s in bundled}) == ["en", "ja", "ko", "zh"]
            assert all(sum(1 for s in bundled if s.lang == lang) == 2 for lang in ("ko", "en", "zh", "ja"))
            # A personal story file is loaded from a personal folder (an owned temporary one here);
            # a malformed file is skipped and a duplicate bundled id cannot replace a bundled story.
            with tempfile.TemporaryDirectory() as folder:
                with open(f"{folder}\\smoke.json", "w", encoding="utf-8") as handle:
                    json.dump({"id": "user-smoke-001", "lang": "en", "title": "Smoke",
                               "sentences": ["One small step.", "Another small step."]}, handle)
                with open(f"{folder}\\broken.json", "w", encoding="utf-8") as handle:
                    handle.write("{ not json")
                with open(f"{folder}\\dup.json", "w", encoding="utf-8") as handle:
                    json.dump({"id": bundled[0].id, "lang": bundled[0].lang, "sentences": ["Replaced."]}, handle)
                merged = load_stories(release_only=True, user_directory=folder)
                assert len(merged) == 9 and any(s.id == "user-smoke-001" for s in merged)
                assert next(s for s in merged if s.id == bundled[0].id).sentences != ("Replaced.",)
            hud.open_about()
            root.update_idletasks()
            assert hud.product_dialog.winfo_exists() and BRAND in root.title()
        finally:
            hud.close()
        return
    LiveInput(hud)
    for argument in sys.argv[1:]:
        if argument == "--diagnose" or argument.startswith("--diagnose="):
            import diagnose  # a short stage-by-stage report (counts and facts only, no typed text)
            seconds = int(argument.split("=", 1)[1]) if "=" in argument else 90
            hud.diagnose = diagnose.Diagnose(hud, seconds)
    root.mainloop()


if __name__ == "__main__":
    main()

