"""UI wording shared by the HUD, its tooltips, the help window and the typing-practice module.

Single lookup for program-language text: `hud.ui_lang` ("EN" or "KO"), `hud.t(en, ko)` and
`pick(lang, en, ko)`. The UI language is only the program's display language (menus, settings, help,
tooltips, notices, typing practice). It is independent of the keyboard input language (KR/EN/JP...).
Default: English. Korean text lives in the second slot of each pair."""

DEFAULT_UI = "EN"


def pick(lang, en, ko):
    """The English or Korean variant for a UI language code ('EN' or 'KO')."""
    return ko if lang == "KO" else en


# ---- naming of the typing-practice feature (button, settings entry, window title and help match) ----
PRACTICE_BUTTON = ("Typing Practice", "타자 연습")          # top-level option-row button
PRACTICE_STORY = ("Story Typing", "동화 타자 연습")         # settings entry AND practice window title

# ---- mirror lock: reason code (mirror_guard) -> short label shown after "LOCK:" -------------------
LOCK_REASONS = {
    "user": ("input lock", "입력 잠금"),
    "password": ("password", "비밀번호"), "uia-password": ("password", "비밀번호"),
    "unknown": ("unknown field", "알 수 없는 칸"), "not-text": ("not text", "입력칸 아님"),
    "unreadable": ("no UIA", "UIA 없음"), "no-uia": ("no UIA", "UIA 없음"),
    "no-element": ("no field", "입력칸 없음"), "other-process": ("focus moved", "포커스 이동"),
    "warming": ("warming", "준비 중"), "timeout": ("slow", "응답 느림"),
    "pending": ("checking", "확인 중"), "navigating": ("checking", "확인 중"),
    "no-target": ("no focus", "포커스 없음"), "own-window": ("own window", "이 프로그램"),
}
# Longer explanation of each reason (tooltip of the status text, help).
LOCK_EXPLAIN = {
    "password": ("a password field: key glow is hidden on purpose", "비밀번호 칸: 보호를 위해 키 발광을 숨깁니다"),
    "unknown": ("Windows could not prove this is a non-password field", "비밀번호가 아님을 확인하지 못했습니다"),
    "not-text": ("the focus is not on a text field", "포커스가 입력칸이 아닙니다"),
    "no-uia": ("this program does not expose UI Automation information", "이 프로그램이 UI 자동화 정보를 제공하지 않습니다"),
    "no-element": ("no focused element was reported", "포커스된 요소가 보고되지 않았습니다"),
    "other-process": ("the focus moved to another program", "포커스가 다른 프로그램으로 옮겨졌습니다"),
    "warming": ("the browser is still building its accessibility tree", "브라우저가 접근성 정보를 만드는 중입니다"),
    "timeout": ("the program answered too slowly", "프로그램의 응답이 늦습니다"),
    "pending": ("checking the field after a click or key", "클릭이나 키 입력 뒤 칸을 확인하는 중입니다"),
    "no-target": ("no window has the keyboard focus", "키보드 포커스가 있는 창이 없습니다"),
    "own-window": ("this program's own window", "이 프로그램 자신의 창입니다"),
}


def lock_label(lang, reason):
    en, ko = LOCK_REASONS.get(reason, (reason or "unknown", reason or "알 수 없음"))
    return pick(lang, f"LOCK: {en}", f"잠금: {ko}")


# ---- tooltips (one entry per control; the help window lists exactly these) ---------------------------
# key: (label shown in help EN, KO, tooltip EN, tooltip KO)
TIPS = {
    "drag": ("Move handle", "이동 손잡이",
             "Drag to move the keyboard. Any empty area of the bar or menu moves it too.",
             "끌어서 키보드를 옮깁니다. 바나 메뉴의 빈 곳을 끌어도 옮겨집니다."),
    "lang": ("Language button", "언어 버튼",
             "Current input language (KR/EN follows the real Hangul/English state). Click to open or close the options menu.",
             "현재 입력 언어입니다(KR/EN은 실제 한/영 상태를 따릅니다). 클릭하면 옵션 메뉴를 펼치거나 접습니다."),
    "gear": ("⚙ Settings", "⚙ 환경설정",
             "Settings menu: Keyboard Diagnostics, Full/Compact layout, Story Typing, Input Lock.",
             "환경설정 메뉴: 키보드 진단, Full/Compact 배열, 동화 타자 연습, 입력 잠금."),
    "status": ("Status text", "상태 글자",
               "Shows the input profile or the manual input lock.",
               "입력 프로필 또는 수동 입력잠금 상태를 표시합니다."),
    "ui": ("UI EN / UI KR", "UI EN / UI KR",
           "Program display language only (menus, settings, help, tooltips, typing practice). Does not change the keyboard input language.",
           "프로그램 표시 언어만 바꿉니다(메뉴, 설정, 도움말, 툴팁, 타자 연습). 자판 입력 언어는 바뀌지 않습니다."),
    "mode": ("Real-time / Last Key", "실시간 / 마지막 키",
             "Real-time: physical keys glow through the press and for about 240 ms after release. Last Key: the last pressed key stays lit until the next key. Click to switch.",
             "실시간: 물리 키를 누르는 동안과 뗀 뒤 약 240ms 동안 발광합니다. 마지막 키: 다음 키를 누를 때까지 마지막 키가 켜져 있습니다. 클릭하면 전환됩니다."),
    "help": ("? Help", "? 도움말",
             "Open this help (every control explained).", "도움말을 엽니다(모든 조작 설명)."),
    "mirror": ("Mirror", "미러",
               "ON: mirror physical keys. OFF: stop receiving physical-key events. Passwords are NOT detected for the glow: turn Input Lock ON before typing a password.",
               "ON: 물리 키의 발광을 표시합니다. OFF: 물리 키 수신을 중지합니다. 발광은 비밀번호를 자동으로 구별하지 않습니다. 비밀번호를 입력하기 전에 입력 잠금을 ON으로 하세요."),
    "menu": ("Menu", "메뉴",
             "Expand or collapse the options row below.", "아래 옵션 줄을 펼치거나 접습니다."),
    "min": ("− Minimize", "− 최소화", "Minimize the keyboard.", "키보드를 최소화합니다."),
    "close": ("× Exit", "× 종료", "Exit HoloKeyboard.", "HoloKeyboard를 종료합니다."),
    "theme": ("Color dots", "색 점",
              "Key color theme (blue, mint, purple, gold, lime).", "키 색 테마(파랑, 민트, 보라, 금색, 라임)."),
    "opacity": ("Opacity", "투명",
                "Keyboard opacity. The menu stays opaque.", "키보드의 투명도입니다. 메뉴는 항상 불투명합니다."),
    "width": ("Width", "두께", "Thickness of the key outlines.", "키 테두리의 두께입니다."),
    "size": ("Size", "크기",
             "Size of the whole keyboard; proportions are kept (the bottom-right grip does the same).",
             "키보드 전체 크기입니다. 비율을 유지합니다(오른쪽 아래 손잡이도 같습니다)."),
    "input": ("Input", "입력표시",
              "Show or hide the one-line preview of the supported focused field.",
              "지원되는 현재 입력칸의 한 줄 미리보기를 켜고 끕니다."),
    "local-mode": ("Typing Auto / EN / KR", "조합 자동 / EN / KR",
                   "Select the local typing layout when the Windows mode is unknown. Does not change Windows input or unlock a field.",
                   "Windows 입력 모드 확인이 안 될 때 사용할 자체 조합 자판입니다. Windows 입력이나 입력 보호에는 영향을 주지 않습니다."),
    "color": ("Text color", "글자색",
              "Color of the preview text: Auto, Black, White or Theme. Click to cycle.",
              "미리보기 글자색: 자동, 검정, 흰색, 테마색. 클릭할 때마다 순서대로 바뀝니다."),
    "practice": ("Typing Practice", "타자 연습",
                 "Open Story Typing practice. Correct keys flash green, wrong keys red on this keyboard.",
                 "동화 타자 연습을 엽니다. 맞는 키는 이 키보드에서 초록, 틀린 키는 빨강으로 깜박입니다."),
    "grip": ("Resize grip", "크기 손잡이",
             "Drag to resize the keyboard; proportions are kept.", "끌어서 키보드 크기를 바꿉니다. 비율을 유지합니다."),
    "preview": ("Input preview", "입력 미리보기",
                "One-line preview of the supported focused field. Use Input Lock to clear it.",
                "지원되는 입력칸의 한 줄 미리보기입니다. 입력 잠금으로 즉시 지울 수 있습니다."),
    # settings (⚙) entries
    "set:diag": ("⚙ Keyboard Diagnostics", "⚙ 키보드 진단",
                 "Open three input checks: hardware mirror, password text hidden, unregistered field.",
                 "세 가지 입력 시험(물리 키 미러, 비밀번호 글자 숨김, 미등록 입력란)을 엽니다."),
    "set:layout": ("⚙ Full / Compact layout", "⚙ Full / Compact 배열",
                   "Switch between the 57-key Compact keyboard and the full 104-key keyboard.",
                   "57키 컴팩트 키보드와 104키 풀 키보드를 전환합니다."),
    "set:story": ("⚙ Story Typing", "⚙ 동화 타자 연습",
                  "Same practice as the Typing Practice button: type story sentences, keys flash green or red.",
                  "타자 연습 버튼과 같은 연습입니다. 동화 문장을 따라 치면 키가 초록 또는 빨강으로 깜박입니다."),
    "set:donate": ("Donate", "후원", "Open the voluntary supporter options.", "자율 후원 안내를 엽니다."),
    "set:about": ("About", "제품 정보", "Show the developer and product version.", "개발사와 버전을 표시합니다."),
    "locked:style": ("Supporter styles", "후원 스타일", "Confirm a donation in Settings → Donate to enable this style.",
                     "환경설정 → 후원에서 후원 여부를 확인하면 사용할 수 있습니다."),
    "set:lock": ("Input Lock", "입력 잠금",
                 "ON clears the preview and key glow immediately and keeps them off (use it before typing passwords: with Input Lock OFF, keys may glow even in a password field). OFF resumes the key glow and the automatic preview in supported text fields.",
                 "ON이면 문장과 키 발광을 즉시 지우고 꺼 둡니다(비밀번호를 입력하기 전에 사용하세요. 입력 잠금 OFF에서는 비밀번호 칸에서도 키가 점멸할 수 있습니다). OFF이면 키 발광과 지원되는 입력칸의 키 입력 표시를 재개합니다."),
}
LANG_TIP = ("Ask Windows to switch the focused program to this layout. IME layouts (JP, CN, KR) use Win+Space. "
            "Bright = current, filled = selected or English companion, gray = unavailable.",
            "포커스된 프로그램의 자판을 이 배열로 바꾸도록 Windows에 요청합니다. IME 배열(JP, CN, KR)은 Win+Space를 쓰세요. "
            "밝음 = 현재 입력 언어, 배경색 = 선택 또는 영문 동반 표시, 회색 = 사용 불가.")


def tip_text(lang, key):
    entry = TIPS.get(key)
    return pick(lang, entry[2], entry[3]) if entry else ""


def tip_label(lang, key):
    entry = TIPS.get(key)
    return pick(lang, entry[0], entry[1]) if entry else ""


def controls_help(lang):
    """Help section listing every tooltip text (same source, so help and hover never disagree)."""
    lines = [pick(lang, "Controls (hover a button for the same text; on a touch screen read it here)",
                  "조작 설명(버튼에 마우스를 올리면 같은 설명이 나옵니다. 터치 화면에서는 여기서 확인하세요)")]
    for key in TIPS:
        lines.append(f"• {tip_label(lang, key)} — {tip_text(lang, key)}")
    lines.append("• " + pick(lang, "KR EN JP CN VN TH ES FR DE RU AR — ", "KR EN JP CN VN TH ES FR DE RU AR — ")
                 + pick(lang, *LANG_TIP))
    lines.append("• " + pick(lang, "Lock reasons — ", "잠금 이유 — ") + "; ".join(
        f"{pick(lang, *LOCK_REASONS[k])}: {pick(lang, *LOCK_EXPLAIN[k])}" for k in LOCK_EXPLAIN))
    return "\n".join(lines)
