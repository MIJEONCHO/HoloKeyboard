"""Offline Windows text-to-speech through ONE persistent PowerShell child.

The child hosts System.Speech.Synthesis.SpeechSynthesizer. Commands go in as
base64(UTF-8 JSON) lines on stdin, answers come back the same way on stdout, so
spoken text never appears on a command line or on disk. Nothing is installed
and no Windows setting is changed.
"""
import atexit
import base64
import ctypes
import json
import os
import subprocess
import threading
import weakref
from ctypes import wintypes as w

# Preferred voice cultures per story language (first exact match, then prefix).
LANG_PREFIX = {"ko": "ko", "en": "en", "zh": "zh", "ja": "ja"}
LANG_PREFERRED = {"ko": ("ko-KR",), "en": ("en-US", "en-GB"), "zh": ("zh-CN", "zh-TW", "zh-HK"), "ja": ("ja-JP",)}

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$syn = New-Object System.Speech.Synthesis.SpeechSynthesizer
function Send($o) {
  $j = $o | ConvertTo-Json -Compress -Depth 5
  [Console]::Out.WriteLine([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($j)))
  [Console]::Out.Flush()
}
Send @{ ev = 'ready' }
$run = $true
while ($run) {
  $line = [Console]::In.ReadLine()
  if ($null -eq $line) { break }
  $line = $line.Trim()
  if ($line -eq '') { continue }
  try {
    $j = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($line)) | ConvertFrom-Json
    if ($j.cmd -eq 'voices') {
      $v = @()
      foreach ($x in $syn.GetInstalledVoices()) {
        if ($x.Enabled) { $v += @{ name = $x.VoiceInfo.Name; culture = $x.VoiceInfo.Culture.Name } }
      }
      Send @{ ev = 'voices'; voices = $v }
    } elseif ($j.cmd -eq 'speak') {
      $chosen = $null
      foreach ($x in $syn.GetInstalledVoices()) {
        if (-not $x.Enabled) { continue }
        if ($j.voice -and $x.VoiceInfo.Name -eq $j.voice) { $chosen = $x.VoiceInfo.Name; break }
        if (-not $chosen -and $j.prefix -and $x.VoiceInfo.Culture.Name.StartsWith([string]$j.prefix, [StringComparison]::OrdinalIgnoreCase)) { $chosen = $x.VoiceInfo.Name }
      }
      if (-not $chosen) { Send @{ ev = 'novoice'; prefix = $j.prefix } }
      else {
        $syn.SelectVoice($chosen)
        $syn.Rate = [int]$j.rate
        $syn.Volume = [int]$j.volume
        $syn.SpeakAsyncCancelAll()
        [void]$syn.SpeakAsync([string]$j.text)
        Send @{ ev = 'speaking'; voice = $chosen }
      }
    } elseif ($j.cmd -eq 'cancel') {
      $syn.SpeakAsyncCancelAll()
      Send @{ ev = 'cancelled' }
    } elseif ($j.cmd -eq 'quit') {
      $run = $false
    }
  } catch {
    Send @{ ev = 'error'; message = [string]$_.Exception.Message }
  }
}
try { $syn.SpeakAsyncCancelAll(); $syn.Dispose() } catch { }
"""


def pick_voice(voices, lang):
    """Choose an installed voice name for a story language, or None."""
    prefix = LANG_PREFIX.get(lang)
    if not prefix or not voices:
        return None
    by_culture = [(str(v.get("culture", "")).lower(), v.get("name")) for v in voices if v.get("name")]
    for want in LANG_PREFERRED.get(lang, ()):
        for culture, name in by_culture:
            if culture == want.lower():
                return name
    for culture, name in by_culture:
        if culture.startswith(prefix):
            return name
    return None


def _ps_path():
    root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return candidate if os.path.exists(candidate) else "powershell.exe"


def _encode(obj):
    return base64.b64encode(json.dumps(obj, ensure_ascii=True).encode("utf-8")).decode("ascii") + "\n"


def _decode(line):
    return json.loads(base64.b64decode(line.strip()).decode("utf-8"))


class _JobObject:
    """Windows job that kills the child when the parent process dies."""

    def __init__(self):
        self.handle = None
        try:
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.CreateJobObjectW.restype = w.HANDLE
            k.CreateJobObjectW.argtypes = (w.LPVOID, w.LPCWSTR)
            k.SetInformationJobObject.argtypes = (w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD)
            k.AssignProcessToJobObject.argtypes = (w.HANDLE, w.HANDLE)
            k.CloseHandle.argtypes = (w.HANDLE,)

            class BASIC(ctypes.Structure):
                _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64), ("LimitFlags", w.DWORD),
                            ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", w.DWORD),
                            ("f", ctypes.c_size_t), ("g", w.DWORD), ("h", w.DWORD)]

            class EXTENDED(ctypes.Structure):
                _fields_ = [("Basic", BASIC), ("io", ctypes.c_uint64 * 6), ("p1", ctypes.c_size_t),
                            ("p2", ctypes.c_size_t), ("p3", ctypes.c_size_t), ("p4", ctypes.c_size_t)]

            self._k, self._ext = k, EXTENDED
            job = k.CreateJobObjectW(None, None)
            if job:
                info = EXTENDED()
                info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                if k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
                    self.handle = job
                else:
                    k.CloseHandle(job)
        except Exception:
            self.handle = None

    def assign(self, process):
        if not self.handle:
            return False
        try:
            return bool(self._k.AssignProcessToJobObject(self.handle, int(process._handle)))
        except Exception:
            return False

    def close(self):
        if self.handle:
            try:
                self._k.CloseHandle(self.handle)
            except Exception:
                pass
            self.handle = None


_LIVE = weakref.WeakSet()


@atexit.register
def _kill_all():
    for tts in list(_LIVE):
        tts.close()


class TTS:
    """Lazy persistent speech child. Safe to call from the Tk thread."""

    def __init__(self, script=SCRIPT):
        self._script = script
        self._proc = None
        self._job = None
        self._reader = None
        self._lock = threading.Lock()
        self._voices = None            # None = unknown yet, [] = none installed
        self.ready = threading.Event()
        self.voices_event = threading.Event()
        self.speaking = threading.Event()
        self.novoice = threading.Event()
        self.last_event = None
        self.events = []               # event names only, never text
        self.speak_voice = None
        self.dead = False

    # -- lifecycle ---------------------------------------------------------
    @property
    def started(self):
        return self._proc is not None

    def start(self):
        if self._proc is not None or self.dead:
            return
        script = base64.b64encode(self._script.encode("utf-16-le")).decode("ascii")
        flags = 0x08000000  # CREATE_NO_WINDOW
        try:
            self._proc = subprocess.Popen(
                [_ps_path(), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-EncodedCommand", script],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=flags)
        except OSError:
            self.dead = True
            self._voices = []
            self.voices_event.set()
            return
        self._job = _JobObject()
        self._job.assign(self._proc)
        _LIVE.add(self)
        self._reader = threading.Thread(target=self._read_loop, name="tts-reader", daemon=True)
        self._reader.start()
        self._send({"cmd": "voices"})

    def _read_loop(self):
        proc = self._proc
        try:
            for raw in proc.stdout:
                try:
                    msg = _decode(raw)
                except Exception:
                    continue
                self._handle(msg)
        except Exception:
            pass
        finally:
            self.dead = True
            if self._voices is None:
                self._voices = []
            self.voices_event.set()

    def _handle(self, msg):
        ev = msg.get("ev")
        self.last_event = ev
        self.events.append(ev)
        if ev == "ready":
            self.ready.set()
        elif ev == "voices":
            data = msg.get("voices") or []
            if isinstance(data, dict):
                data = [data]
            self._voices = [{"name": v.get("name"), "culture": v.get("culture")} for v in data]
            self.voices_event.set()
        elif ev == "speaking":
            self.speak_voice = msg.get("voice")
            self.speaking.set()
        elif ev == "novoice":
            self.novoice.set()

    def _send(self, obj):
        proc = self._proc
        if proc is None or proc.stdin is None or self.dead:
            return False
        try:
            with self._lock:
                proc.stdin.write(_encode(obj).encode("ascii"))
                proc.stdin.flush()
            return True
        except (OSError, ValueError):
            self.dead = True
            return False

    # -- voices ------------------------------------------------------------
    @property
    def voices(self):
        return self._voices

    def set_voices_for_test(self, voices):
        """Inject an installed-voice list (tests: 'no voice installed' path)."""
        self._voices = list(voices)
        self.voices_event.set()

    def has_voice(self, lang):
        """True/False once the voice list is known, None while still unknown."""
        if self._voices is None:
            return None
        return pick_voice(self._voices, lang) is not None

    # -- speech ------------------------------------------------------------
    def speak(self, text, lang, rate=0, volume=100):
        if not text:
            return False
        voice = None
        if self._voices is not None:
            voice = pick_voice(self._voices, lang)
            if voice is None:
                return False          # no voice installed: nothing is spawned or sent
        self.start()
        rate = max(-10, min(10, int(rate)))
        volume = max(0, min(100, int(volume)))
        return self._send({"cmd": "speak", "text": text, "voice": voice,
                           "prefix": LANG_PREFIX.get(lang, ""), "rate": rate, "volume": volume})

    def cancel(self):
        if self._proc is not None:
            self._send({"cmd": "cancel"})

    def close(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        self.dead = True
        try:
            proc.stdin.write(_encode({"cmd": "quit"}).encode("ascii"))
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=2.0)
            except Exception:
                pass
        if self._job:
            self._job.close()
            self._job = None
        try:
            proc.stdout.close()
        except Exception:
            pass
        _LIVE.discard(self)

    @property
    def process_alive(self):
        return self._proc is not None and self._proc.poll() is None
