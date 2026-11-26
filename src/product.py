"""Identity and optional, local-only supporter styles for HoloKeyboard V1."""
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import webbrowser

BRAND = "AI Companion Lab"
PRODUCT = "HoloKeyboard"
VERSION = "1.0.0"
DONATE_URL = "https://ko-fi.com/aiportal"
FUNDING_PLATFORM = "AI World Portal"
DONATION_NOTICE = (
    "Donations are entirely voluntary.\n"
    "We trust and respect every user's personal choice.\n"
    "We hope HoloKeyboard makes your everyday life a little better.",
    "후원은 의무가 아닌 자율적인 선택입니다.\n"
    "우리는 모든 사용자의 양심과 선택을 존중합니다.\n"
    "HoloKeyboard가 여러분에게 도움이 되기를 바랍니다.",
)
PASSWORD_WARNING = (
    "Please turn Input Lock ON before entering passwords.",
    "비밀번호 입력 시 입력잠금을 ON으로 설정해 주세요.",
)


class SupportSettings:
    def __init__(self, path=None):
        local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        self.path = Path(path) if path is not None else local / BRAND / PRODUCT / "support.json"
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.confirmed = isinstance(data, dict) and data.get("support_confirmed") is True
        except (OSError, ValueError):
            self.confirmed = False

    def confirm(self, value):
        folder = self.path.parent
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder, delete=False) as handle:
            temporary = Path(handle.name)
            try:
                json.dump({"support_confirmed": bool(value)}, handle)
            except OSError:
                handle.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.confirmed = bool(value)


def _dialog(owner, title):
    window = tk.Toplevel(owner)
    window.title(f"{PRODUCT} — {title}")
    box = ttk.Frame(window, padding=18)
    box.pack(fill="both", expand=True)
    window.bind("<Escape>", lambda _event: window.destroy())
    return window, box


def show_about(owner, text):
    window, box = _dialog(owner, text("About", "제품 정보"))
    ttk.Label(box, text=f"{PRODUCT} V{VERSION}", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(box, text=BRAND).pack(anchor="w", pady=(4, 14))
    ttk.Button(box, text=text("Close", "닫기"), command=window.destroy).pack(anchor="e")
    return window


def show_support(owner, text, settings, changed):
    window, box = _dialog(owner, text("Donate", "후원"))
    ttk.Label(box, text=f"{BRAND} · {PRODUCT}").pack(anchor="w")
    ttk.Label(box, text=text(*DONATION_NOTICE), wraplength=390, justify="left").pack(anchor="w", pady=(8, 0))
    ttk.Label(box, text=text(
        "All core features and the blue style are free. The full palette and border width are available "
        "to supporters. Confirm your contribution on your honor. The app saves the checkbox locally.",
        "핵심 기능과 파란색 스타일은 무료입니다. 전체 색상과 테두리 두께는 후원 스타일입니다. "
        "후원 여부를 직접 확인하면 체크 상태를 이 PC에 저장합니다."),
        wraplength=390, justify="left").pack(anchor="w", pady=(8, 12))
    ttk.Button(box, text=f"{FUNDING_PLATFORM} · Ko-fi",
               command=lambda: webbrowser.open(DONATE_URL)).pack(anchor="w")
    ttk.Label(box, text=DONATE_URL).pack(anchor="w", pady=(4, 10))
    choice = tk.BooleanVar(window, value=settings.confirmed)
    ttk.Checkbutton(box, text=text("I confirm that I have donated.", "후원했음을 확인합니다."),
                    variable=choice).pack(anchor="w")
    error = ttk.Label(box, foreground="#b63e27")
    error.pack(anchor="w", pady=4)

    def apply():
        try:
            settings.confirm(choice.get())
        except OSError:
            error.configure(text=text("Could not save the setting.", "설정을 저장하지 못했습니다."))
            return
        changed()
        window.destroy()

    ttk.Button(box, text=text("Apply", "적용"), command=apply).pack(anchor="e")
    return window
