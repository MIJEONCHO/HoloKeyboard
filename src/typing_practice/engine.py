"""Pure-python judging, stats, pacing and next-key mapping for typing practice.

Nothing here touches Tk, the disk or the network. Typed text is only ever a
transient argument: the judge keeps lengths and flags, never the text itself.
"""
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

PENDING, OK, BAD = 0, 1, 2

# ---------------------------------------------------------------- normalising

_LENIENT_LANGS = ("zh", "ja")


def _skippable(ch, lang):
    """Characters that zh/ja learners may omit (spaces and any punctuation)."""
    return ch.isspace() or unicodedata.category(ch).startswith("P")


def normalize_with_map(text, lang):
    """Return (normalised text, map normalised index -> original index)."""
    text = unicodedata.normalize("NFC", text)
    out, index = [], []
    if lang in _LENIENT_LANGS:
        for i, ch in enumerate(text):
            if not _skippable(ch, lang):
                out.append(ch)
                index.append(i)
    else:
        previous_space = True  # drops leading spaces, collapses runs
        for i, ch in enumerate(text):
            if ch.isspace():
                if not previous_space:
                    out.append(" ")
                    index.append(i)
                previous_space = True
            else:
                out.append(ch)
                index.append(i)
                previous_space = False
        while out and out[-1] == " ":
            out.pop()
            index.pop()
    return "".join(out), index


def normalize(text, lang, *, keep_trailing_space=False):
    """Normalised comparison form. Trailing space is kept only for prefixes."""
    text = unicodedata.normalize("NFC", text)
    if lang in _LENIENT_LANGS:
        return "".join(ch for ch in text if not _skippable(ch, lang))
    trailing = keep_trailing_space and text[-1:].isspace()
    result, _ = normalize_with_map(text, lang)
    return result + (" " if trailing and result else "")


# -------------------------------------------------------------------- judging

@dataclass
class JudgeResult:
    states: list                    # per ORIGINAL target char: PENDING/OK/BAD
    matched: int = 0                # normalised chars matched so far
    wrong: bool = False             # a committed mismatch exists
    unresolved: int = 0             # committed mismatches currently in the Entry
    added_errors: int = 0           # newly committed mismatches since the prior update
    composing_pending: bool = False  # last char is being composed, not judged
    complete: bool = False
    new_error: bool = False         # True once per wrong commit
    advanced: bool = False          # matched count grew since last update
    cursor: int = 0                 # original index of the next char to type
    typed_last: str = ""            # last typed char (transient, not stored)
    target_last: str = ""           # last correctly matched target char


class Judge:
    """Judges committed text against one target sentence.

    `composing` may be a callable or a bool passed to update(). While it is
    truthy, a mismatch on the very last typed character is treated as the
    unfinished IME syllable and is neither coloured red nor counted.
    """

    def __init__(self, target, lang, composing=None):
        self.target = target
        self.lang = lang
        self.norm, self.map = normalize_with_map(target, lang)
        self.composing = composing
        self._prev_matched = 0
        self._prev_wrong = False
        self._prev_unresolved = 0

    def reset(self):
        self._prev_matched = 0
        self._prev_wrong = False
        self._prev_unresolved = 0

    def _is_composing(self, override):
        if override is not None:
            return max(0, int(override))
        if callable(self.composing):
            try:
                return max(0, int(self.composing()))
            except Exception:
                return False
        return max(0, int(self.composing or 0))

    def update(self, typed, composing=None):
        comp = self._is_composing(composing)
        norm = self.norm
        t = normalize(typed, self.lang, keep_trailing_space=True)
        committed = normalize(typed[:-comp], self.lang, keep_trailing_space=True) if comp else t
        unresolved = sum(a != b for a, b in zip(committed, norm))
        unresolved += len(committed[len(norm):].strip())
        mism = None
        for i, ch in enumerate(committed):
            if i >= len(norm):
                if committed[i:].strip():
                    mism = i
                break
            if ch != norm[i]:
                mism = i
                break
        pending_comp = bool(comp and len(t) > len(committed))
        matched = len(committed) if mism is None else mism
        matched = min(matched, len(norm))
        wrong = mism is not None
        complete = (not wrong and not comp and matched == len(norm) and len(norm) > 0
                    and t.strip() == norm)
        states = [PENDING] * len(self.target)
        for k in range(matched):
            states[self.map[k]] = OK
        if self.map:
            # Skipped (punctuation/space) chars between matched chars are OK.
            last_ok = self.map[matched - 1] if matched else -1
            for i in range(last_ok + 1):
                if states[i] == PENDING:
                    states[i] = OK
            if matched == len(norm):
                for i in range(len(states)):
                    states[i] = OK
        if wrong:
            for i in range(mism, min(len(committed), len(norm))):
                states[self.map[i]] = BAD if committed[i] != norm[i] else OK
        cursor = len(self.target) if matched >= len(norm) else self.map[matched]
        if not wrong and matched and matched < len(norm):
            cursor = self.map[matched - 1] + 1 if self.lang in _LENIENT_LANGS else self.map[matched]
        new_error = wrong and not self._prev_wrong
        advanced = matched > self._prev_matched
        result = JudgeResult(
            states=states, matched=matched, wrong=wrong, unresolved=unresolved, composing_pending=pending_comp,
            added_errors=max(0, unresolved-self._prev_unresolved),
            complete=complete, new_error=new_error, advanced=advanced, cursor=cursor,
            typed_last=committed.rstrip()[-1:],
            target_last=(norm[matched - 1] if matched else ""),
        )
        self._prev_matched = matched
        self._prev_wrong = wrong
        if not comp:
            self._prev_unresolved = unresolved
        return result


# ---------------------------------------------------------------------- stats

class Stats:
    """Typing speed (characters per minute), accuracy and progress."""

    IDLE_CAP = 3.0  # seconds: longer gaps are not counted as typing time

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.reset()

    def reset(self):
        self.active = 0.0
        self.errors = 0
        self.done_chars = 0      # chars of completed sentences
        self.cur_correct = 0     # correct chars of the current sentence
        self.sentences_done = 0
        self.sentences_total = 0
        self._last = None

    def touch(self):
        now = self.clock()
        if self._last is not None:
            self.active += min(max(0.0, now - self._last), self.IDLE_CAP)
        self._last = now

    def note_error(self, count=1):
        self.errors += count

    def set_current(self, correct):
        self.cur_correct = max(0, correct)

    def sentence_done(self, length):
        self.done_chars += length
        self.cur_correct = 0
        self.sentences_done += 1

    def new_sentence(self):
        self.cur_correct = 0
        self._last = None  # the pause between sentences is not typing time

    @property
    def correct_total(self):
        return self.done_chars + self.cur_correct

    def cpm(self):
        if self.active < 1.0:
            return 0
        return int(round(self.correct_total / (self.active / 60.0)))

    def accuracy(self):
        total = self.correct_total + self.errors
        return 100 if total == 0 else int(round(100.0 * self.correct_total / total))

    def progress(self, fraction_of_current=0.0):
        if not self.sentences_total:
            return 0
        value = (self.sentences_done + max(0.0, min(1.0, fraction_of_current))) / self.sentences_total
        return int(round(100 * min(1.0, value)))


# -------------------------------------------------------------- speed / pacer

LEVEL_CPM = {1: 60, 2: 110, 3: 180, 4: 270, 5: 380}   # pacing guide, chars/min


class AutoSpeed:
    """AUTO pacing: ~110% of the learner's recent speed, always bounded."""

    MIN_CPM, MAX_CPM, FACTOR, START = 40, 480, 1.10, 100

    def __init__(self):
        self._ema = None

    def observe(self, sentence_cpm):
        if sentence_cpm is None or sentence_cpm <= 0:
            return
        sample = max(10.0, min(1000.0, float(sentence_cpm)))
        self._ema = sample if self._ema is None else 0.6 * self._ema + 0.4 * sample

    @property
    def cpm(self):
        if self._ema is None:
            return float(self.START)
        return max(float(self.MIN_CPM), min(float(self.MAX_CPM), self._ema * self.FACTOR))


def pace_cpm(mode, auto):
    """mode: 'auto' or a level 1..5."""
    if mode == "auto":
        return auto.cpm
    return float(LEVEL_CPM.get(int(mode), LEVEL_CPM[2]))


# ------------------------------------------------------------ next-key mapping

_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = [""] + list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")
_SPLIT = {
    "ㅘ": "ㅗㅏ", "ㅙ": "ㅗㅐ", "ㅚ": "ㅗㅣ", "ㅝ": "ㅜㅓ", "ㅞ": "ㅜㅔ", "ㅟ": "ㅜㅣ", "ㅢ": "ㅡㅣ",
    "ㄳ": "ㄱㅅ", "ㄵ": "ㄴㅈ", "ㄶ": "ㄴㅎ", "ㄺ": "ㄹㄱ", "ㄻ": "ㄹㅁ", "ㄼ": "ㄹㅂ",
    "ㄽ": "ㄹㅅ", "ㄾ": "ㄹㅌ", "ㄿ": "ㄹㅍ", "ㅀ": "ㄹㅎ", "ㅄ": "ㅂㅅ",
}
_LEFT_HAND = {
    "Backquote", "Digit1", "Digit2", "Digit3", "Digit4", "Digit5", "KeyQ", "KeyW", "KeyE", "KeyR",
    "KeyT", "KeyA", "KeyS", "KeyD", "KeyF", "KeyG", "KeyZ", "KeyX", "KeyC", "KeyV", "KeyB",
}


def hangul_jamo(ch):
    """Decompose a syllable/jamo into the jamo sequence typed on a 2-set board."""
    code = ord(ch) - 0xAC00
    if 0 <= code < 11172:
        seq = _CHO[code // 588] + _JUNG[(code % 588) // 28] + _JONG[code % 28]
    elif "ㄱ" <= ch <= "ㆎ":
        seq = ch
    else:
        return None
    return "".join(_SPLIT.get(j, j) for j in seq)


def _import_layout():
    try:
        import v8_layout
        return v8_layout
    except ImportError:
        import importlib.util
        path = Path(__file__).resolve().parent.parent / "v8_layout.py"
        spec = importlib.util.spec_from_file_location("v8_layout", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("v8_layout", module)
        spec.loader.exec_module(module)
        return module


class KeyMapper:
    """Maps target characters to HUD key codes (plus Shift when needed)."""

    def __init__(self, layouts=None, key_rows=None):
        if layouts is None or key_rows is None:
            module = _import_layout()
            layouts = layouts or module.LAYOUTS
            key_rows = key_rows or module.KEY_ROWS
        self.latin = {}
        for row in key_rows:
            for code, normal, shifted, _width, special in row:
                if special is not None and code != "Space":
                    continue
                if code == "Space":
                    self.latin[" "] = (code, False)
                    continue
                self.latin.setdefault(normal, (code, False))
                if shifted != normal:
                    self.latin.setdefault(shifted, (code, True))
        self.jamo = {}
        for code, (normal, shifted) in (layouts.get("KR") or {}).items():
            self.jamo.setdefault(normal, (code, False))
            if shifted != normal:
                self.jamo.setdefault(shifted, (code, True))

    def strokes(self, ch, lang):
        """List of (key code, shift) strokes to type `ch`, or [] if unmappable."""
        if lang not in ("ko", "en"):
            return []
        if lang == "ko":
            jamo = hangul_jamo(ch)
            if jamo is not None:
                seq = [self.jamo.get(j) for j in jamo]
                return [] if any(s is None for s in seq) else seq
        entry = self.latin.get(ch)
        return [entry] if entry else []

    @staticmethod
    def _with_shift(stroke):
        code, shift = stroke
        if not shift:
            return [code]
        return [code, "ShiftRight" if code in _LEFT_HAND else "ShiftLeft"]

    def hint_codes(self, ch, lang):
        """Key codes to softly highlight for the first stroke of `ch`."""
        seq = self.strokes(ch, lang)
        return self._with_shift(seq[0]) if seq else []

    def last_code(self, ch, lang):
        """Key code that finished typing `ch` (used for the green/red flash)."""
        seq = self.strokes(ch, lang)
        return seq[-1][0] if seq else None
