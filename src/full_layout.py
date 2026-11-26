"""Standard full-size layout as a unit grid. The HUD turns units into pixels.

Compact (v8_layout.KEY_ROWS) is never touched. Rows 1-4 of Full reuse the Compact
legends and widths, so a key has one code and one legend in both layouts.
"""
from v8_layout import KEY_ROWS

MAIN_UNITS = 15
FULL_UNITS = 23           # 15 main + .5 + 3 navigation + .5 + 4 keypad
FULL_ROW_COUNT = 6        # function row + five main rows
FN_ROW_GAP = .25          # extra space (in row pitches) under the function row
NAV_X, PAD_X = 15.5, 19

# A key spec is (code, normal, shifted, special, x_units, row, width_units, rows_tall).


def _row(row, items, x=0):
    out = []
    for code, normal, shifted, units, special in items:
        out.append((code, normal, shifted, special, x, row, units, 1))
        x += units
    return out


def full_specs(special_widths):
    """Return every Full key spec. special_widths gives the main-block widths."""
    specs = []
    # Function row: Esc, F1-F4, F5-F8, F9-F12 and the two system keys.
    specs.append(("Escape", "Esc", "Esc", "fn", 0, 0, 1, 1))
    for number in range(1, 13):
        x = 1 + number + (.5 if number > 4 else 0) + (.5 if number > 8 else 0)
        specs.append((f"F{number}", f"F{number}", f"F{number}", "fn", x, 0, 1, 1))
    specs.append(("PrintScreen", "PrtSc", "PrtSc", "nav", NAV_X, 0, 1, 1))
    specs.append(("ScrollLock", "ScrLk", "ScrLk", "nav", NAV_X+1, 0, 1, 1))
    # Rows 1-4 reuse the Compact definitions and widths.
    for index, source in enumerate(KEY_ROWS[:4]):
        specs += _row(index+1, [(code, normal, shifted, special_widths.get(code, width), special)
                                for code, normal, shifted, width, special in source])
    # Bottom row: 8 x 1.25 + 5 = 15 units, the Korean/AltGr key stays next to Alt.
    bottom = (("CtrlLeft", "Ctrl", 1.25, "mod"), ("WinLeft", "Win", 1.25, "mod"),
              ("AltLeft", "Alt", 1.25, "mod"), ("Space", "KR · Space", 5, "space"),
              ("AltRight", "Alt", 1.25, "mod"), ("LangToggle", "한/영", 1.25, "lang"),
              ("WinRight", "Win", 1.25, "mod"), ("Menu", "Menu", 1.25, "nav"),
              ("CtrlRight", "Ctrl", 1.25, "mod"))
    specs += _row(5, [(code, text, text, width, special) for code, text, width, special in bottom])
    # Navigation block.
    for code, text, x, row in (("Insert", "Ins", 0, 1), ("Home", "Home", 1, 1), ("PageUp", "PgUp", 2, 1),
                               ("Delete", "Del", 0, 2), ("End", "End", 1, 2), ("PageDown", "PgDn", 2, 2),
                               ("ArrowUp", "↑", 1, 4), ("ArrowLeft", "←", 0, 5),
                               ("ArrowDown", "↓", 1, 5), ("ArrowRight", "→", 2, 5)):
        specs.append((code, text, text, "nav", NAV_X+x, row, 1, 1))
    # Numeric keypad.
    pad = (("NumLock", "Num", 0, 1, 1, 1), ("NumpadDivide", "/", 1, 1, 1, 1),
           ("NumpadMultiply", "*", 2, 1, 1, 1), ("NumpadSubtract", "-", 3, 1, 1, 1),
           ("Numpad7", "7", 0, 2, 1, 1), ("Numpad8", "8", 1, 2, 1, 1), ("Numpad9", "9", 2, 2, 1, 1),
           ("NumpadAdd", "+", 3, 2, 1, 2),
           ("Numpad4", "4", 0, 3, 1, 1), ("Numpad5", "5", 1, 3, 1, 1), ("Numpad6", "6", 2, 3, 1, 1),
           ("Numpad1", "1", 0, 4, 1, 1), ("Numpad2", "2", 1, 4, 1, 1), ("Numpad3", "3", 2, 4, 1, 1),
           ("NumpadEnter", "Enter", 3, 4, 1, 2),
           ("Numpad0", "0", 0, 5, 2, 1), ("NumpadDecimal", ".", 2, 5, 1, 1))
    for code, text, x, row, units, tall in pad:
        specs.append((code, text, text, "pad", PAD_X+x, row, units, tall))
    return specs
