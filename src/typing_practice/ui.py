"""Practice window: glowing pacer, judged input, LED progress, effects.

Everything runs on ONE Tk `after` loop (<= 30 fps) that exists only while the
window is open. Typed text is read from the Entry transiently for judging and
the Entry is cleared on every sentence change and on close.
"""
import colorsys
import ctypes
import gc
import math
import random
import time
import tkinter as tk
import tkinter.font as tkfont

from . import engine, sfx as sfx_mod, stories as stories_mod, tts as tts_mod
from .moles import MOLE_SECONDS, MoleEffect

try:
    import win_native
except Exception:  # pragma: no cover - the practice window also works without raising the keyboard
    win_native = None

HUD_WIDTH = 729                # Compact keyboard geometry (holo_keyboard_hud.WIDTH / KEY_TOP)
HUD_KEY_TOP = 113
HUD_KEYS_BOTTOM = 330
MOLE_H = 112

EFFECTS_ENABLED = True        # master switch for mole game + rainbow sweep
MAX_FPS = 30                  # animation cap
TICK_MS = 33                  # ~30 fps; also the ~30 ms IME poll
RAINBOW_SECONDS = 3.0         # one slow hue sweep (>= 3 s cycle, no flashing)
ADVANCE_MS = 450              # pause after a finished sentence
LISTEN_REVEAL_MS = 1400       # reveal time in listen-and-write mode
FLASH_MS = 250                # green/red key feedback, cleared automatically
PACE_LEAD = 0.6               # seconds before the pacer starts moving
LED_COUNT = 32
FONT_FAMILY = "Malgun Gothic"

BG, PANEL = "#0a1118", "#101923"
TEXT, DIM, FAINT = "#d7ecf7", "#6f8799", "#2c3b48"
OK_COLOR, BAD_COLOR = "#47d98a", "#ff6b6b"

STR = {
    "title": ("Story Typing", "동화 타자 연습"),  # same names as the HUD: hud_i18n.PRACTICE_STORY
    "KO": ("Korean", "한국어"), "EN": ("English", "영어"), "ZH": ("Chinese", "중국어"), "JA": ("Japanese", "일본어"),
    "speed": ("Pace", "속도"), "auto": ("AUTO", "자동"),
    "mode": ("Mode", "모드"), "copy": ("Copy", "따라 쓰기"), "listen": ("Listen & write", "듣고 따라 쓰기"),
    "voice": ("Voice", "음성"), "sound": ("Sound", "효과음"), "vspeed": ("Voice speed", "음성 속도"),
    "replay": ("Replay", "다시 듣기"), "restart": ("Restart", "처음부터"), "close": ("Close", "닫기"),
    "skip": ("Skip", "건너뛰기"), "on": ("ON", "켬"), "off": ("OFF", "끔"),
    "no_stories": ("No stories found.", "이야기를 찾을 수 없습니다."),
    "no_voice": ("Voice for this language is not installed in Windows. Typing practice still works.",
                 "이 언어의 음성이 Windows에 설치되어 있지 않습니다. 타자 연습은 그대로 할 수 있습니다."),
    "speed_stat": ("Speed", "속도"), "cpm": ("CPM", "자/분"), "accuracy": ("Accuracy", "정확도"),
    "progress": ("Progress", "진행"), "score": ("Whacks", "두더지"),
    "done": ("Story complete! Well done.", "이야기를 모두 마쳤어요! 잘했어요."),
    "help": ("Green is correct and red marks an error. Use Backspace to fix errors. "
             "A completed sentence advances automatically. Esc skips effects.",
             "초록은 맞는 글자, 빨강은 오타입니다. 백스페이스로 오타를 고치세요. "
             "문장을 완성하면 자동으로 넘어갑니다. Esc는 효과를 건너뜁니다."),
}


def blend(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a, b = bytes.fromhex(c1[1:]), bytes.fromhex(c2[1:])
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def hsv_hex(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


# ------------------------------------------------------------------ IME probe

def make_ime_probe(widget):
    """Return probe() -> the number of UTF-16 units in the active IME composition."""
    try:
        imm = ctypes.WinDLL("imm32")
        user = ctypes.WinDLL("user32")
        imm.ImmGetContext.restype = ctypes.c_void_p
        imm.ImmGetContext.argtypes = (ctypes.c_void_p,)
        imm.ImmReleaseContext.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        imm.ImmGetCompositionStringW.restype = ctypes.c_long
        imm.ImmGetCompositionStringW.argtypes = (ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong)
        user.GetAncestor.restype = ctypes.c_void_p
        user.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
    except Exception:
        return lambda: False

    def probe():
        try:
            entry = widget.winfo_id()
            for hwnd in (entry, user.GetAncestor(entry, 2)):
                if not hwnd:
                    continue
                himc = imm.ImmGetContext(hwnd)
                if himc:
                    try:
                        # GCS_COMPSTR = 8; only the LENGTH is read, never the text.
                        size = imm.ImmGetCompositionStringW(himc, 8, None, 0)
                        if size > 0:
                            return size//2
                    finally:
                        imm.ImmReleaseContext(hwnd, himc)
        except Exception:
            pass
        return False
    return probe


def toplevel_hwnd(widget):
    try:
        user = ctypes.WinDLL("user32")
        user.GetAncestor.restype = ctypes.c_void_p
        user.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        return int(user.GetAncestor(widget.winfo_id(), 2) or 0)
    except Exception:
        return 0


# ------------------------------------------------------------------- HUD glow

class KeyGlow:
    """Layered per-key glow requests (flash > fx > hint) pushed to the HUD."""

    def __init__(self, hud, highlight):
        self.hud = hud
        self.highlight = highlight
        self.hint = {}      # code -> color (steady, no blink)
        self.flash = {}     # code -> (color, expiry)
        self.fx = {}        # code -> color (rainbow)
        self.applied = {}
        self._busy = False

    def _want(self, code):
        if code in self.flash:
            return self.flash[code][0]
        return self.fx.get(code) or self.hint.get(code)

    def set_hint(self, codes):
        self.hint = {c: blend("#000000", self.highlight, 0.75) for c in codes}
        self.apply()

    def flash_key(self, code, color, now, ms=FLASH_MS):
        if code:
            self.flash[code] = (color, now + ms / 1000.0)
            self.apply()

    def set_fx(self, mapping):
        self.fx = dict(mapping)
        self.apply()

    def expire(self, now):
        gone = [c for c, (_, t) in self.flash.items() if t <= now]
        for c in gone:
            del self.flash[c]
        if gone:
            self.apply()

    def apply(self, force=False):
        setter = getattr(self.hud, "set_key_glow", None)
        if setter is None or self._busy:
            return
        self._busy = True
        try:
            for code in set(self.applied) | set(self.hint) | set(self.flash) | set(self.fx):
                want = self._want(code)
                if force and want is None and code not in self.applied:
                    continue
                if force or self.applied.get(code) != want:
                    try:
                        setter(code, want)
                    except Exception:
                        pass
                    if want is None:
                        self.applied.pop(code, None)
                    else:
                        self.applied[code] = want
        finally:
            self._busy = False

    def on_render(self):
        """HUD render hook: the HUD keeps overrides, but re-assert ours cheaply."""
        if self.applied:
            self.apply(force=True)

    def clear_all(self):
        self.hint, self.flash, self.fx = {}, {}, {}
        setter = getattr(self.hud, "set_key_glow", None)
        if setter is not None:
            for code in list(self.applied):
                try:
                    setter(code, None)
                except Exception:
                    pass
        self.applied = {}


# -------------------------------------------------------------------- effects

class PracticeWindow:
    def __init__(self, hud, *, stories=None, tts=None, sfx=None, ime_probe=None, clock=None,
                 effects=None, on_closed=None, rng=None):
        self.hud = hud
        self.root = hud.root
        self.clock = clock or time.monotonic
        self.on_closed = on_closed
        self.effects_enabled = EFFECTS_ENABLED if effects is None else effects
        self.rng = rng or random.Random()
        self._closed = False
        self._job = None
        self._advance_job = None
        self._evaluation_job = None
        try:
            self._home = (self.root.winfo_rootx(), self.root.winfo_rooty() + round(HUD_KEY_TOP * float(hud.scale)))
        except Exception:
            self._home = (100, 300)
        self._saved_language = getattr(hud, "language", None)
        self._saved_pos = None
        self.docked = False
        dock = getattr(hud, "set_docked", None)
        if callable(dock):
            try:
                self._saved_pos = (self.root.winfo_rootx(), self.root.winfo_rooty())
                dock(True)
                self.docked = True
            except Exception:
                self.docked = False
        self.scale = max(0.6, float(getattr(hud, "scale", 1.0) or 1.0))
        self.ui_lang = getattr(hud, "ui_language", "EN")
        self.stories_all = stories if stories is not None else stories_mod.load_stories()
        self.tts = tts if tts is not None else tts_mod.TTS()
        self.sfx = sfx if sfx is not None else sfx_mod.Sfx()
        self.sfx.enabled = True
        self._ime_override = ime_probe
        self.mapper = None
        self.stats = engine.Stats(self.clock)
        self.auto = engine.AutoSpeed()
        self.speed_mode = "auto"
        self.mode = "copy"
        self.voice_on = True
        self.voice_rate = 0
        self.story = None
        self.lang = None
        self.sent_index = 0
        self.judge = None
        self.state = "idle"       # idle | typing | advancing | finished
        self.target = ""
        self.sentence_started = 0.0
        self._pace_pos = -1.0
        self._chars = []          # per original char: dict(item,x,y,w,line)
        self._painted = []
        self._composing_prev = False
        self._voice_check = True
        self._notice_shown = False
        self.whacks = 0
        self.led_level = [0.0] * LED_COUNT
        self.led_shown = [None] * LED_COUNT
        self._led_target = 0.0
        self._led_pos = 0.0
        self.rainbow_start = None
        self.last_result = None
        self._hint_for = None
        self._revealed = False
        self._rainbow_last_keys = 0.0

        theme = getattr(hud, "theme", None) or {}
        self.highlight = theme.get("highlight", "#00d8ff")
        self.border = theme.get("border", "#00a8e8")
        self.glow = KeyGlow(hud, self.highlight)

        self._build()
        self._remember_metrics()
        self.mapper = self._make_mapper()
        self._register_with_hud()
        self.probe = self._ime_override or make_ime_probe(self.entry)
        self._populate_languages()
        self._schedule()
        self.focus()

    # ------------------------------------------------------------------ text
    def T(self, key):
        pair = STR[key]
        return pair[1] if self.ui_lang == "KO" else pair[0]

    def S(self, v):
        return max(1, round(v * self.scale))

    def font(self, size, weight="normal"):
        return (FONT_FAMILY, -self.S(size), weight)

    # ----------------------------------------------------------------- build
    def _make_mapper(self):
        try:
            return engine.KeyMapper()
        except Exception:
            return None

    def _build(self):
        S = self.S
        self.win = tk.Toplevel(self.root, bg=BG)
        self.win.title(self.T("title"))
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Destroy>", self._on_destroy, add="+")
        self.win.bind("<Escape>", lambda _e: self.skip_effects())
        for sequence in ("<Configure>", "<FocusIn>", "<Map>"):
            self.win.bind(sequence, self.sync_hud, add="+")
        pad = S(14)
        hud_w = round(getattr(self.hud, "width", HUD_WIDTH) * self.scale)
        self.width = hud_w + 2 * pad          # same width as the embedded keyboard
        self.win.resizable(False, False)
        if self.docked:
            self.win.attributes("-topmost", True)
            self.win.bind("<Unmap>", self._hide_dock, add="+")
        outer = tk.Frame(self.win, bg=BG)
        outer.pack(fill="both", expand=True, padx=pad, pady=S(10))
        self.outer = outer

        head = tk.Frame(outer, bg=BG)
        head.pack(fill="x")
        left = tk.Frame(head, bg=BG)
        left.pack(side="left", fill="x", expand=True)

        # row 1: story picker + close
        top = tk.Frame(left, bg=BG)
        top.pack(fill="x")
        self.lang_frame = tk.Frame(top, bg=BG)
        self.lang_frame.pack(side="left")
        self.lang_buttons = {}
        self.story_var = tk.StringVar(master=self.win)
        self.story_menu = tk.OptionMenu(top, self.story_var, "")
        self._style_menu(self.story_menu)
        self.story_menu.configure(width=1, anchor="w")
        self.story_menu.pack(side="left", fill="x", expand=True, padx=(S(10), S(6)))
        self.story_menu.bind("<Configure>", self._fit_story_label, add="+")
        self.close_btn = self._btn(top, "close", self.close)
        self.close_btn.pack(side="right")

        # row 2: pace
        ctl = tk.Frame(left, bg=BG)
        ctl.pack(fill="x", pady=(S(6), 0))
        self.speed_label = self._label(ctl, "speed")
        self.speed_label.pack(side="left")
        self.speed_btns = {}
        for key in ("auto", 1, 2, 3, 4, 5):
            b = self._btn(ctl, None, lambda k=key: self.set_speed(k), text=str(key) if key != "auto" else None)
            b.pack(side="left", padx=(S(3), 0))
            self.speed_btns[key] = b

        # row 3: mode + voice/sound switches
        ctl3 = tk.Frame(left, bg=BG)
        ctl3.pack(fill="x", pady=(S(6), 0))
        self.mode_label = self._label(ctl3, "mode")
        self.mode_label.pack(side="left")
        self.mode_btns = {}
        for key in ("copy", "listen"):
            b = self._btn(ctl3, key, lambda k=key: self.set_mode(k))
            b.pack(side="left", padx=(S(3), 0))
            self.mode_btns[key] = b
        self.voice_btn = self._btn(ctl3, None, self.toggle_voice)
        self.voice_btn.pack(side="left", padx=(S(10), 0))
        self.sound_btn = self._btn(ctl3, None, self.toggle_sound)
        self.sound_btn.pack(side="left", padx=(S(4), 0))

        # row 4: voice speed, replay, restart
        ctl2 = tk.Frame(left, bg=BG)
        ctl2.pack(fill="x", pady=(S(6), 0))
        self.vspeed_label = self._label(ctl2, "vspeed")
        self.vspeed_label.pack(side="left")
        self.vminus = self._btn(ctl2, None, lambda: self.change_voice_rate(-1), text="−")
        self.vminus.pack(side="left", padx=(S(3), 0))
        self.vrate_label = tk.Label(ctl2, text="0", bg=BG, fg=TEXT, font=self.font(12), width=3)
        self.vrate_label.pack(side="left")
        self.vplus = self._btn(ctl2, None, lambda: self.change_voice_rate(1), text="+")
        self.vplus.pack(side="left")
        self.replay_btn = self._btn(ctl2, "replay", self.replay)
        self.replay_btn.pack(side="left", padx=(S(14), 0))
        self.restart_btn = self._btn(ctl2, "restart", self.restart)
        self.restart_btn.pack(side="left", padx=(S(6), 0))

        self.fx = tk.Canvas(outer, width=hud_w, height=S(MOLE_H), bg="#14271f",
                            highlightthickness=0)
        self.fx.pack(fill="x", pady=(S(8), 0))

        # sentence canvas
        self.sent_font = tkfont.Font(family=FONT_FAMILY, size=-S(30))
        self.line_h = round(self.sent_font.metrics("linespace") * 1.45)
        self.sent_w = self.width - 2 * pad
        self.sentence = tk.Canvas(outer, width=self.sent_w, height=self.line_h * 2 + S(16), bg=PANEL,
                                  highlightthickness=1, highlightbackground=blend(PANEL, self.border, .45))
        self.sentence.pack(fill="x", pady=(S(10), 0))
        # input
        self.var = tk.StringVar(master=self.win)
        self.entry = tk.Entry(outer, textvariable=self.var, font=self.font(22), bg="#0e1a24", fg=TEXT,
                              readonlybackground="#13231f",
                              insertbackground=self.highlight, relief="flat", highlightthickness=1,
                              highlightbackground=blend(PANEL, self.border, .5), highlightcolor=self.highlight)
        self.entry.pack(fill="x", pady=(S(10), 0), ipady=S(5))
        self.var.trace_add("write", self._entry_changed)
        self.entry.bind("<Return>", lambda _e: self.win.after(40, self._evaluate))
        self.entry.bind("<space>", lambda _e: self.win.after(40, self._evaluate), add="+")

        # LED strip
        self.led_h = S(16)
        self.leds = tk.Canvas(outer, width=self.sent_w, height=self.led_h, bg=BG, highlightthickness=0)
        self.leds.pack(fill="x", pady=(S(8), 0), after=self.sentence)   # progress LEDs sit under the sentence
        self.led_items = []
        step = self.sent_w / LED_COUNT
        r = S(4)
        for i in range(LED_COUNT):
            cx = step * (i + 0.5)
            self.led_items.append(self.leds.create_oval(cx - r, self.led_h / 2 - r, cx + r, self.led_h / 2 + r,
                                                        fill=FAINT, outline=""))
        # stats
        self.stats_label = tk.Label(outer, text="", bg=BG, fg=TEXT, font=self.font(13), anchor="w")
        self.stats_label.pack(fill="x", pady=(S(6), 0))
        self.notice_label = tk.Label(outer, text="", bg=BG, fg="#ffcf70", font=self.font(11), anchor="w",
                                     justify="left", wraplength=self.sent_w)
        self.notice_label.pack(fill="x")
        self.help_label = tk.Label(outer, text="", bg=BG, fg=DIM, font=self.font(10), anchor="w", justify="left",
                                   wraplength=self.sent_w)
        self.help_label.pack(fill="x", pady=(S(2), 0))
        # The Compact keyboard (the HUD itself, docked) is laid over this empty band.
        kb_h = round(HUD_KEYS_BOTTOM * self.scale) - round(HUD_KEY_TOP * self.scale) + S(6)
        self.kb_zone = tk.Frame(outer, bg=BG, height=kb_h, width=self.sent_w)
        self.kb_zone.pack(fill="x", pady=(S(4), 0))
        self.kb_zone.pack_propagate(False)
        self.resize_grip = tk.Label(outer, text="↘", bg=BG, fg=self.highlight,
                                    font=self.font(16), cursor="size_nw_se")
        self.resize_grip.place(relx=1, rely=1, anchor="se")
        self.resize_grip.bind("<ButtonPress-1>", self._begin_resize)
        self.resize_grip.bind("<B1-Motion>", self._drag_resize)
        self.moles = MoleEffect(self.fx, self.scale, self.sfx, self._on_score,
                                lambda: self.T("skip"), self.rng)

        self.win.update_idletasks()
        self._place_window()
        self._relabel()

    def _remember_metrics(self):
        """Record the Pack layout in units of the opening scale."""
        self._initial_scale = self.scale
        self._metrics = []
        pending = [self.outer]
        while pending:
            widget = pending.pop()
            if isinstance(widget, tk.Menu):
                continue
            pending.extend(widget.winfo_children())
            info = widget.pack_info() if widget.winfo_manager() == "pack" else {}
            padding = {}
            for name in ("padx", "pady", "ipadx", "ipady"):
                if name in info:
                    parts = info[name] if isinstance(info[name], tuple) else widget.tk.splitlist(str(info[name]))
                    if parts:
                        padding[name] = tuple(widget.winfo_pixels(part) for part in parts)
            font = None
            if "font" in widget.keys():
                parts = widget.tk.splitlist(widget.cget("font"))
                if len(parts) >= 2 and str(parts[1]).lstrip("-").isdigit():
                    font = parts
            self._metrics.append((widget, padding, font))

    def _begin_resize(self, event):
        self._size_start = (event.x_root, self.scale)

    def _drag_resize(self, event):
        x, start = self._size_start
        self.resize(start + (event.x_root-x)/(HUD_WIDTH+28))

    def resize(self, scale):
        """Resize the panel and the native Compact hit surface without replacing the Entry."""
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        maximum = min(1.45, (sw-40)/(HUD_WIDTH+28),
                      self.scale*(sh-84)/max(1, self.win.winfo_height()))
        scale = round(max(.60, min(maximum, scale)), 2)
        if scale == self.scale:
            return
        old_scale, self.scale = self.scale, scale
        ratio = scale/self._initial_scale
        S = self.S
        for widget, padding, font in self._metrics:
            if padding:
                widget.pack_configure(**{key: tuple(round(x*ratio) for x in values)
                                         for key, values in padding.items()})
            if font:
                widget.configure(font=(font[0], -max(1, round(abs(int(font[1]))*ratio)), *font[2:]))
        for button in self.lang_buttons.values():
            button.configure(font=self.font(12))
            button.pack_configure(padx=(0, S(4)))
        self.resize_grip.configure(font=self.font(16))
        self.story_menu["menu"].configure(font=self.font(12))
        self.sent_w = round(HUD_WIDTH*scale)
        self.width = self.sent_w + 2*S(14)
        self.sent_font.configure(size=-S(30))
        self.line_h = round(self.sent_font.metrics("linespace")*1.45)
        self.sentence.configure(width=self.sent_w, height=self.line_h*2+S(16))
        self.notice_label.configure(wraplength=self.sent_w)
        self.help_label.configure(wraplength=self.sent_w)
        self.fx.configure(width=self.sent_w, height=S(MOLE_H))
        self.moles.resize(scale)
        self.led_h = S(16)
        self.leds.configure(width=self.sent_w, height=self.led_h)
        for i, item in enumerate(self.led_items):
            cx, cy, r = self.sent_w*(i+.5)/LED_COUNT, self.led_h/2, S(4)
            self.leds.coords(item, cx-r, cy-r, cx+r, cy+r)
        self.kb_zone.configure(width=self.sent_w, height=round(HUD_KEYS_BOTTOM*scale)
                               - round(HUD_KEY_TOP*scale)+S(6))
        if self.target:
            self._draw_sentence(getattr(self, "_flow_offset", 0)*scale/old_scale)
            if self.last_result:
                self._paint(self.last_result.states)
        elif self.story is None:
            self._show_message(self.T("no_stories"))
        if self.docked:
            self.hud.set_docked(True, scale=scale)
        self.win.update_idletasks()
        self.win.geometry(f"{self.width}x{self.win.winfo_reqheight()}")
        self.win.after_idle(self.sync_hud)

    def _hide_dock(self, event):
        if event.widget is self.win and self.docked and not self._closed:
            self.root.withdraw()

    def _style_menu(self, menu):
        menu.configure(bg=PANEL, fg=TEXT, activebackground=blend(PANEL, self.border, .3), activeforeground=TEXT,
                       relief="flat", highlightthickness=1, highlightbackground=blend(PANEL, self.border, .5),
                       font=self.font(12), bd=0, takefocus=0, anchor="w")
        menu["menu"].configure(bg=PANEL, fg=TEXT, activebackground=blend(PANEL, self.border, .4),
                               font=self.font(12))

    def _btn(self, parent, key, command, text=None):
        b = tk.Button(parent, text=text if text is not None else (self.T(key) if key else ""), bg=PANEL, fg=TEXT,
                      activebackground=blend(PANEL, self.border, .35), activeforeground=TEXT, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=blend(PANEL, self.border, .4), takefocus=0,
                      font=self.font(12), padx=self.S(8), pady=self.S(2),
                      command=lambda: (command(), self._refocus()))
        b._key = key
        return b

    def _label(self, parent, key):
        return tk.Label(parent, text=self.T(key), bg=BG, fg=DIM, font=self.font(12))

    def _refocus(self):
        try:
            if not self._closed:
                self.entry.focus_set()
        except tk.TclError:
            pass

    def _select_style(self, button, selected):
        button.configure(highlightbackground=self.highlight if selected else blend(PANEL, self.border, .4),
                         fg=self.highlight if selected else TEXT)

    def _place_window(self):
        """Put the window where the HUD was (clamped on screen), then dock the keyboard into it."""
        try:
            self.win.update_idletasks()
            w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
            sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
            x, y = self._home[0], self._home[1] - (h - round(HUD_KEYS_BOTTOM * self.scale))
            x = max(0, min(x, sw - w))
            y = max(0, min(y, sh - h - 40))
            self.win.geometry(f"{w}x{h}+{x}+{y}")
            self.win.update_idletasks()
        except tk.TclError:
            pass
        self.sync_hud()

    def sync_hud(self, _event=None):
        """Keep the docked keyboard exactly over the keyboard band, above the practice window."""
        if self._closed or not self.docked:
            return
        try:
            if not self.win.winfo_viewable():
                return
            if self.root.state() == "withdrawn":
                self.root.deiconify()
            zone = self.kb_zone
            hud_w = round(self.hud.width * self.hud.scale)
            x = zone.winfo_rootx() + (zone.winfo_width() - hud_w) // 2
            y = zone.winfo_rooty() - round(HUD_KEY_TOP * self.hud.scale) + self.S(3)
            if _event is None and (x, y) == getattr(self, "_last_sync", None):
                return                      # periodic check: nothing moved
            self._last_sync = (x, y)
            hwnd = win_native.get_ancestor(self.root.winfo_id(), 2)
            if hwnd:
                # HWND_TOPMOST | SWP_NOSIZE | SWP_NOACTIVATE: move and stay above, never take focus
                win_native.set_pos(hwnd, -1, x, y, 0, 0, 0x11)
        except Exception:
            pass

    def _register_with_hud(self):
        self.hwnd = toplevel_hwnd(self.win)
        reg = getattr(self.hud, "register_safe_window", None)
        if reg and self.hwnd:
            try:
                reg(self.hwnd)
            except Exception:
                pass
        hooks = getattr(self.hud, "render_hooks", None)
        if isinstance(hooks, list):
            hooks.append(self.glow.on_render)

    # -------------------------------------------------------------- labelling
    def _relabel(self):
        self.win.title(self.T("title"))
        for lang, b in self.lang_buttons.items():
            b.configure(text=self.T(lang.upper()))
        for key, b in self.mode_btns.items():
            b.configure(text=self.T(key))
        self.speed_btns["auto"].configure(text=self.T("auto"))
        self.speed_label.configure(text=self.T("speed"))
        self.mode_label.configure(text=self.T("mode"))
        self.vspeed_label.configure(text=self.T("vspeed"))
        self.replay_btn.configure(text=self.T("replay"))
        self.restart_btn.configure(text=self.T("restart"))
        self.close_btn.configure(text=self.T("close"))
        self.voice_btn.configure(text=f"{self.T('voice')}: {self.T('on' if self.voice_on else 'off')}")
        self.sound_btn.configure(text=f"{self.T('sound')}: {self.T('on' if self.sfx.enabled else 'off')}")
        self._select_style(self.voice_btn, self.voice_on)
        self._select_style(self.sound_btn, self.sfx.enabled)
        for key, b in self.speed_btns.items():
            self._select_style(b, key == self.speed_mode)
        for key, b in self.mode_btns.items():
            self._select_style(b, key == self.mode)
        for lang, b in self.lang_buttons.items():
            self._select_style(b, lang == self.lang)
        self.vrate_label.configure(text=f"{self.voice_rate:+d}" if self.voice_rate else "0")
        self.help_label.configure(text=self.T("help"))
        self._rebuild_story_menu()
        self._update_notice()
        self._update_stats()

    # ------------------------------------------------------------ picker
    def _populate_languages(self):
        for child in self.lang_frame.winfo_children():
            child.destroy()
        self.lang_buttons = {}
        langs = stories_mod.languages(self.stories_all)
        for lang in langs:
            b = self._btn(self.lang_frame, None, lambda l=lang: self.select_language(l), text=self.T(lang.upper()))
            b.pack(side="left", padx=(0, self.S(4)))
            self.lang_buttons[lang] = b
        if langs:
            self.select_language(langs[0])
        else:
            self.story = None
            self._show_message(self.T("no_stories"))
            self._relabel()

    def _stories_of(self, lang):
        return [s for s in self.stories_all if s.lang == lang]

    def select_language(self, lang):
        self.lang = lang
        items = self._stories_of(lang)
        self._relabel()
        if items:
            self.select_story(items[0])

    def _rebuild_story_menu(self):
        menu = self.story_menu["menu"]
        menu.delete(0, "end")
        items = self._stories_of(self.lang) if self.lang else []
        for s in items:
            menu.add_command(label=s.display_title(self.ui_lang), command=lambda st=s: self.select_story(st))
        self._fit_story_label()

    def _fit_story_label(self, _event=None):
        title = self.story.display_title(self.ui_lang) if self.story else ""
        width = self.story_menu.winfo_width() - self.S(35)
        if width > 0:
            font = tkfont.Font(root=self.win, font=self.story_menu.cget("font"))
            if font.measure(title) > width:
                end = len(title)
                while end and font.measure(title[:end].rstrip()+"…") > width:
                    end -= 1
                title = title[:end].rstrip()+"…"
        if title != self.story_var.get():
            self.story_var.set(title)

    def select_story(self, story):
        self.story = story
        self._fit_story_label()
        self._voice_check = True
        # Legends follow the story: Korean tale -> Korean letters on the keys (a live Hangul/English
        # state reported by Windows still takes precedence inside the HUD).
        pick = getattr(self.hud, "select_language", None) if not getattr(self.hud, "input_driver", None) else None
        wanted = {"ko": "KR", "en": "EN"}.get(story.lang)
        if wanted and callable(pick) and getattr(self.hud, "language", None) != wanted:
            try:
                pick(wanted)
            except Exception:
                pass
        self.start_story()
        self._refocus()

    # ---------------------------------------------------------- story flow
    def start_story(self):
        self._cancel_advance()
        self.moles.stop()
        self._stop_rainbow()
        self.stats.reset()
        self.stats.sentences_total = len(self.story.sentences) if self.story else 0
        self.sent_index = 0
        self._led_target = 0.0
        self.var.set("") if self.var.get() else None
        self._activate_sentence()
        self._relabel()

    def restart(self):
        if self.story:
            self.start_story()

    def _activate_sentence(self):
        if not self.story:
            return
        self.target = self.story.sentences[self.sent_index]
        self.state = "typing"
        self.entry.configure(state="normal")
        if self.var.get():
            self.var.set("")
        self.judge = engine.Judge(self.target, self.story.lang)
        self.stats.new_sentence()
        self.sentence_started = self.clock()
        self._pace_pos = -1.0
        self.last_result = None
        self.moles.set_errors(0)
        self._draw_sentence()
        self._set_hint(0)
        self._update_stats()
        self._speak_current()

    def _speak_current(self):
        if self.voice_on and self.story and self.tts.speak(self.target, self.story.lang, self.voice_rate):
            return True
        return False

    def replay(self):
        if self.story and self.state in ("typing", "advancing"):
            self.tts.cancel()
            self._speak_current()

    def _show_message(self, text):
        self.sentence.delete("all")
        self._chars, self._painted = [], []
        self.sentence.create_text(self.sent_w / 2, self.sentence.winfo_reqheight() / 2, text=text, fill=DIM,
                                  font=self.font(18), width=self.sent_w - 40)

    # ------------------------------------------------------- sentence drawing
    def _draw_sentence(self, offset=None):
        c = self.sentence
        c.delete("all")
        hidden = self.mode == "listen" and self.state != "finished" and not self._revealed
        font = self.sent_font
        c.configure(height=self.line_h+self.S(18))
        self._chars = []
        x, y = 0, self.S(8)
        self._flow_offset = self.sent_w*.35 if offset is None else offset
        self._flow_time = self.clock()
        for ch in self.target:
            width = max(1, font.measure(ch))
            shown = "•" if hidden and ch != " " else ch
            center = x+width/2+self._flow_offset
            halo = c.create_text(center, y+self.S(2), text=shown, font=font,
                                 fill="#22454d", anchor="n", tags=("flow",))
            item = c.create_text(center, y, text=shown, font=font, fill=FAINT if hidden else "#a6e5ec",
                                 anchor="n", tags=("flow",))
            self._chars.append(dict(item=item, halo=halo, x=x, w=width))
            x += width
        self._flow_width = max(1.0, x/max(1, len(self.target)))
        self._painted = [None] * len(self._chars)
        self._pace_pos = 0.0

    def _paint(self, states, composing_char=None):
        hidden = self.mode == "listen" and self.state == "typing" and not self._revealed
        for i, st in enumerate(states):
            if i >= len(self._chars) or self._painted[i] == st:
                continue
            self._painted[i] = st
            color = {engine.OK: OK_COLOR, engine.BAD: BAD_COLOR}.get(st, FAINT if hidden else "#a6e5ec")
            char = self._chars[i]
            self.sentence.itemconfigure(char["item"], fill=color)
            self.sentence.itemconfigure(char["halo"], fill=blend(PANEL, color, .42))

    def _reveal(self):
        self._revealed = True
        for i, ch in enumerate(self.target):
            if i < len(self._chars):
                self.sentence.itemconfigure(self._chars[i]["item"], text=ch)
                self.sentence.itemconfigure(self._chars[i]["halo"], text=ch)

    # ------------------------------------------------------------ judging
    def _composing_now(self):
        try:
            return max(0, int(self.probe()))
        except Exception:
            return False

    def _entry_changed(self, *_):
        """Let the native IME finish processing the edit message before grading."""
        if self._ime_override is not None:
            self._evaluate()
        elif not self._closed and self._evaluation_job is None:
            self._evaluation_job = self.win.after_idle(self._evaluate_entry)

    def _evaluate_entry(self):
        self._evaluation_job = None
        self._evaluate()

    def _evaluate(self):
        if self._closed or self.state != "typing" or self.judge is None:
            return
        now = self.clock()
        typed = self.var.get()
        composing = self._composing_now()
        self._composing_prev = composing
        res = self.judge.update(typed, composing=composing)
        if res.advanced or res.new_error or typed:
            self.stats.touch()
        self.stats.set_current(res.matched if not res.wrong else res.matched)
        self.last_result = res
        self._paint(res.states)
        if self.moles.errors != min(5, res.unresolved):
            self.moles.set_errors(res.unresolved)
        if res.added_errors and not composing:
            self.stats.note_error(res.added_errors)
            self.sfx.play("typo")
            code = self.mapper.last_code(res.typed_last, self.story.lang) if self.mapper and res.typed_last else None
            self.glow.flash_key(code, BAD_COLOR, now)
        elif res.advanced and res.target_last and self.mapper:
            self.glow.flash_key(self.mapper.last_code(res.target_last, self.story.lang), OK_COLOR, now)
        self._set_hint(res.cursor)
        self._update_stats()
        if res.complete:
            self._complete_sentence()

    def _set_hint(self, cursor):
        if (not self.mapper or not self.story or self.story.lang not in ("ko", "en")
                or not self._keyboard_matches_story()):
            self.glow.set_hint([])
            self._hint_for = None
            return
        if cursor >= len(self.target):
            self.glow.set_hint([])
            return
        codes = self.mapper.hint_codes(self.target[cursor], self.story.lang)
        key = tuple(codes)
        if key != self._hint_for:
            self._hint_for = key
            self.glow.set_hint(codes)

    def _complete_sentence(self):
        elapsed = max(0.5, self.clock() - self.sentence_started)
        length = len(engine.normalize(self.target, self.story.lang))
        self.stats.sentence_done(length)
        self.auto.observe(length / (elapsed / 60.0))
        last = self.sent_index >= len(self.story.sentences) - 1
        self.state = "advancing"
        self.tts.cancel()
        self.entry.configure(state="readonly")
        self.glow.set_hint([])
        self._hint_for = None
        self._reveal_if_listen()
        self._led_target = self.stats.progress() / 100.0
        if last:
            self.sfx.play("arpeggio")
            if self.effects_enabled:
                self.moles.start(self.clock(), celebrate=True)
                self._start_rainbow()
        else:
            self.sfx.play("chime")
            if self.effects_enabled:
                self.moles.start(self.clock(), celebrate=(self.sent_index+1) % 5 == 0)
        self._update_stats()
        delay = LISTEN_REVEAL_MS if self.mode == "listen" else ADVANCE_MS
        if last and self.effects_enabled:
            delay = max(delay, int(RAINBOW_SECONDS * 1000) + 250)
        self._advance_job = self.win.after(delay, self._advance)

    def _reveal_if_listen(self):
        if self.mode == "listen":
            self._reveal()
            self._paint([engine.OK] * len(self.target))

    def _cancel_advance(self):
        if self._advance_job is not None:
            try:
                self.win.after_cancel(self._advance_job)
            except tk.TclError:
                pass
            self._advance_job = None

    def _advance(self):
        self._advance_job = None
        if self._closed:
            return
        self._revealed = False
        if self.sent_index >= len(self.story.sentences) - 1:
            self.state = "finished"
            self.entry.configure(state="normal")
            self.var.set("")
            self._show_message(self.T("done"))
            self._update_stats()
            return
        self.sent_index += 1
        self._activate_sentence()

    # --------------------------------------------------------------- stats
    def _update_stats(self):
        if self._closed:
            return
        frac = 0.0
        if self.state == "typing" and self.target:
            norm_len = max(1, len(self.judge.norm)) if self.judge else 1
            frac = (self.last_result.matched / norm_len) if self.last_result else 0.0
        if self.state == "finished":
            frac = 0.0
        progress = 100 if self.state == "finished" else self.stats.progress(frac)
        text =(f"{self.T('speed_stat')} {self.stats.cpm()} {self.T('cpm')}    "
                f"{self.T('accuracy')} {self.stats.accuracy()}%    "
                f"{self.T('progress')} {progress}%")
        if self.speed_mode == "auto":
            text += f"    {self.T('auto')} {int(self.pace_cpm())}"
        if self.whacks:
            text += f"    {self.T('score')} {self.whacks}"
        self.stats_label.configure(text=text)
        self._led_target = progress / 100.0

    def pace_cpm(self):
        return engine.pace_cpm(self.speed_mode, self.auto)

    # ------------------------------------------------------------ controls
    def set_speed(self, mode):
        self.speed_mode = mode
        self._flow_time = self.clock()
        self._relabel()

    def set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        self._revealed = False
        if self.story and self.state == "typing":
            res = self.last_result
            self._draw_sentence()
            if res:
                self._paint(res.states)
        self._relabel()

    def toggle_voice(self):
        self.voice_on = not self.voice_on
        if not self.voice_on:
            self.tts.cancel()
        else:
            self._voice_check = True
        self._relabel()

    def change_voice_rate(self, delta):
        self.voice_rate = max(-10, min(10, self.voice_rate + delta))
        self._relabel()

    def toggle_sound(self):
        self.sfx.enabled = not self.sfx.enabled
        if not self.sfx.enabled:
            self.sfx.stop()
        self._relabel()

    def _on_score(self, score):
        self.whacks += 1
        self._update_stats()

    def skip_effects(self):
        self.moles.stop()
        self._stop_rainbow()

    # ------------------------------------------------------- voice notice
    def _update_notice(self):
        show = False
        if self.voice_on and self.story:
            show = self.tts.has_voice(self.story.lang) is False
        mismatch = self.story and not self._keyboard_matches_story()
        language_notice = ("맞는 Windows 입력 모드를 선택하세요 (Win+Space / 한·영)." if self.ui_lang == "KO"
                           else "Select the matching Windows input mode (Win+Space / Korean-English).")
        text = "  ".join(part for part in (language_notice if mismatch else "",
                                           self.T("no_voice") if show else "") if part)
        self.notice_label.configure(text=text)
        self._notice_shown = show

    def _keyboard_matches_story(self):
        if not self.story or not getattr(self.hud, "input_driver", None):
            return True
        current = getattr(self.hud, "live_language", None)
        profile = getattr(self.hud, "profile_code", None)
        if self.story.lang in ("ko", "en"):
            return current == ("KR" if self.story.lang == "ko" else "EN")
        return profile == {"ja": "JP", "zh": "CN"}.get(self.story.lang)

    # ----------------------------------------------------------- rainbow
    def _start_rainbow(self):
        self.rainbow_start = self.clock()
        self._rainbow_last_keys = 0.0

    def _stop_rainbow(self):
        if self.rainbow_start is None:
            return
        self.rainbow_start = None
        self.glow.set_fx({})
        for i in range(LED_COUNT):
            self.led_shown[i] = None

    def _step_rainbow(self, now):
        t = now - self.rainbow_start
        if t >= RAINBOW_SECONDS:
            self._stop_rainbow()
            return
        env = math.sin(math.pi * t / RAINBOW_SECONDS)       # smooth in / out
        for i in range(LED_COUNT):
            hue = (i / LED_COUNT) * 0.8 + t / RAINBOW_SECONDS
            color = blend(FAINT, hsv_hex(hue, 0.55, 0.95), 0.25 + 0.75 * env)
            if self.led_shown[i] != color:
                self.leds.itemconfigure(self.led_items[i], fill=color)
                self.led_shown[i] = color
        # HUD keys at <= 10 Hz with quantised hue (no luminance flicker)
        if now - self._rainbow_last_keys >= 0.1:
            self._rainbow_last_keys = now
            keys = getattr(self.hud, "keys", None) or []
            right = max((k.bounds[2] for k in keys), default=1) or 1
            fx = {}
            for key in keys:
                u = ((key.bounds[0] + key.bounds[2]) / 2) / right
                hue = round(((u * 0.8 + t / RAINBOW_SECONDS) % 1.0) * 24) / 24
                fx[key.code] = blend("#000000", hsv_hex(hue, 0.55, 0.95), 0.55 * env)
            self.glow.set_fx(fx)

    # ------------------------------------------------------------- pacer
    def _step_pacer(self, now):
        if not self._chars or self.state not in ("typing", "advancing"):
            return
        elapsed = max(0.0, min(.12, now-self._flow_time))
        self._flow_time = now
        if now-self.sentence_started < PACE_LEAD:
            return
        cursor = self.last_result.cursor if self.last_result else 0
        x = self._chars[min(cursor, len(self._chars)-1)]["x"]
        # Keep the next character in view even when the reader pauses.
        lower = self.sent_w*.18-x
        upper = self.sent_w*.80-x
        pixels = elapsed*self.pace_cpm()/60.0*self._flow_width
        offset = min(upper, max(lower, self._flow_offset-pixels))
        self.sentence.move("flow", offset-self._flow_offset, 0)
        self._pace_pos += max(0.0, self._flow_offset-offset) / self._flow_width
        self._flow_offset = offset

    # --------------------------------------------------------------- LEDs
    def _step_leds(self, now):
        if self.rainbow_start is not None:
            return
        # slow low-pass: roughly a 1.5 s fade, never blinks
        diff = self._led_target - self._led_pos
        if abs(diff) > 0.0005:
            self._led_pos += diff * 0.06
        else:
            self._led_pos = self._led_target
        for i in range(LED_COUNT):
            lvl = max(0.0, min(1.0, self._led_pos * LED_COUNT - i))
            q = round(lvl * 24) / 24
            if self.led_shown[i] != q:
                self.led_shown[i] = q
                self.led_level[i] = q
                self.leds.itemconfigure(self.led_items[i], fill=blend(FAINT, self.highlight, 0.15 + 0.85 * q if q else 0))

    # --------------------------------------------------------------- loop
    def _schedule(self):
        if not self._closed:
            self._job = self.win.after(TICK_MS, self.tick)

    def tick(self):
        self._job = None
        if self._closed:
            return
        try:
            now = self.clock()
            if self.state == "typing":
                comp = self._composing_now()
                if comp != self._composing_prev:
                    self._evaluate()
            self._ticks = getattr(self, "_ticks", 0) + 1
            if self._ticks % 8 == 0:
                self.sync_hud()             # cheap: only acts when the window really moved
                matches = self._keyboard_matches_story()
                if matches != getattr(self, "_last_keyboard_match", None):
                    self._last_keyboard_match = matches
                    self._update_notice()
                    if self.last_result:
                        self._set_hint(self.last_result.cursor)
                    elif self.state == "typing":
                        self._set_hint(0)
            self._poll_ui_language()
            self._poll_voice()
            self._step_pacer(now)
            self._step_leds(now)
            self.moles.step(now)
            if self.rainbow_start is not None:
                self._step_rainbow(now)
            self.glow.expire(now)
        finally:
            self._schedule()

    def _poll_ui_language(self):
        lang = getattr(self.hud, "ui_language", self.ui_lang)
        if lang != self.ui_lang:
            self.ui_lang = lang
            self._relabel()

    def _poll_voice(self):
        if self._voice_check and self.story:
            known = self.tts.has_voice(self.story.lang)
            if known is not None:
                self._voice_check = False
                self._update_notice()
            elif not self.tts.started and self.voice_on:
                self.tts.start()

    # -------------------------------------------------------------- misc
    def alive(self):
        if self._closed:
            return False
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.entry.focus_force()
        except tk.TclError:
            pass

    def inject_commit(self, text):
        """Test/automation helper: behave as if `text` was committed in the Entry."""
        self.var.set(text)
        if self._evaluation_job is not None:
            self.win.after_cancel(self._evaluation_job)
            self._evaluate_entry()

    def _undock(self):
        """Give the keyboard back exactly as it was: layout, size, display, language and position."""
        if not self.docked:
            return
        self.docked = False
        try:
            self.hud.set_docked(False)
            if self.root.state() == "withdrawn":
                self.root.deiconify()
            if self._saved_language and getattr(self.hud, "language", None) != self._saved_language:
                self.hud.select_language(self._saved_language)
            if self._saved_pos:
                self.root.geometry(f"+{self._saved_pos[0]}+{self._saved_pos[1]}")
        except Exception:
            pass

    def _on_destroy(self, event):
        if event.widget is self.win and not self._closed:
            self.close()

    def close(self):
        if self._closed:
            return
        self._closed = True
        for job in (self._job, self._advance_job, self._evaluation_job):
            if job is not None:
                try:
                    self.win.after_cancel(job)
                except tk.TclError:
                    pass
        self._job = self._advance_job = self._evaluation_job = None
        try:
            self.moles.stop()
        except Exception:
            pass
        self.rainbow_start = None
        try:
            self.var.set("")
        except tk.TclError:
            pass
        self.glow.clear_all()
        hooks = getattr(self.hud, "render_hooks", None)
        if isinstance(hooks, list) and self.glow.on_render in hooks:
            hooks.remove(self.glow.on_render)
        unreg = getattr(self.hud, "unregister_safe_window", None)
        if unreg and getattr(self, "hwnd", 0):
            try:
                unreg(self.hwnd)
            except Exception:
                pass
        try:
            self.tts.close()
        except Exception:
            pass
        try:
            self.sfx.close()
        except Exception:
            pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        self._undock()
        callback, self.on_closed = self.on_closed, None
        if callback:
            callback(self)
        self.judge = self.story = None
        self._chars = []
        gc.collect()
