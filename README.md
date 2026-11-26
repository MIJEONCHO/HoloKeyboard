# HoloKeyboard V1 · AI Companion Lab

[한국어 README](README.ko.md)

HoloKeyboard is a Windows keyboard overlay with a Typing Practice window, by **AI Companion Lab**. The blue style and all core features are free. The full palette and border-width adjustment are optional supporter styles.

## Passwords and sensitive input — read this first

- **Turn Input Lock ON before you type a password or anything secret** (Settings → Input Lock, or the Input Lock button in the expanded menu). ON clears and stops both the key glow and the bottom line. Turn it OFF when you are done.
- **With Input Lock OFF the keys glow in every program, including while you type a password.** Anyone watching your screen, a screen share or a recording can see which keys you press.
- The bottom line has a separate automatic check: it is hidden for password fields that Windows reports as passwords, and for fields it cannot confirm. This depends on what the other program tells Windows. A program that draws its own password box and does not report it may not be recognised, so **do not rely on the automatic check; use Input Lock.**
- Typed text is never saved, logged, copied or sent anywhere. HoloKeyboard does not read the text of other programs' fields. The bottom line (up to 120 characters) is built in memory from the keys and may differ from your document.

## Hancom Hangul (Korean word processor)

- To use the Windows Korean IME: in Hancom Hangul press **Alt+F2** (입력기 환경 설정 → 글자판 바꾸기) and set **현재 글자판** and **제1 글자판** to **윈도우 입력기** (Windows input method).
- Hancom handles keyboard input in its own way and does not give Windows the usual field information. For privacy the bottom line is shown only where HoloKeyboard can identify the document body (checked with Hangul 2010). The password setup dialog was checked: it shows "Protected input — hidden". Other Hancom dialogs, versions or editing areas were not all checked and may stay hidden; use Input Lock for any secret.
- If the indicator shows IME ?, press the Han/Eng key once, or choose Typing EN or KR for the bottom line.
- Password-masked input boxes placed inside a Hancom document (form objects) are not told apart from the body. Turn Input Lock ON for them.
- After you use a top-bar button or menu of the HUD, click your editor again before typing. Clicking the on-screen keys does not need this.

## Code signing and SmartScreen

The executable is **not code-signed**. Windows SmartScreen may show "Windows protected your PC", and Smart App Control or company policy may block it. Download only from this project's GitHub Releases page and compare the ZIP's SHA-256 with the published value (`Get-FileHash <zip> -Algorithm SHA256`). If it matches and you trust the source, choose **More info → Run anyway**. Do not turn Windows protection features off for this program.

## Run the Windows x64 package

Extract the complete Windows ZIP and open `HoloKeyboard.exe`. Keep its `_internal` folder beside it. This unsigned build was tested on Windows 11 x64. If the Visual C++ x64 runtime is missing, use Microsoft's [official installer](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). The source can be run on Windows with Python 3.13 x64 and Tcl/Tk by running `python -B src/holo_keyboard_hud.py`.

- [English manual](MANUAL.en.md)
- [한국어 사용설명서](MANUAL.ko.md)
- [Privacy and support scope](PRIVACY-SUPPORT.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Content list](CONTENT-LIST.md) and [Content rights](CONTENT-RIGHTS.md)
- [Add your own story](MANUAL.en.md#add-your-own-story-personal-use) (JSON examples in `examples/`)
- [Release notes](CHANGELOG.md) and [Future improvements](FUTURE-IMPROVEMENTS.md)
- [License (MIT)](LICENSE)

## Support

> Donations are entirely voluntary.  
> We trust and respect every user's personal choice.  
> We hope HoloKeyboard makes your everyday life a little better.

[Donate through AI World Portal on Ko-fi](https://ko-fi.com/aiportal). AI World Portal is the shared funding platform. HoloKeyboard is developed and branded by AI Companion Lab.

Open Settings → Donate and confirm your contribution if you wish to activate the optional styles. The app saves the checkbox locally. It has no account, payment verification or activation server.

## License

The first-party source code (`src/`) and documentation are under the **MIT License** (`LICENSE`). The license does **not** cover: third-party software in the ZIP (Python, Tcl/Tk, zlib, libffi, bzip2, libmpdec, PyInstaller bootloader; each keeps its own license, see [Third-party notices](THIRD_PARTY_NOTICES.md) and `licenses/`); the names and logos "AI Companion Lab", "HoloKeyboard" and "AI World Portal"; and any content you add yourself. The eight bundled typing-practice texts are original texts written for this project and are offered under the MIT License (see [Content rights](CONTENT-RIGHTS.md)).

## Status

- Typing Practice bundles eight original texts (a short new story and an "add your own story" guide in each of Korean, English, Chinese and Japanese). You can add personal story files as JSON; see the manual. The 20 earlier retellings are not included (see [Content list](CONTENT-LIST.md)).
- Windows 11 x64 only (tested). The executable is not code-signed.
