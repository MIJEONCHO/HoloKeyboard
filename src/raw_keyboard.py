"""Windows Raw Input registration and stateless packet decoding."""
import ctypes as c
from dataclasses import dataclass

import win_native as n


@dataclass(frozen=True)
class RawKey:
    device: int
    code: str
    down: bool


class RawKeyboard:
    def __init__(self, key_ids):
        self.key_ids = key_ids
        self.enabled = False

    def set_enabled(self, enabled, hwnd):
        if bool(enabled) == self.enabled:
            return False
        device = n.RawDevice(1, 6, 0x2100 if enabled else 1, hwnd if enabled else None)
        n.checked(n.register_raw(c.byref(device), 1, c.sizeof(device)))
        self.enabled = bool(enabled)
        return True

    def read(self, handle):
        size = n.w.UINT()
        header_size = c.sizeof(n.RawHeader)
        minimum = header_size + c.sizeof(n.RawKeyboard)
        if n.get_raw(handle, 0x10000003, None, c.byref(size), header_size) != 0:
            return None
        if not minimum <= size.value <= 1024:
            return None
        buffer = c.create_string_buffer(size.value)
        read = n.get_raw(handle, 0x10000003, buffer, c.byref(size), header_size)
        if not minimum <= read <= len(buffer):
            return None
        packet = n.RawPacket.from_buffer(buffer)
        key = packet.keys
        if packet.header.kind != 1 or key.extra == 0x484F4C4F or key.flags & 4 or key.scan == 0xff or key.vk >= 0xff:
            return None
        code = ("LangToggle" if key.vk == 0x15 else
                self.key_ids.get(key.scan | (0xe000 if key.flags & 2 else 0)))
        return RawKey(packet.header.device or 0, code, not key.flags & 1) if code else None
