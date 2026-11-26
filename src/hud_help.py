"""Offline UI labels and help. UI language is unrelated to key legends."""
import tkinter as tk
from tkinter import ttk
from hud_i18n import controls_help
from input_profiles import PROFILES
from product import BRAND

EN = {
    "미러": "Mirror", "메뉴": "Menu", "투명": "Opacity", "두께": "Width", "크기": "Size",
    "입력표시": "Input", "표시": "View", "배열": "Layout", "잠금": "LOCK",
    "글자색": "Text color", "키 입력": "Keystrokes",
    "조합": "Typing", "입력 보호 확인 중": "Checking input protection",
    "키 입력 대기": "Waiting for keystrokes", "키 입력 모드 미확인": "Keystroke mode unverified",
    "자동": "Auto",
    "검정": "Black", "흰색": "White", "테마색": "Theme",
    
    "입력 잠금": "Input Lock", "입력 잠김": "Input locked",
    "입력 표시 차단": "Protected input — hidden", "IME 조합 중": "IME composing",
    "Windows 입력 제한": "Windows input blocked",
    "실시간": "Real-time", "마지막 키": "Last Key", "도움말": "Help",
    "키보드 진단": "Keyboard Diagnostics",
    "대상 창 없음": "No input target", "활성": "Active",
    "Windows에 없음": "Unavailable", "확인 불가": "Unconfirmed",
    "전환 확인 중": "Switching…", "프로필 확인 불가": "Profile unknown",
    "Compact 배열로 전환": "Switch to Compact layout", "Full 배열로 전환": "Switch to Full layout",
    "동화 타자 연습": "Story Typing", "타자 연습": "Typing Practice",
    "타자 모듈 없음": "Typing: n/a", "타자 모듈 오류": "Typing: error",
    "Ctrl+Alt+Del 불가": "Ctrl+Alt+Del: Windows only",
    "입력표시 OFF": "Input is OFF",
}
GUIDE = {
    "EN": """HoloKeyboard Help

Passwords (read first)
Turn Input Lock ON before typing a password or anything secret. With Input Lock OFF the keys glow in every program, including while you type a password. The bottom line is also hidden for password fields that Windows reports and for fields it cannot confirm, but a program that draws its own password box may not be recognised, so rely on Input Lock. Typed text is never saved, logged or sent.

Hancom Hangul
For the Windows IME press Alt+F2 in Hangul (입력기 환경 설정 → 글자판 바꾸기) and set 현재 글자판 and 제1 글자판 to 윈도우 입력기. Hancom processes input in its own way; for privacy the bottom line is shown only in the identified document body (checked with Hangul 2010). The password setup dialog was checked and stays hidden. Password boxes placed inside a document are not told apart from the body: use Input Lock.

After using a top-bar button or menu, click your editor again before typing.

Start and close
HoloKeyboard.exe opens the keyboard without a Command Prompt. The gear (⚙), second button from the left of the top bar, opens Settings with Keyboard Diagnostics, Switch to Full/Compact layout, Story Typing, Input Lock, Donate and About. Close diagnostics or its × closes the diagnostic window only. The HUD's × exits HoloKeyboard. The far-right − minimizes it. With the menu expanded, the Typing Practice button in the option row (next to Input and Text color) opens the same practice as Story Typing.

Move and resize
Drag any unused area of the top bar or expanded menu. Menu expands or collapses the settings. Use the Size slider or drag the bottom-right grip. Both keep the keyboard's proportions. Opacity affects the keyboard, not the menu. Width changes the key outlines. The colored dots choose a key theme.

Language and keys
UI EN / UI KR switches the program's display language only (menus, settings, help, tooltips, notices and the typing-practice screens; English by default); it never changes the keyboard input language. The language buttons request Windows profiles for the focused app. When a country layout is selected (for example KR, JP or CN) that button and EN are both lit; the language you are really typing in right now (follows the real Hangul/English key) is drawn brighter than the merely selected one, and unavailable profiles are gray. EN can be a companion indicator even when a separate US QWERTY profile is unavailable. Keys follow the layout Windows reports. Use Win+Space for IME selection or when the focused app does not accept a switch. Unavailable means Windows did not expose the required profile to HoloKeyboard. IME ? means that the mode could not be read. When the mode is known, the Korean/English key is lit (full glow = KR, dim glow = EN), shows KR or EN, the letter keys show Hangul or Latin, and the space bar reads KR · Space or EN · Space, all from the same real Windows state. Caps Lock ON keeps the Caps key glowing in a fixed amber (hot pink on the Gold and Lime themes), clearly different from the normal press glow, until Caps Lock is switched off, from any program. Windows handles actual key input and IME composition. The existing bottom modifier key acts as AltGr on confirmed layouts that expose it, or as Korean/English on a Korean profile.

IME status limits
KR/EN is shown when HoloKeyboard can verify the current mode of the focused editor; programs and IMEs differ. When it cannot, it shows IME ? instead of guessing. The first moment after switching windows can show IME ?.

Layouts
Compact (default) is the 57-key keyboard. Full adds the Esc/F1-F12 row, PrtSc/ScrLk, Insert/Home/PgUp/Delete/End/PgDn, four arrows and the numeric keypad. Switch only from the gear menu (Switch to Full layout / Switch to Compact layout); the window grows to fit and every setting keeps working.

Modifier keys
Shift, Ctrl, Alt and Win are sticky one-shot keys: click one (it stays lit), then click the key to combine, for example Ctrl and then C. The modifier clears after that key, when the target window changes, or when you click it again. A modifier alone is never sent. Ctrl+Alt+Del is reserved by Windows and cannot be sent by any program; HoloKeyboard shows a notice instead.

Mirror and glow
Mirror enables the display of keys pressed on your hardware keyboard. Real-time highlights a physical key during the press and for about 240 ms after release. Last Key keeps the most recent ordinary key lit until the next ordinary key. These modes do not store a typing history. Turn Mirror off when you do not want physical keystrokes visible.

Mirror lock
Input Lock (manual). The mirror sees keys system-wide. HoloKeyboard V1 does NOT detect password fields for the key glow: with Input Lock OFF, the keys you press light up in any program, including while you type a password, and a screen share or recording would show which keys were pressed. Turn Input Lock ON before typing a password (Settings, Input Lock). While Input Lock is ON every key glow and the Last Key memory are cleared, the status text shows LOCK: input lock, and clicks on the HUD still type but are not echoed. Local keystroke display blocks password and unverified fields.

Click protection for Korean input
While a Korean IME is active and the pointer is over a key, a short-lived mouse hook keeps composition from breaking. It is removed when the pointer leaves, on minimize or close, and a click that never completes is released after 1.5 seconds.

Typing practice (Story Typing)
Choose Typing Practice from the expanded menu or Story Typing from Settings. Move the window by its title bar and drag ↘ to resize the panel and keyboard together. Choose a story and type in its field. Windows controls the actual input language. If prompted, choose a matching profile with Win+Space or the Korean-English key. The keyboard is restored when you close the practice window.

Automatic input preview and Input Lock
The lower line is composed locally. If the Windows mode cannot be verified, choose Typing EN or KR. This setting affects the preview only. HoloKeyboard does not read the target field. Password and unverified fields are blocked. Input Lock ON clears the line and key glow. Input OFF clears and hides the line.

Input preview and test fields
Input ON/OFF controls the local display. Text color changes the lettering.

Keyboard Diagnostics
1. Registered input checks the hardware mirror and the input preview. Enable Mirror and Input, click the top field, then hold A for a second and release it. Try Shift separately. The held-key status and key highlight should change as you press and release.
2. Password — blocked checks that the HUD never reads password text. Type dummy text in the middle field. The field masks the characters and the HUD does not display them (key glow is controlled only by Input Lock).
3. Unregistered — blocked checks permission. Type dummy text in the bottom field. The field shows your text normally, while the HUD leaves the value hidden.
Use sample text only. Closing diagnostics discards the sample text.

Tablet touch is not verified on hardware.

Keyboard Compatibility & Customization
HoloKeyboard is designed around standard Windows keyboard layouts.
If you require additional keyboard layouts, special keys, or customized features, please contact us.
• Free requests: Reviewed and prioritized based on user demand.
• Paid customization: Prompt review and priority development, subject to feasibility and agreed delivery time.
• Bug fixes for officially supported features are provided free of charge.
We welcome your suggestions to improve HoloKeyboard.
""",
    "KO": """HoloKeyboard 도움말

비밀번호 (먼저 읽기)
비밀번호나 비밀 내용을 입력하기 전에 입력 잠금을 ON으로 하세요. 입력 잠금이 OFF이면 비밀번호를 입력할 때를 포함해 모든 프로그램에서 키가 발광합니다. 하단 한 줄은 Windows가 비밀번호라고 알려 주는 칸과 확인할 수 없는 칸에서 숨기지만, 비밀번호 칸을 자체적으로 그리는 프로그램은 구별하지 못할 수 있으니 입력 잠금을 사용하세요. 입력한 내용은 저장·기록·전송하지 않습니다.

한컴 한글
Windows 입력기를 쓰려면 한글에서 Alt+F2(입력기 환경 설정 → 글자판 바꾸기)를 누르고 현재 글자판과 제1 글자판을 윈도우 입력기로 선택하세요. 한컴은 독자적인 방식으로 입력을 처리하므로, 개인정보 보호를 위해 하단 한 줄은 식별된 문서 본문에서만 표시합니다(한글 2010에서 확인). 암호 설정 대화상자에서 숨기는 것을 확인했습니다. 문서 안에 넣은 암호 입력 상자는 본문과 구별하지 못하므로 입력 잠금을 사용하세요.

상단 버튼이나 메뉴를 사용한 뒤에는 입력할 창을 다시 클릭하고 타자하세요.

실행과 종료
HoloKeyboard.exe는 명령 프롬프트 없이 키보드를 엽니다. ⚙(조작바 왼쪽에서 두 번째 버튼) 환경설정에는 키보드 진단, Full/Compact 배열 전환, 동화 타자 연습, 입력 잠금, 후원, 제품 정보가 있습니다. 키보드 진단은 필요할 때만 엽니다. 진단 닫기나 진단창의 ×는 진단창만 닫습니다. HUD의 ×는 프로그램을 종료하고, 맨 오른쪽 −는 최소화합니다. 메뉴를 펼치면 옵션 줄(입력표시와 글자색 옆)의 타자 연습 버튼이 동화 타자 연습과 같은 연습을 엽니다.

이동과 크기
상단 조작바나 펼친 메뉴의 빈 곳을 드래그하면 이동합니다. 메뉴 버튼은 설정을 펼치거나 접습니다. 크기 슬라이더나 오른쪽 아래 손잡이로 비율을 유지하면서 크기를 바꿉니다. 투명도는 키보드에, 두께는 키 테두리에 적용됩니다. 색 점은 키의 테마를 선택합니다.

언어와 상태
UI EN / UI KR는 프로그램 표시 언어(메뉴, 설정, 도움말, 툴팁, 알림, 타자 연습 화면)만 바꾸며 기본은 영어입니다. 자판 입력 언어는 바꾸지 않습니다. 국가 배열(KR, JP, CN 등)을 선택하면 그 버튼과 EN이 함께 켜지고, 지금 실제로 입력 중인 언어(실제 한/영 키를 따름)는 단순히 선택된 것보다 밝게 표시됩니다. 사용할 수 없는 프로필은 회색입니다. 별도 미국식 자판이 없어도 EN 동반 표시가 켜질 수 있습니다. 자판 버튼은 현재 입력 대상의 Windows 프로필 전환을 요청하고, 키 표시는 Windows가 보고한 배열을 따릅니다. IME를 선택하거나 대상 앱에서 전환이 되지 않을 때는 Win+Space를 사용하세요. 사용 불가는 Windows에서 해당 프로필이 프로그램에 노출되지 않았다는 뜻입니다. IME ?는 상태를 읽을 수 없다는 뜻입니다. 상태를 알 수 있으면 한/영 키가 켜지고(KR은 밝은 발광, EN은 어두운 발광) KR/EN 글자가 표시되며, 글자 키는 한글/영문으로, 스페이스는 KR · Space/EN · Space로 같은 실제 Windows 상태에 맞춰 함께 바뀝니다. Caps Lock이 켜져 있으면 Caps 키가 고정된 호박색(골드·라임 테마는 분홍)으로 계속 발광하며 일반 누름 발광과 확실히 구분됩니다. 다른 프로그램에서 껐다 켜도 따라갑니다. 실제 입력과 문자 조합은 Windows가 담당합니다. 하단 전환키는 확인된 배열에서 AltGr이 있을 때 AltGr, 한국어 프로필에서는 한/영으로 동작합니다.

IME 상태의 한계
포커스된 편집창의 현재 모드를 확인할 수 있을 때 KR/EN을 표시합니다. 프로그램과 IME마다 다릅니다. 확인할 수 없으면 추측하지 않고 IME ?로 표시합니다. 창을 바꾼 직후에는 잠깐 IME ?가 보일 수 있습니다.

배열
컴팩트(기본)는 57키입니다. 풀(Full)은 Esc/F1~F12, PrtSc/ScrLk, Insert/Home/PgUp/Delete/End/PgDn, 방향키 4개, 숫자 키패드를 더합니다. ⚙ 메뉴(Full 배열로 전환 / Compact 배열로 전환)에서만 바꾸며, 창이 커지고 다른 설정은 그대로 동작합니다.

조합 키
Shift·Ctrl·Alt·Win은 한 번만 적용되는 고정 키입니다. 하나를 누르면(켜진 채 유지) 다음 키와 함께 전달됩니다. 예: Ctrl 다음 C. 그 키 하나 뒤, 대상 창이 바뀔 때, 같은 키를 다시 누를 때 해제됩니다. 조합 키만 단독으로 보내지는 않습니다. Ctrl+Alt+Del은 Windows가 예약한 키라 어떤 프로그램도 보낼 수 없으므로 안내만 표시합니다.

미러와 발광
미러가 켜져 있으면 물리 키를 HUD에서 보여 줍니다. 실시간은 물리 키를 누르는 동안과 뗀 뒤 약 240ms 동안, 마지막 키는 다음 일반 키를 누를 때까지 표시합니다. 입력 이력은 저장하지 않습니다. 물리 타건이 화면에 보이면 안 되는 때에는 미러를 끄세요.

미러 잠금
입력 잠금(수동). 미러는 시스템 전체의 키를 봅니다. HoloKeyboard V1은 키 발광에 대해 비밀번호 입력칸을 자동으로 구별하지 않습니다. 입력 잠금이 OFF이면 비밀번호를 입력할 때를 포함해 어떤 프로그램에서든 누른 키가 점멸하며, 화면 공유나 녹화에는 어떤 키를 눌렀는지 보일 수 있습니다. 비밀번호를 입력하기 전에는 입력 잠금을 ON으로 하세요(환경설정, 입력 잠금). 입력 잠금이 ON인 동안에는 모든 키 발광과 마지막 키 기억이 지워지고, 상태 글자에 잠금: 입력 잠금이 표시되며, HUD 키를 눌러도 입력은 되지만 화면에 표시하지 않습니다. 자체 키 입력 표시는 비밀번호 칸과 보호 여부가 확인되지 않는 칸에서 차단됩니다.

한국어 입력 클릭 보호
한국어 IME가 켜져 있고 포인터가 키 위에 있는 동안에만 짧게 마우스 후크를 둬서 조합이 끊기지 않게 합니다. 포인터가 벗어나거나 최소화·종료하면 즉시 제거하고, 끝나지 않은 클릭은 1.5초 뒤 해제합니다.

동화 타자 연습
펼친 메뉴의 타자 연습 또는 환경설정의 동화 타자 연습을 선택하세요. 제목 표시줄을 끌면 전체 창을 옮기고 오른쪽 아래 ↘를 끌면 연습판과 키보드 크기가 함께 바뀝니다. 동화를 골라 입력칸에 따라 치세요. 안내가 나오면 Win+Space 또는 한/영 키로 동화에 맞는 Windows 입력 모드를 선택하세요. 연습을 닫으면 원래 키보드가 복원됩니다.

입력 자동 표시와 입력 잠금
키를 자체 조합해 하단 한 줄에 표시합니다. Windows 모드를 확인할 수 없을 때 조합 EN/KR을 선택할 수 있습니다. 이 선택은 하단 표시에만 적용됩니다. 비밀번호와 보호 여부를 확인할 수 없는 입력칸에서는 표시를 차단합니다. 입력잠금 ON이면 입력 표시와 발광이 지워집니다.

입력 표시와 시험용 입력란
입력표시 ON/OFF로 하단 한 줄을 켜고 끕니다. 글자색으로 표시 글자의 색상을 바꿉니다.

키보드 진단
1. 일반·등록 입력란은 물리 키 미러와 입력 표시를 확인합니다. 미러와 입력표시를 켜고 맨 위 칸을 클릭한 후 A를 1초간 눌렀다 떼세요. Shift도 따로 시험하세요. 현재 누른 키 표시와 HUD 발광이 눌렀다 뗄 때 바뀌는지 확인합니다.
2. 비밀번호·차단 입력란은 HUD가 비밀번호 글자를 읽지 않는지 시험합니다. 가운데 칸에 시험용 문자를 넣으면 글자가 가려지며 HUD에 표시되지 않습니다(키 발광은 입력 잠금으로만 조절됩니다).
3. 미등록·차단 입력란은 접근 허용 여부를 시험합니다. 맨 아래 칸에 넣은 문자는 그 칸에는 보이지만, HUD는 그 값을 표시하지 않습니다.
실제 비밀번호 대신 시험용 문자만 넣으세요. 진단창을 닫으면 시험 문자열은 사라집니다.

실제 태블릿 터치는 검증되지 않았습니다.

키보드 호환성 및 맞춤 개발
HoloKeyboard는 Windows 표준 키보드 배열을 기반으로 설계되었습니다.
추가 자판 배열, 특수 키 또는 맞춤 기능이 필요한 경우 요청해 주세요.
• 무료 개선 요청: 사용자 요청과 수요를 바탕으로 검토하고 우선순위를 정합니다.
• 유료 맞춤 개발: 신속히 검토하고 기술적 가능성 및 일정 협의 후 우선 개발합니다.
• 공식 지원 기능의 오류 수정은 무료로 제공합니다.
여러분의 의견을 통해 HoloKeyboard를 지속적으로 개선하겠습니다.
""",
}


def profile_guide(language, availability):
    english = language == "EN"
    lines = [
        "Windows profiles and verification" if english else "Windows 프로필 및 검증 범위",
        ("Key range: the 57-key Compact ANSI area or the standard Full layout. "
         "Extra ISO/JIS keys and alternative layouts are outside V1." if english else
         "키 범위는 컴팩트 ANSI 57키 또는 표준 풀 배열입니다. ISO/JIS 추가 키와 변형 배열은 V1 범위 밖입니다."),
        ("Availability reflects profiles Windows exposes on this device. The Windows IME selector "
         "(Win+Space) handles IME selection. An exact IME cannot always be identified in other apps." if english else
         "사용 가능 여부는 이 기기에서 Windows가 노출한 프로필을 기준으로 합니다. "
         "IME 선택은 Win+Space를 사용하며, 외부 앱의 정확한 IME를 확인하지 못할 수 있습니다."),
    ]
    for code, profile in PROFILES.items():
        present = availability.get(code)
        local = (("available" if present else "unavailable") if present is not None else "unconfirmed") if english else (
            ("사용 가능" if present else "사용 불가") if present is not None else "확인 불가")
        tested = ("Korean/English modes verified in the test Edit" if code == "KR" else
                  "Windows input not verified for this profile") if english else (
            "전용 편집창에서 한/영 모드 검증" if code == "KR" else "이 프로필의 Windows 실입력 미검증")
        lines.append(f"{code} — {profile.name} | {local}; {tested}")
    return "\n\n".join(lines)


# Korean wording that differs from the (Korean) lookup key itself.
KO = {"동화 타자 연습": "동화 타자 연습"}


def translate(language, text):
    return EN.get(text, text) if language == "EN" else KO.get(text, text)


def open_help(owner, language, availability=None):
    window = tk.Toplevel(owner)
    window.title(f"HoloKeyboard · {BRAND} — " + translate(language, "도움말"))
    window.geometry("640x510")
    shell = ttk.Frame(window, padding=12)
    shell.pack(fill="both", expand=True)
    content = tk.Text(shell, wrap="word", padx=9, pady=7,
                      font=("Segoe UI" if language == "EN" else "Malgun Gothic", 11))
    scroll = ttk.Scrollbar(shell, orient="vertical", command=content.yview)
    scroll.pack(side="right", fill="y")
    ttk.Button(window, text="Close" if language == "EN" else "닫기",
               command=window.destroy).pack(side="bottom", pady=(0, 8))
    content.configure(yscrollcommand=scroll.set)
    content.pack(side="left", fill="both", expand=True)
    content.insert("1.0", BRAND+" · "+GUIDE[language]+"\n"+controls_help(language)+"\n\n"
                   + profile_guide(language, availability or {}))
    content.configure(state="disabled")
    window.bind("<Escape>", lambda _event: window.destroy())
    window.lift()
    return window

