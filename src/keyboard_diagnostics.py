"""Reusable, explicitly opened Windows keyboard diagnostics."""
import ctypes as c
import tkinter as tk

import win_native as n

set_fg = n.api(n.USER, "SetForegroundWindow", n.w.BOOL, n.w.HWND)
set_focus = n.api(n.USER, "SetFocus", n.w.HWND, n.w.HWND)


def enable_dpi():
    n.api(n.USER, "SetProcessDpiAwarenessContext", n.w.BOOL, c.c_void_p)(c.c_void_p(-4))


class KeyboardDiagnostics:
    def __init__(self, root, driver=None, *, physical=False):
        self.window = tk.Toplevel(root)
        self.window.title("HoloKeyboard TEST — disposable input")
        self.window.geometry("470x257+100+459" if physical else "420x150+100+485")
        self.window.attributes("-topmost", True)
        self.window.update_idletasks()
        self.native = self.window.winfo_id()
        self.top = n.get_ancestor(self.native, 2)
        self.driver = driver
        self.status_job = None
        offset = 110 if physical else 0
        self.normal = self._edit(13+offset, False)
        self.protected = self._edit(57+offset, True)
        self.unsupported = self._edit(101+offset, False)
        if driver:
            # Only the disposable registered controls may display local typing.
            for hwnd in (self.normal, self.protected):
                driver.ui.guard.register_safe_control(hwnd)
        if physical:
            self._physical_panel()

    def _physical_panel(self):
        intro = tk.Label(self.window, anchor="w")
        intro.place(x=16, y=3)
        hint = tk.Label(self.window, anchor="w")
        hint.place(x=16, y=23)
        status = tk.Label(self.window, anchor="w", justify="left", wraplength=430)
        status.place(x=16, y=46)
        tk.Button(self.window, text="?", width=4, command=self.driver.ui.show_help).place(x=16, y=72)
        close = tk.Button(self.window, command=self.close)
        close.place(x=68, y=72)
        fields = []
        for y in (104, 149, 193):
            label = tk.Label(self.window, anchor="w")
            label.place(x=16, y=y)
            fields.append(label)
        displayed_language = None

        def show_state():
            nonlocal displayed_language
            if self.driver.closed:
                return
            english = self.driver.ui.ui_language == "EN"
            if self.driver.ui.ui_language != displayed_language:
                displayed_language = self.driver.ui.ui_language
                self.window.title("HoloKeyboard — " + ("Keyboard Diagnostics" if english else "키보드 진단"))
                intro.configure(text=("Click the top field. Hold A for one second, then release."
                                      if english else "맨 위 입력란을 클릭하고 A만 1초간 누른 뒤 떼세요."))
                hint.configure(text=("Try Shift separately. Use dummy text only."
                                     if english else "Shift도 따로 시험하세요. 시험용 문자만 입력하세요."))
                close.configure(text="Close diagnostics" if english else "진단 닫기")
                names = ("Registered input", "Password — blocked", "Unregistered — blocked") if english else (
                    "일반·등록", "비밀번호·차단", "미등록·차단"
                )
                for field, name in zip(fields, names):
                    field.configure(text=name)
            keys = sorted(self.driver.key_glow.pressed())
            if english:
                state = "On" if self.driver.raw.enabled else "Off"
                text = f"Mirror detection: {state} / Keys held: " + (", ".join(keys) or "None")
            else:
                state = "등록" if self.driver.raw.enabled else "해제"
                text = f"미러 감지: {state} / 현재 누른 물리 키: " + (", ".join(keys) or "없음")
            status.configure(text=text)
            self.status_job = self.window.after(40, show_state)

        self.window.protocol("WM_DELETE_WINDOW", self.close)
        show_state()

    def close(self):
        if not self.window.winfo_exists():
            return
        if self.status_job is not None:
            self.window.after_cancel(self.status_job)
            self.status_job = None
        if self.driver:
            for hwnd in (self.normal, self.protected):
                self.driver.ui.guard.unregister_safe_window(hwnd)
        self.window.destroy()
        if self.driver and not self.driver.closed:
            self.driver.refresh()

    def _edit(self, y, password):
        style = 0x50810080 | (0x20 if password else 0)
        hwnd = n.checked(n.create_window(0, "Edit", "", style, 16, y, 379, 32,
                                         self.native, None, n.module_handle(None), None))
        return hwnd

    def focus(self, hwnd):
        self.window.lift()
        self.window.update()
        set_fg(self.top)
        set_focus(hwnd)
        self.window.update()
