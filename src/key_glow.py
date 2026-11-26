"""Physical key holds. The HUD owns colors and release animation."""


class KeyGlow:
    def __init__(self):
        self.held = {}

    def update(self, key):
        keys = self.held.setdefault(key.device, set())
        if key.down:
            keys.add(key.code)
            return False
        released = key.code in keys
        keys.discard(key.code)
        if not keys:
            self.held.pop(key.device)
        return released

    def active(self, code):
        return any(code in keys for keys in self.held.values())

    def pressed(self):
        return {code for keys in self.held.values() for code in keys}

    def remove(self, device):
        return self.held.pop(device, ())

    def clear(self):
        codes = self.pressed()
        self.held.clear()
        return codes
