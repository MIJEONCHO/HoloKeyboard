"""Win32 primitives shared by the HUD input driver and its isolated test lab."""
import ctypes as c
from ctypes import wintypes as w

USER = c.WinDLL("user32", use_last_error=True)
KERNEL = c.WinDLL("kernel32", use_last_error=True)
GDI = c.WinDLL("gdi32", use_last_error=True)
IMM = c.WinDLL("imm32", use_last_error=True)
WPARAM, LPARAM = c.c_size_t, c.c_ssize_t
PROC = c.WINFUNCTYPE(LPARAM, w.HWND, w.UINT, WPARAM, LPARAM)


def api(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, args
    return fn


class WindowClass(c.Structure):
    _fields_ = [("style", w.UINT), ("proc", PROC), ("extra_class", c.c_int),
                ("extra_window", c.c_int), ("instance", w.HINSTANCE), ("icon", w.HANDLE),
                ("cursor", w.HANDLE), ("background", w.HANDLE), ("menu", w.LPCWSTR),
                ("name", w.LPCWSTR)]


class GuiThread(c.Structure):
    _fields_ = [("size", w.DWORD), ("flags", w.DWORD),
                ("active", w.HWND), ("focus", w.HWND), ("capture", w.HWND),
                ("menu", w.HWND), ("move", w.HWND), ("caret", w.HWND), ("rect", w.RECT)]


class RawDevice(c.Structure):
    _fields_ = [("usage_page", w.USHORT), ("usage", w.USHORT), ("flags", w.DWORD),
                ("target", w.HWND)]


class RawHeader(c.Structure):
    _fields_ = [("kind", w.DWORD), ("size", w.DWORD), ("device", w.HANDLE), ("param", WPARAM)]


class RawKeyboard(c.Structure):
    _fields_ = [("scan", w.USHORT), ("flags", w.USHORT), ("reserved", w.USHORT),
                ("vk", w.USHORT), ("message", w.UINT), ("extra", w.ULONG)]


class RawPacket(c.Structure):
    _fields_ = [("header", RawHeader), ("keys", RawKeyboard)]


class KeyboardInput(c.Structure):
    _fields_ = [("vk", w.WORD), ("scan", w.WORD), ("flags", w.DWORD),
                ("time", w.DWORD), ("extra", WPARAM)]


class MouseInput(c.Structure):
    _fields_ = [("x", w.LONG), ("y", w.LONG), ("data", w.DWORD),
                ("flags", w.DWORD), ("time", w.DWORD), ("extra", WPARAM)]


class InputValue(c.Union):
    _fields_ = [("mouse", MouseInput), ("keyboard", KeyboardInput)]


class Input(c.Structure):
    _fields_ = [("kind", w.DWORD), ("value", InputValue)]


create_window = api(USER, "CreateWindowExW", w.HWND, w.DWORD, w.LPCWSTR, w.LPCWSTR,
                    w.DWORD, c.c_int, c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU,
                    w.HINSTANCE, c.c_void_p)
module_handle = api(KERNEL, "GetModuleHandleW", w.HINSTANCE, w.LPCWSTR)
register_class = api(USER, "RegisterClassW", w.ATOM, c.POINTER(WindowClass))
unregister_class = api(USER, "UnregisterClassW", w.BOOL, w.LPCWSTR, w.HINSTANCE)
def_window = api(USER, "DefWindowProcW", LPARAM, w.HWND, w.UINT, WPARAM, LPARAM)
destroy_window = api(USER, "DestroyWindow", w.BOOL, w.HWND)
set_pos = api(USER, "SetWindowPos", w.BOOL, w.HWND, w.HWND, c.c_int, c.c_int,
              c.c_int, c.c_int, w.UINT)
get_ancestor = api(USER, "GetAncestor", w.HWND, w.HWND, w.UINT)
foreground = api(USER, "GetForegroundWindow", w.HWND)
window_thread = api(USER, "GetWindowThreadProcessId", w.DWORD, w.HWND, c.POINTER(w.DWORD))
get_gui = api(USER, "GetGUIThreadInfo", w.BOOL, w.DWORD, c.POINTER(GuiThread))
get_style = api(USER, "GetWindowLongW", w.LONG, w.HWND, c.c_int)
set_style = api(USER, "SetWindowLongW", w.LONG, w.HWND, c.c_int, w.LONG)
get_layout = api(USER, "GetKeyboardLayout", w.HANDLE, w.DWORD)
is_ime = api(IMM, "ImmIsIME", w.BOOL, w.HANDLE)
ime_context = api(IMM, "ImmGetContext", w.HANDLE, w.HWND)
ime_release = api(IMM, "ImmReleaseContext", w.BOOL, w.HWND, w.HANDLE)
ime_open = api(IMM, "ImmGetOpenStatus", w.BOOL, w.HANDLE)
ime_conversion = api(IMM, "ImmGetConversionStatus", w.BOOL, w.HANDLE, c.POINTER(w.DWORD),
                     c.POINTER(w.DWORD))
register_raw = api(USER, "RegisterRawInputDevices", w.BOOL, c.POINTER(RawDevice),
                   w.UINT, w.UINT)
get_raw = api(USER, "GetRawInputData", w.UINT, w.HANDLE, w.UINT, c.c_void_p,
              c.POINTER(w.UINT), w.UINT)
screen_to_client = api(USER, "ScreenToClient", w.BOOL, w.HWND, c.POINTER(w.POINT))
show_window = api(USER, "ShowWindow", w.BOOL, w.HWND, c.c_int)
make_region = api(GDI, "CreateRectRgn", w.HANDLE, c.c_int, c.c_int, c.c_int, c.c_int)
merge_region = api(GDI, "CombineRgn", c.c_int, w.HANDLE, w.HANDLE, w.HANDLE, c.c_int)
delete_region = api(GDI, "DeleteObject", w.BOOL, w.HANDLE)
set_region = api(USER, "SetWindowRgn", c.c_int, w.HWND, w.HANDLE, w.BOOL)
send_input = api(USER, "SendInput", w.UINT, w.UINT, c.POINTER(Input), c.c_int)
message_extra = api(USER, "GetMessageExtraInfo", LPARAM)
capture = api(USER, "SetCapture", w.HWND, w.HWND)
release_capture = api(USER, "ReleaseCapture", w.BOOL)
pointer_type = api(USER, "GetPointerType", w.BOOL, w.UINT, c.POINTER(w.UINT))
remote_session = api(USER, "GetSystemMetrics", c.c_int, c.c_int)
default_ime_window = api(IMM, "ImmGetDefaultIMEWnd", w.HWND, w.HWND)
send_timeout = api(USER, "SendMessageTimeoutW", LPARAM, w.HWND, w.UINT, WPARAM, LPARAM,
                   w.UINT, w.UINT, c.POINTER(c.c_size_t))
class_name = api(USER, "GetClassNameW", c.c_int, w.HWND, w.LPWSTR, c.c_int)
is_window = api(USER, "IsWindow", w.BOOL, w.HWND)


def checked(result):
    if not result:
        raise c.WinError(c.get_last_error())
    return result


def scan_event(scan, up=False, extended=False, vk=0):
    event = Input()
    event.kind = 1
    flags = (0 if vk else 8) | (2 if up else 0) | (1 if extended else 0)
    event.value.keyboard = KeyboardInput(vk, scan, flags, 0, 0x484F4C4F)
    return event


def send_events(events):
    batch = (Input*len(events))(*events)
    return send_input(len(batch), batch, c.sizeof(Input))


def primary_work_area():
    """Primary monitor work area, excluding the taskbar."""
    area = w.RECT()
    read = api(USER, "SystemParametersInfoW", w.BOOL, w.UINT, w.UINT, c.POINTER(w.RECT), w.UINT)
    return area if read(0x30, 0, c.byref(area), 0) else None  # SPI_GETWORKAREA
