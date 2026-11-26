"""Story loader: reads DEV\\stories\\*.json, tolerant of missing or bad files."""
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

LANG_ORDER = ("ko", "en", "zh", "ja")
# Set to True in a release build, or export HOLO_RELEASE_ONLY=1.
RELEASE_ONLY = bool(getattr(sys, "frozen", False))


def release_only_enabled():
    return RELEASE_ONLY or os.environ.get("HOLO_RELEASE_ONLY", "").strip() in ("1", "true", "yes")


@dataclass(frozen=True)
class Story:
    id: str
    lang: str
    title: str
    title_en: str
    sentences: tuple
    rights_status: str = "unverified"
    release: bool = False
    source: dict = None
    notes: str = ""

    def display_title(self, ui_language="EN"):
        if ui_language == "KO":
            return self.title or self.title_en
        return self.title_en or self.title


def default_dir():
    return Path(__file__).resolve().parent.parent / "stories"


def _parse(item):
    if not isinstance(item, dict):
        return None
    lang = str(item.get("lang", "")).lower()
    sentences = item.get("sentences")
    if lang not in LANG_ORDER or not isinstance(sentences, list):
        return None
    clean = tuple(s.strip() for s in sentences if isinstance(s, str) and s.strip())
    if not clean:
        return None
    story_id = str(item.get("id") or "")
    if not story_id:
        return None
    return Story(
        id=story_id, lang=lang, title=str(item.get("title") or ""),
        title_en=str(item.get("title_en") or ""), sentences=clean,
        rights_status=str(item.get("rights_status") or "unverified"),
        release=bool(item.get("release", False)),
        source=item.get("source") if isinstance(item.get("source"), dict) else {},
        notes=str(item.get("notes") or ""),
    )


MAX_FILE_BYTES = 256 * 1024   # a story file larger than this is ignored (personal files included)
_DEFAULT = object()


def user_dir():
    """Personal stories folder: %LOCALAPPDATA%\\AI Companion Lab\\HoloKeyboard\\stories."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "AI Companion Lab" / "HoloKeyboard" / "stories"


def _read_folder(folder, release_only, seen, found):
    try:
        files = sorted(folder.glob("*.json"))
    except OSError:
        return
    for path in files:
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            with open(path, "r", encoding="utf-8-sig") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            story = _parse(item)
            if story is None or story.id in seen:
                continue
            if release_only and not (story.release and story.rights_status == "cleared"):
                continue
            seen.add(story.id)
            found.append(story)


def load_stories(directory=None, release_only=None, user_directory=_DEFAULT):
    """Return stories sorted by language then id. Never raises.

    The bundled folder is read first and, in a release build, only rights-cleared stories pass.
    Then the personal folder (``user_dir()``, or ``user_directory``; ``None`` = skip) is read: the
    user's own files are for personal use on this PC and are not release-gated. An id that is
    already taken (bundled first) is ignored, so a personal file cannot replace a bundled story.
    Unreadable, oversized or malformed files are skipped silently.
    """
    if release_only is None:
        release_only = release_only_enabled()
    folder = Path(directory) if directory is not None else default_dir()
    if user_directory is _DEFAULT:
        user_directory = user_dir() if directory is None else None
    found, seen = [], set()
    _read_folder(folder, release_only, seen, found)
    if user_directory is not None:
        _read_folder(Path(user_directory), False, seen, found)
    found.sort(key=lambda s: (LANG_ORDER.index(s.lang), s.id))
    return found


def languages(stories):
    present = {s.lang for s in stories}
    return [lang for lang in LANG_ORDER if lang in present]
