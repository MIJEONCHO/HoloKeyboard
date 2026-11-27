# HoloKeyboard V1 · AI Companion Lab

[English README](README.md)

HoloKeyboard는 키보드를 내려다보지 않고 화면의 홀로그램 자판을 보며 타자할 수 있게 해 주는 Windows 프로그램입니다. 타자 연습 창이 함께 들어 있습니다. 문서를 비추는 프로그램이 아니라 키보드를 비추는 프로그램입니다. 파란색 스타일과 모든 핵심 기능은 무료입니다.

## 비밀번호와 민감한 입력 — 먼저 읽어 주세요

- **비밀번호나 비밀 내용을 입력하기 전에 입력 잠금을 ON으로 하세요**(환경설정 → 입력 잠금, 또는 펼친 메뉴의 입력 잠금 버튼). ON이면 키 발광과 하단 한 줄이 모두 지워지고 멈춥니다. 입력이 끝나면 OFF로 돌리세요.
- **입력 잠금이 OFF이면 비밀번호를 입력할 때를 포함해 모든 프로그램에서 누른 키가 발광합니다.** 화면을 보는 사람, 화면 공유, 녹화에 누른 키가 보일 수 있습니다.
- 하단 한 줄에는 별도의 자동 확인이 있습니다. Windows가 비밀번호라고 알려 주는 입력칸과 확인할 수 없는 입력칸에서는 표시하지 않습니다. 이 확인은 상대 프로그램이 Windows에 알려 주는 정보에 의존합니다. 비밀번호 칸을 자체적으로 그리고 알려 주지 않는 프로그램에서는 구별하지 못할 수 있습니다. **자동 확인에 의존하지 말고 입력 잠금을 사용하세요.**
- 입력한 내용은 저장·기록·복사·외부 전송하지 않습니다. 다른 프로그램 입력칸의 글자를 읽지도 않습니다. 하단 한 줄(최대 120자)은 누른 키로 메모리에서 만든 것이라 문서 내용과 다를 수 있습니다.

## 한컴 한글

- Windows 한글 입력기를 쓰려면 한글에서 **Alt+F2**(입력기 환경 설정 → 글자판 바꾸기)를 누르고 **현재 글자판**과 **제1 글자판**을 **윈도우 입력기**로 선택하세요.
- 한컴 한글은 독자적인 방식으로 입력을 처리해 Windows에 일반적인 입력칸 정보를 주지 않습니다. 개인정보 보호를 위해 하단 한 줄은 HoloKeyboard가 문서 본문이라고 식별할 수 있는 곳에서만 표시합니다(한글 2010에서 확인). 암호 설정 대화상자에서 "Protected input — hidden"이 표시되는 것을 확인했습니다. 다른 한컴 대화상자·버전·편집 영역은 모두 확인하지 못했으며 숨겨질 수 있습니다. 비밀 내용은 입력 잠금을 켜고 입력하세요.
- 표시가 IME ?이면 한/영 키를 한 번 누르거나, 하단 표시용 조합을 EN 또는 KR로 선택하세요.
- 한컴 문서 안에 넣은 암호 표시 입력 상자(양식 개체)는 본문과 구별하지 못합니다. 이런 칸에 입력할 때는 입력 잠금을 켜세요.
- HUD의 상단 버튼이나 메뉴를 사용한 뒤에는 입력할 창을 한 번 클릭하고 타자하세요. 화면 자판 키를 누를 때는 필요 없습니다.

## 코드 서명과 SmartScreen

실행 파일에는 **코드 서명이 없습니다.** Windows SmartScreen이 "Windows의 PC 보호" 화면을 표시할 수 있고, 스마트 앱 컨트롤이나 회사 정책이 실행을 차단할 수 있습니다. 이 프로젝트의 GitHub Releases에서만 내려받고, ZIP의 SHA-256을 게시된 값과 비교하세요(`Get-FileHash <zip> -Algorithm SHA256`). 값이 같고 출처를 신뢰할 때에만 **추가 정보 → 실행**을 선택하세요. 이 프로그램 때문에 Windows 보호 기능을 끄지는 마세요.

## 실행

Windows x64 ZIP을 모두 풀고 `HoloKeyboard.exe`를 실행하세요. `_internal` 폴더는 EXE 옆에 둡니다. Windows 11 x64에서 시험했습니다. VC 런타임이 없다는 메시지가 나오면 [Microsoft 공식 설치 파일](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)을 사용하세요. 소스는 Python 3.13 x64(Tcl/Tk 포함)에서 `python -B src/holo_keyboard_hud.py`로 실행합니다.

- [사용설명서](MANUAL.ko.md) · [개인정보 및 지원 범위](PRIVACY-SUPPORT.md)
- [제3자 고지](THIRD_PARTY_NOTICES.md) · [콘텐츠 목록](CONTENT-LIST.md) · [콘텐츠 권리](CONTENT-RIGHTS.md)
- [릴리스 노트](CHANGELOG.md) · [향후 개선](FUTURE-IMPROVEMENTS.md) · [라이선스](LICENSE)

## 후원

> 후원은 의무가 아닌 자율적인 선택입니다.  
> 우리는 모든 사용자의 양심과 선택을 존중합니다.  
> HoloKeyboard가 여러분에게 도움이 되기를 바랍니다.

[AI World Portal Ko-fi 자율 후원](https://ko-fi.com/aiportal). AI World Portal은 공통 후원 창구이고, HoloKeyboard의 개발·제품 브랜드는 AI Companion Lab입니다. 선택 스타일은 환경설정 → 후원에서 후원 사실을 직접 체크하면 켜집니다. 계정, 결제 확인, 인증 서버는 없습니다.

## 라이선스

자체 소스(`src/`)와 문서는 **MIT License**입니다. ZIP의 제3자 소프트웨어(Python, Tcl/Tk, zlib, libffi, bzip2, libmpdec, PyInstaller 부트로더)는 각자의 라이선스를 따릅니다. "AI Companion Lab", "HoloKeyboard", "AI World Portal" 이름과 로고, 사용자가 추가한 콘텐츠에는 이 라이선스가 적용되지 않습니다. 기본 타자 연습 글 8편은 이 프로젝트를 위해 새로 쓴 글입니다([콘텐츠 권리](CONTENT-RIGHTS.md)).

개발: AI Companion Lab. 저작권 (c) 2026 Mijeon Cho.
