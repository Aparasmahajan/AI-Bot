"""Hotkeys, double taps and hold detection (design §13.1), as measured in P0-2 on 14 Oct 2026.

No keyboard hook. Shortcuts go through RegisterHotKey with MOD_NOREPEAT, each with a fallback list. Caps Lock and
Alt can't be registered without breaking them, so the core reads only those two keys' up/down state every 15 ms:
two clean taps within 350 ms make a double tap, and Caps Lock is put back to the state it had before the first."""
import logging, time

from mwb import winapi
from mwb.winapi import user32

log = logging.getLogger('mwb.keys')

MAX_TAP = 0.25          # a key held longer than this is not a tap
DOUBLE = 0.35           # second key-down within 350 ms of the first key-up
OTHERS = (winapi.VK_CONTROL, winapi.VK_SHIFT, winapi.VK_LWIN, winapi.VK_RWIN, winapi.VK_TAB)
MODS = {'ctrl': winapi.MOD_CONTROL, 'alt': winapi.MOD_ALT, 'shift': winapi.MOD_SHIFT, 'win': winapi.MOD_WIN}
MOD_VK = {'ctrl': winapi.VK_CONTROL, 'alt': winapi.VK_MENU, 'shift': winapi.VK_SHIFT, 'win': winapi.VK_LWIN}
NAMED = {'space': 0x20, 'esc': 0x1B, 'escape': 0x1B, 'enter': 0x0D, 'tab': 0x09}


def parse(combo):
    """'ctrl+alt+space' -> (modifier flags, virtual key, [vks to hold])."""
    parts = [p.strip().lower() for p in combo.split('+')]
    mods, held = 0, []
    for p in parts[:-1]:
        mods |= MODS[p]
        held.append(MOD_VK[p])
    key = parts[-1]
    vk = NAMED.get(key) or (ord(key.upper()) if len(key) == 1 else int(key, 0))
    return mods, vk, held + [vk]


def pretty(combo):
    return '+'.join(p.capitalize() if len(p) > 1 else p.upper() for p in combo.split('+'))


class Hotkeys:
    """Registers named shortcuts on the calling thread; that thread's message loop receives WM_HOTKEY."""

    def __init__(self):
        self.by_id, self.active, self.next_id = {}, {}, 1

    def register(self, name, candidates):
        """Try each combo in order; returns the one registered, or None. Logs each one that is taken."""
        for combo in ([candidates] if isinstance(candidates, str) else candidates):
            mods, vk, held = parse(combo)
            hid = self.next_id
            if user32.RegisterHotKey(None, hid, mods | winapi.MOD_NOREPEAT, vk):
                self.next_id += 1
                self.by_id[hid] = name
                self.active[name] = (hid, combo, held)
                log.info('[hotkey] %s: %s', name, combo)
                return combo
            log.warning('[hotkey] %s could not be registered (another app owns it)', combo)
        return None

    def unregister(self, name):
        if name in self.active:
            hid, _, _ = self.active.pop(name)
            user32.UnregisterHotKey(None, hid)
            self.by_id.pop(hid, None)

    def unregister_all(self):
        for name in list(self.active):
            self.unregister(name)

    def name_of(self, hotkey_id):
        return self.by_id.get(hotkey_id)

    def held_keys(self, name):
        return self.active[name][2] if name in self.active else []


class TapWatcher:
    """Double taps of one key from its up/down state, checked every 15 ms (P0-2: 100 of 100 caught)."""

    def __init__(self, name, vk):
        self.name, self.vk = name, vk
        self.was_down = False
        self.t_down = 0.0
        self.dirty = False
        self.caps_before = None
        self.first_tap = None           # (time up, clean, Caps Lock state before it)

    def reset(self):
        self.was_down = winapi.down(self.vk)
        self.first_tap = None
        user32.GetAsyncKeyState(self.vk)        # clear the "pressed since last check" bit

    def step(self, now):
        """True when a clean double tap has just finished."""
        state = user32.GetAsyncKeyState(self.vk)
        d, pressed_since = bool(state & 0x8000), bool(state & 1)
        hit = False
        if d and not self.was_down:
            self.t_down, self.dirty = now, False
            if self.vk == winapi.VK_CAPITAL:
                self.caps_before = winapi.caps_on() ^ True     # Windows has already toggled it
        if d:
            self.dirty |= any(winapi.down(v) for v in OTHERS if v != self.vk)
        if not d and self.was_down:
            hit = self._tap(now, now - self.t_down)
        elif not d and not self.was_down and pressed_since:     # down and up between two checks
            if self.vk == winapi.VK_CAPITAL:
                self.caps_before = not winapi.caps_on()
            self.dirty = False
            hit = self._tap(now, 0.0)
        self.was_down = d
        return hit

    def _tap(self, now, held):
        if held > MAX_TAP:
            self.first_tap = None
            return False
        clean = not self.dirty
        if self.first_tap and (now - held) - self.first_tap[0] <= DOUBLE and clean and self.first_tap[1]:
            caps_before = self.first_tap[2]
            self.first_tap = None
            if self.vk == winapi.VK_CAPITAL and caps_before is not None and winapi.caps_on() != caps_before:
                winapi.send_keys((winapi.VK_CAPITAL, False), (winapi.VK_CAPITAL, True))    # put the light back
                time.sleep(0.03)
                user32.GetAsyncKeyState(winapi.VK_CAPITAL)       # so our own press isn't counted as a tap
                self.was_down = False
            return True
        self.first_tap = (now, clean, self.caps_before)
        return False


class HoldWatch:
    """After a hold shortcut fires: released() turns True once any of its keys is let go."""

    def __init__(self, vks):
        self.vks = vks
        self.t0 = time.monotonic()

    def released(self):
        return not all(winapi.down(vk) for vk in self.vks)

    @property
    def held_s(self):
        return time.monotonic() - self.t0
