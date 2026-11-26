# Content list · HoloKeyboard V1 · AI Companion Lab

This list names everything in the public repository and in the Windows x64 ZIP, and what is deliberately not included.

## Included

| Item | Where | Rights / license status |
|---|---|---|
| HoloKeyboard source code (Python, Tkinter, ctypes) | `src/` | First-party. MIT License (`LICENSE`). Copyright (c) 2026 AI Companion Lab. |
| README, user guides (EN/KO), privacy and support scope, release notes | repository root | First-party documentation, MIT License. Names and logos are not licensed. |
| `HoloKeyboard.exe` and `_internal` runtime (ZIP only) | Windows x64 ZIP | Python 3.13.17, Tcl/Tk 8.6.15, zlib, libffi, bzip2 and libmpdec, PyInstaller bootloader. Notices in `THIRD_PARTY_NOTICES.md` and `licenses/`. |
| Third-party license texts | `licenses/` (repository and ZIP) | CPython, Tcl/Tk, zlib, libmpdec (mpdecimal). |
| Logo | none | No logo file is included. The brand names are not covered by the MIT License. |
| 8 typing-practice texts: `ko-n01` `en-n01` `zh-n01` `ja-n01` (new short stories) and `ko-g01` `en-g01` `zh-g01` `ja-g01` (how to add your own story) | `src/stories/` (repository), `_internal/stories/` (ZIP) | Original texts written for this project by Claude (an AI model) at the owner's request; offered under the MIT License. Details, authorship and limits: `CONTENT-RIGHTS.md`. |
| Story file examples (`my-story.example.en.json`, `my-story.example.ko.json`) | `examples/` | First-party, MIT License. Copy them to your personal stories folder (see the user guide). |

Not redistributed: the Microsoft Visual C++ runtime, Windows components and installed Windows voices (see `THIRD_PARTY_NOTICES.md`).

## Not included (deliberately)

- **The 20 earlier story retellings.** The retellings of traditional tales prepared during development do not have a confirmed author, rights holder and license for their wording, so they are excluded from the public repository and ZIP. They are kept privately by the project owner.
- **Anyone's personal story files.** Files you add to your personal folder stay on your PC and are never part of the package.
- Internal hand-off documents, development test material and development-machine paths.
- Audio, voices, fonts, images and illustrations from outside sources: none are used.

## Verification

SHA-256 of the ZIP is listed in `HoloKeyboard-V1-SHA256SUMS.txt` beside the ZIP.
