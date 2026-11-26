"""A bounded, disposable line assembled from HUD key events."""
import input_profiles as profiles
from v8_layout import KEY_ROWS, LAYOUTS

_BASE_KEYS = {code: (normal, shifted) for row in KEY_ROWS for code, normal, shifted, _, special in row
              if special is None}
from typing_practice.engine import _CHO, _JUNG, _JONG, _SPLIT

_JOIN = {pair: combined for combined, pair in _SPLIT.items()}
MAX_LINE = 120


class KeyPreview:
    def __init__(self):
        self.clear()

    def clear(self):
        self.line = ""
        self.first = self.vowel = self.last = ""

    @property
    def pending(self):
        if self.first and self.vowel:
            return chr(0xAC00 + (_CHO.index(self.first) * 21 + _JUNG.index(self.vowel)) * 28
                       + _JONG.index(self.last))
        return self.first or self.vowel

    @property
    def text(self):
        return (self.line + self.pending)[-MAX_LINE:]

    def _commit(self):
        self.line = (self.line + self.pending)[-MAX_LINE:]
        self.first = self.vowel = self.last = ""

    def backspace(self):
        if self.last:
            self.last = _SPLIT.get(self.last, "")[:1]
        elif self.vowel:
            self.vowel = _SPLIT.get(self.vowel, "")[:1]
        elif self.first:
            self.first = ""
        else:
            self.line = self.line[:-1]

    def append(self, value, korean=False):
        if korean and len(value) == 1 and value in _JUNG:
            self._add_vowel(value)
        elif korean and len(value) == 1 and value in _CHO:
            self._add_consonant(value)
        else:
            self._commit()
            self.line = (self.line + value)[-MAX_LINE:]

    def _add_vowel(self, value):
        if self.last:
            parts = _SPLIT.get(self.last, self.last)
            self.last = parts[:-1]
            self._commit()
            self.first, self.vowel = parts[-1], value
        elif self.vowel:
            combined = _JOIN.get(self.vowel + value)
            if combined is not None and combined in _JUNG:
                self.vowel = combined
            else:
                self._commit()
                self.vowel = value
        else:
            self.vowel = value

    def _add_consonant(self, value):
        if self.first and self.vowel and value in _JONG:
            combined = _JOIN.get(self.last + value) if self.last else value
            if combined in _JONG:
                self.last = combined
                return
        self._commit()
        self.first = value



class LocalPreview:
    """One local line for a verified target. No external value reader."""

    def __init__(self):
        self.scope = self.token = None
        self.suspended = False
        self.line = KeyPreview()

    def set_target(self, scope, suspended=False):
        if scope != self.scope:
            self.line.clear()
        if scope != self.scope or suspended != self.suspended:
            self.token = object() if scope and not suspended else None
        self.scope, self.suspended = scope, suspended

    def display(self):
        if self.suspended:
            return "입력 보호 확인 중", ""
        if not self.scope:
            return "입력 표시 차단", ""
        if self.scope[2] not in ("KR", "EN"):
            return "키 입력 모드 미확인", ""
        return "키 입력 대기", self.line.text

    def key(self, code, scan, shift, caps):
        if self.token is None:
            return
        _, layout, language, _, fallback = self.scope
        if language not in ("KR", "EN"):
            return
        if code in ("Escape", "Delete", "Home", "End", "PageUp", "PageDown", "LangToggle"):
            self.line.clear()
        elif code == "Backspace":
            self.line.backspace()
        elif code == "Space":
            self.line.append(" ")
        elif scan:
            korean = language == "KR"
            legends = LAYOUTS["KR"].get(code) if korean else None
            if legends:
                value = legends[int(shift)]
            elif fallback:
                base = _BASE_KEYS.get(code)
                value = base[int(shift ^ caps if code.startswith("Key") else shift)] if base else None
            else:
                value = profiles.legend(layout, scan, shift, caps)
            if value:
                self.line.append(value, korean)
