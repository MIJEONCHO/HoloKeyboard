"""Hover tooltip for the HUD controls.

A small borderless Toplevel shown ~400 ms after the pointer rests on a control. It never takes focus or
activation (WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT on a layered window, shown with
SWP_NOACTIVATE) and sits beside the pointer, so it neither changes the HUD's no-activate style nor
steals clicks. It holds only fixed help text, never typed text."""
import tkinter as tk

import win_native as win

DELAY_MS = 400
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x20, 0x80, 0x08000000
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x10, 0x40
BG, FG, EDGE = "#101923", "#e6f4ff", "#00a8e8"


class Tooltip:
    def __init__(self, root, delay_ms=DELAY_MS):
        self.root, self.delay = root, delay_ms
        self.window = self.label = None
        self.job = None
        self.key = None        # what the pending/visible tooltip is for
        self.text = ""         # text currently shown (tests read this)

    # ---- public ------------------------------------------------------------------------------
    def hover(self, key, text_fn, x_root, y_root):
        """Pointer is over control `key` (None = over nothing). `text_fn()` gives the text lazily."""
        if key is None:
            self.hide()
            return
        if key == self.key:
            return                       # still the same control: keep waiting / keep showing
        self.hide()
        self.key = key
        self.job = self.root.after(self.delay, lambda: self._show(text_fn, x_root, y_root))

    def hide(self):
        if self.job is not None:
            try:
                self.root.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None
        self.key, self.text = None, ""
        if self.window is not None:
            try:
                self.window.withdraw()
            except tk.TclError:
                self.window = self.label = None

    def close(self):
        self.hide()
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = self.label = None

    @property
    def visible(self):
        try:
            return bool(self.window is not None and self.text and self.window.state() == "normal")
        except tk.TclError:
            return False

    @property
    def hwnd(self):
        return win.get_ancestor(self.window.winfo_id(), 2) if self.window is not None else None

    # ---- internals ---------------------------------------------------------------------------
    def _build(self):
        window = tk.Toplevel(self.root, bg=EDGE)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-alpha", .97)   # layered: lets WS_EX_TRANSPARENT make it click-through
        self.label = tk.Label(window, bg=BG, fg=FG, justify="left", wraplength=330, padx=8, pady=5,
                              font=("Malgun Gothic", 9), bd=0)
        self.label.pack(padx=1, pady=1)
        self.window = window
        window.update_idletasks()
        hwnd = win.get_ancestor(window.winfo_id(), 2)
        if hwnd:
            style = win.get_style(hwnd, -20)
            win.set_style(hwnd, -20, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT)

    def _show(self, text_fn, x_root, y_root):
        self.job = None
        text = text_fn()
        if not text:
            return
        if self.window is None:
            self._build()
        self.label.configure(text=text)
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        x, y = x_root+14, y_root+20
        right, bottom = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if x+width > right:
            x = max(0, right-width-4)
        if y+height > bottom:
            y = max(0, y_root-height-10)
        self.text = text
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        if self.window.state() == "withdrawn":
            self.window.deiconify()      # WS_EX_NOACTIVATE is already set: this does not activate
        hwnd = win.get_ancestor(self.window.winfo_id(), 2)
        if hwnd:
            win.set_pos(hwnd, -1, x, y, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW)
