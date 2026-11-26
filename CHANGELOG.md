# Release notes · HoloKeyboard · AI Companion Lab

## 1.0.0 (V1)

- Windows on-screen keyboard HUD with a glow style. Compact (57 keys) and Full (104 keys) layouts, sticky one-shot modifiers, function keys, arrows and numpad.
- Physical-key mirror (Real-time / Last Key), Caps Lock and Korean/English indicators, language profiles for the Windows layouts and IMEs installed on the PC. The indicator shows IME ? when the current mode cannot be verified.
- One-line preview composed locally from the keys you press. HoloKeyboard does not read the text of other programs. Typing Auto/EN/KR applies only when the Windows mode cannot be verified.
- The preview is hidden for password fields Windows reports and for fields it cannot confirm. A focused element that is only a whole window is not accepted as a text field. The Hancom Hangul document body is recognised and its password setup dialog stays hidden (checked with Hangul 2010).
- Input Lock (manual): ON clears and stops the key glow and the preview. There is no automatic password detection for the key glow. Typed text is never stored, logged or sent anywhere.
- Hover tooltips, English/Korean interface (default English), help window, taskbar button and icon.
- Typing Practice with an embedded keyboard, speed levels, progress LEDs, optional voice and sound effects, and eight original texts (ko/en/zh/ja). Personal story files (`.json`) are read from `%LOCALAPPDATA%\AI Companion Lab\HoloKeyboard\stories` (see the user guide).
- Settings: Keyboard Diagnostics, About, Donate (optional supporter styles; the blue style and all core features are free).
- Windows x64 package built with PyInstaller 6.22.0 on Python 3.13.17. Not code-signed.
- Fixed: the Settings (⚙) menu could be partly covered by the top bar on the first click.
- Third-party notices: `THIRD_PARTY_NOTICES.md` and the `licenses/` folder.
