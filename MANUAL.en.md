# HoloKeyboard V1 User Guide · AI Companion Lab

1. Extract the Windows x64 ZIP and double-click `HoloKeyboard.exe`. Keep `_internal` beside the EXE. If Windows reports a missing VC runtime, use the [official x64 redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). In a source checkout use Python with Tcl/Tk. The program opens without a Command Prompt.
2. Use the top bar or empty portions of the expanded menu to drag the HUD. Drag the bottom-right grip or use Size to scale the keyboard. Menu expands the controls. Settings lets you switch between Compact (57 keys) and Full (104).
3. Mirror ON shows supported physical keys. Real-time gives a 240 ms afterglow and Last Key keeps the last ordinary key until another. Caps Lock and confirmed Korean/English states have their own indicators. Click the on-screen keys to type into the focused app when Windows accepts input.
4. The bottom line builds typing locally. If the Windows mode is unknown, select Typing EN or KR for the local display. This does not change Windows or field protection. Password and unverified fields are blocked. Input OFF clears the line. Input Lock clears it and the key glow. Turn Input Lock on before typing secrets.
5. The HUD refreshes keyboard mode after a Hangul/English key press or when you return to an editor. It shows KR or EN when it can verify the current mode, and IME ? when it cannot, including with some Hancom Hangul layouts. UI EN/UI KR changes the interface language. Use Win+Space if needed to select an installed Windows input profile. See ? for availability.
6. Choose Typing Practice in the expanded menu. Select a language and a story, then type in the input field with the matching Windows IME. Pace controls, Voice, Sound and Replay are in the same window. Voice requires a matching Windows voice. The package bundles eight original texts, two per language: a short new story and a guide to adding your own story (see [Content rights](CONTENT-RIGHTS.md)). Your own story files are explained in "Add your own story" below.
7. Settings → Keyboard Diagnostics opens a disposable typing test. Settings → About displays the product and developer. Settings → Donate opens voluntary supporter options. Minimize and close are on the right of the HUD.

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

## Add your own story (personal use)

Typing Practice reads story files (`.json`) from two places: the bundled stories inside the app and your **personal folder**. You never need an editor or any tool besides Notepad.

**1. Find or create the personal folder.** Paste this into the File Explorer address bar and press Enter. Create the folders `AI Companion Lab`, `HoloKeyboard` and `stories` if they do not exist yet:

```
%LOCALAPPDATA%\AI Companion Lab\HoloKeyboard\stories
```

**2. Create the file.** Copy `examples\my-story.example.en.json` (or `.ko.json`) from the ZIP into that folder and rename it, for example `my-first-story.json`. Open it in Notepad.

**3. Edit it.** The file structure is:

```json
{
  "id": "user-en-001",
  "lang": "en",
  "title": "My First Story",
  "title_en": "My First Story",
  "sentences": [
    "Write one short sentence on each line of this list.",
    "Keep every sentence to about sixty characters or fewer.",
    "The last sentence has no comma after it."
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | A **unique** text ID such as `user-en-001`. Use the prefix `user-` and never reuse an ID. If an ID is already taken (bundled stories are read first), the second file is ignored. |
| `lang` | yes | `ko`, `en`, `zh` or `ja`. This selects the language button and the key hints (hints exist for `ko` and `en`). |
| `title` | no | Name shown when the interface language is Korean. |
| `title_en` | no | Name shown when the interface language is English. If one title is missing the other is used. |
| `sentences` | yes | A list of text lines in quotes, separated by commas. Recommended 8 to 12 lines, at most about 60 characters each for `ko`/`en`, 30 for `zh`, 36 for `ja`. |

Other fields (for example `source` or `notes`) are allowed and ignored. A file may also contain a list `[ {...}, {...} ]` of several stories.

**4. Save as UTF-8.** In Notepad choose File → Save As → Encoding **UTF-8**. The name must end in `.json` (turn off "Hide extensions" if you get `.json.txt`). A file larger than 256 KB is ignored.

**5. Load it.** Close the Typing Practice window and open it again (Typing Practice button). The story appears in the story list of its language. Nothing needs to be restarted.

**If the story does not appear:** the loader skips a file silently when the JSON is invalid (a missing comma or quote is the usual cause), when `id`, `lang` or `sentences` is missing or wrong, when the ID is already used, or when the file is too large. Check these, save again as UTF-8 and reopen the window. Chinese and Japanese practice ignore spaces and punctuation; Korean and English compare exactly.

**Rights.** Stories you write yourself are yours; using them privately on your own PC is fine. Text written by other people (books, songs, websites, translations) stays under their copyright. Typing it in for your own practice is a private matter, but **sharing or redistributing it, including in a repository or package, needs the rights holder's permission.** The project does not review personal files, and never reads or sends them anywhere. The bundled texts and their license are described in [Content rights](CONTENT-RIGHTS.md).

HoloKeyboard is by **AI Companion Lab**. The shared funding route is [AI World Portal on Ko-fi](https://ko-fi.com/aiportal). No sign-in or online verification is required. See [Privacy and support](PRIVACY-SUPPORT.md).

## Donations

> Donations are entirely voluntary.  
> We trust and respect every user's personal choice.  
> We hope HoloKeyboard makes your everyday life a little better.
