# Third-party notices · HoloKeyboard V1 · AI Companion Lab

| Component | Where it is used | Treatment |
|---|---|---|
| CPython 3.13.17 | Executable bundle | Preserve the unmodified Python installation LICENSE.txt, including PSF/historical terms and bundled component notices (including libffi and bzip2). |
| Tcl/Tk 8.6.15 | Executable bundle | Preserve the Tcl/Tk license terms and shipped notices. |
| zlib 1.3.1 | Executable bundle | Preserve the upstream zlib notice. |
| libmpdec (mpdecimal) | Executable bundle (inside Python's `_decimal.pyd`) | BSD 2-clause notice reproduced in `licenses/mpdecimal-LICENSE.txt`, as published in the Python 3.13 documentation. |
| Windows UCRT and Visual C++ runtime | Host OS | UCRT comes from Windows. If necessary, install Microsoft's official Visual C++ x64 Redistributable. The candidate does not ship Microsoft runtime DLLs. |
| Windows Raw Input, UI Automation, IME, System.Speech and installed voices | Host OS | Windows APIs and existing Windows components. Voices and system DLLs are not distributed with HoloKeyboard. |
| PyInstaller 6.22.0 | Build tooling and executable bootloader | Its executable-distribution exception applies, subject to bundled dependency terms. No separate build packages are shipped. |

Bundled files under `licenses/` are the original applicable notices from the Python distribution, upstream zlib, Tcl/Tk and libmpdec. Retain these with the binary ZIP. See [Python license](https://docs.python.org/3.13/license.html), [Tcl/Tk terms](https://www.tcl-lang.org/software/tcltk/license.html), [zlib license](https://www.zlib.net/zlib_license.html), and [PyInstaller license exception](https://www.pyinstaller.org/en/stable/license.html).

The separately installed x64 Microsoft runtime is available from [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). Windows 11 supplies the [system UCRT](https://learn.microsoft.com/en-us/cpp/windows/universal-crt-deployment).

제3자 라이선스 원문은 바이너리의 `licenses/`를 유지하세요. Windows 구성 요소와 설치된 음성은 제품에 동봉하지 않습니다. libmpdec 고지는 `licenses/mpdecimal-LICENSE.txt`입니다. 제1자 코드와 문서는 MIT License입니다(`LICENSE`).
