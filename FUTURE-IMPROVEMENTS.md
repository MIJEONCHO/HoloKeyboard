# Future improvements · HoloKeyboard · AI Companion Lab

Recorded for later releases. None of these is part of V1.

## Automatic password detection for the key glow
- **V1 behavior:** the key glow is stopped only by the manual **Input Lock**. With Input Lock OFF, pressed keys may glow in any program, including while a password is typed. This is documented in the user guide and the privacy note. HoloKeyboard does not read text from other programs; the one-line preview is composed from the keys and is hidden for password and unconfirmed fields.
- **Idea:** detect password fields automatically and hide the glow there, without ever opening the glow on a field that might hold a secret (fail-closed).
- **What was learned (measured on Windows with Office 2010/2016 and Hancom Office 2020):**
  - Raw Input reception and focus detection work in every tested program; the stop was only in the field-confirmation step.
  - Word, Notepad and browsers report a text field through UI Automation or Win32. Excel cell editing, PowerPoint text boxes and the Hancom Hangul body are plain panes for UI Automation, so a text field cannot be confirmed there.
  - Excel (cell selection and editing) and the Hancom body can be confirmed through the program's own accessibility report (MSAA role text, no protected state; a selected spreadsheet cell next to Excel's cell editor). PowerPoint text boxes are not reported at all.
- **Per-program handling** is needed for such programs (spreadsheet, presentation and word-processor surfaces) and must rest on evidence the program itself reports, not on window class names alone. Password dialogs of those programs must stay blocked.
- **Open decision:** whether an opt-in setting "glow in unconfirmed fields" is acceptable.

## Korean/English indicator in Hancom Hangul
Hancom Hangul can use an internal layout whose state Windows does not expose. V1 shows IME ? until it can verify the mode. A reliable read-only source for Hancom's internal state remains an open question.

## V1.1 candidates found in the final audit
- Microsoft Publisher: the one-line preview is not supported in V1.
- Clicking a top-bar button or menu of the HUD leaves no foreground window; the user has to click the editor again (also in earlier test builds). The on-screen keys use a separate non-activating window.
- The bottom-line check trusts what each program reports. A custom-drawn password box reported as an ordinary pane or edit control is not recognised.
- Hancom Hangul versions other than 2010, and Hancom form-object password boxes inside a document, are not verified.

## Other open items
- Signed executable (SmartScreen), real tablet touch, Japanese/Chinese IME composition, and more programs (Office 365, Firefox, other Electron apps) need verification.
