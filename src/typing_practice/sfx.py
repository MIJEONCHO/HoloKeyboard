"""Tiny in-memory sound effects: 16-bit mono WAVs synthesised on demand."""
import io
import math
import random
import threading
import wave

RATE = 22050
MAX_MS = 400
PEAK = 0.40  # fraction of full scale, keeps the sounds moderate


def _env(n, i, attack, decay):
    a = min(1.0, i / max(1, attack))
    return a * math.exp(-decay * i / max(1, n))


def _tone(freq, ms, vol, decay=4.0, sweep_to=None, harmonics=((1, 1.0),)):
    n = int(RATE * ms / 1000)
    attack = int(RATE * 0.004)
    out, phase = [], 0.0
    for i in range(n):
        f = freq if sweep_to is None else freq + (sweep_to - freq) * i / n
        phase += 2 * math.pi * f / RATE
        s = sum(w * math.sin(phase * h) for h, w in harmonics)
        out.append(s * vol * _env(n, i, attack, decay))
    return out


def _mix(parts, total_ms):
    n = int(RATE * total_ms / 1000)
    buf = [0.0] * n
    for start_ms, samples in parts:
        s0 = int(RATE * start_ms / 1000)
        for i, v in enumerate(samples):
            if s0 + i < n:
                buf[s0 + i] += v
    return buf


def to_wav(samples):
    peak = max((abs(v) for v in samples), default=0.0)
    scale = 1.0 if peak <= PEAK else PEAK / peak
    pcm = bytearray()
    for v in samples:
        iv = int(max(-1.0, min(1.0, v * scale)) * 32767)
        pcm += iv.to_bytes(2, "little", signed=True)
    # Short fade-out so no click occurs at the end.
    fade = min(len(pcm) // 2, 120)
    for k in range(fade):
        idx = len(pcm) - 2 * (k + 1)
        iv = int.from_bytes(pcm[idx:idx + 2], "little", signed=True)
        pcm[idx:idx + 2] = int(iv * (k / fade)).to_bytes(2, "little", signed=True)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(pcm))
    return buf.getvalue()


def make_typo():
    return to_wav(_tone(190, 110, 0.30, decay=5.0, sweep_to=140))


def make_chime():
    return to_wav(_mix([(0, _tone(784, 170, 0.30, 3.5, harmonics=((1, 1), (2, .25)))),
                        (140, _tone(1047, 230, 0.30, 3.5, harmonics=((1, 1), (2, .25))))], 380))


def make_pop():
    rnd = random.Random(7)
    noise = [rnd.uniform(-1, 1) * 0.12 * math.exp(-i / 90) for i in range(int(RATE * 0.03))]
    body = _tone(620, 90, 0.34, decay=6.0, sweep_to=220)
    return to_wav(_mix([(0, body), (0, noise)], 100))


def make_arpeggio():
    notes = (523.25, 659.25, 783.99, 1046.5)
    parts = [(i * 85, _tone(f, 120, 0.26, 3.0, harmonics=((1, 1), (2, .2)))) for i, f in enumerate(notes)]
    return to_wav(_mix(parts, 390))


MAKERS = {"typo": make_typo, "chime": make_chime, "pop": make_pop, "arpeggio": make_arpeggio}


class Sfx:
    """Plays cached WAVs. `player(data)` is injectable so tests stay silent."""

    def __init__(self, enabled=True, player=None):
        self.enabled = enabled
        self._player = player
        self._cache = {}
        self._wake = threading.Condition()
        self._thread = None
        self._next = None
        self._closed = False
        self.played = []  # names only; no typed text is ever involved

    def wav(self, name):
        if name not in self._cache:
            self._cache[name] = MAKERS[name]()
        return self._cache[name]

    @staticmethod
    def _winsound_play(data):
        import winsound
        winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)

    def _run(self):
        while True:
            with self._wake:
                self._wake.wait_for(lambda: self._closed or self._next is not None)
                if self._closed:
                    return
                data, self._next = self._next, None
            try:
                self._winsound_play(data)
            except (OSError, RuntimeError):
                continue

    def play(self, name):
        if not self.enabled or self._closed:
            return False
        try:
            data = self.wav(name)
            if self._player is not None:
                self._player(data)
                self.played.append(name)
            else:
                with self._wake:
                    self._next = data
                    if self._thread is None:
                        self._thread = threading.Thread(target=self._run, name="holo-sound", daemon=True)
                        self._thread.start()
                    self._wake.notify()
            return True
        except Exception:
            return False

    def stop(self):
        # The sound already in progress is at most 400 ms; clear any waiting sound.
        with self._wake:
            self._next = None

    def close(self):
        with self._wake:
            self._closed = True
            self._next = None
            self._wake.notify()
        self._cache.clear()
