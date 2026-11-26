"""Lazy-loaded story typing practice for HoloKeyboard.

Importing this package is nearly free; the window, audio and speech code are
only imported when open(hud) is called (from the HUD settings menu).
"""
_window = None


def open(hud, **options):  # noqa: A001 - public entry point name is part of the HUD contract
    """Open (or focus) the single practice window and return it."""
    global _window
    if _window is not None and _window.alive():
        _window.focus()
        return _window
    from . import ui
    _window = ui.PracticeWindow(hud, on_closed=_forget, **options)
    return _window


def _forget(window):
    global _window
    if _window is window:
        _window = None


def close():
    """Close the practice window if it is open (idempotent)."""
    if _window is not None:
        _window.close()


def is_open():
    return _window is not None and _window.alive()
