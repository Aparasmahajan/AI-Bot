"""P0-2: double taps of Caps Lock and Alt by a 15 ms check, and Ctrl+Alt+Space hold-to-talk with paste.
Works the way design §13.2 describes: GetAsyncKeyState for Caps Lock and Alt only (no keyboard hook),
RegisterHotKey for Ctrl+Alt+Space, polling only while it is held. Also notes whether Ctrl, Shift,
Win or Tab was down during a tap, to show how many false starts a stricter rule would avoid.
Standard library only. Logs timings (no other keys) to %LOCALAPPDATA%\\MWB\\p0\\p0-2-keys.csv.

  py -3.14 -I p0_2_keys.py      then follow the steps it prints; Ctrl+C prints the results.
  (--seconds N stops by itself after N seconds.)

Steps: 1) double-tap Caps Lock 50 times at your normal pace; 2) double-tap Alt 50 times;
3) work normally for 5 minutes (typing, Alt+Tab, capitals): anything detected then is a false start;
4) in Outlook, Teams, VS Code and Brave, click in a text box, hold Ctrl+Alt+Space (or the fallback
   it names) for 1-2 s, let go:
   a test line should appear. Your clipboard text is put back afterwards."""
import csv, ctypes, ctypes.wintypes as wt, datetime, os, sys, time

user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetKeyState.restype = ctypes.c_short
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
user32.GetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]

TICK = 0.015            # the 15 ms check
MAX_TAP = 0.25          # a key held longer than this is not a tap
DOUBLE = 0.35           # second key-down within 350 ms of the first key-up
VK_CAPITAL, VK_MENU, VK_SPACE, VK_CONTROL, VK_SHIFT = 0x14, 0x12, 0x20, 0x11, 0x10
OTHERS = {'Ctrl': 0x11, 'Shift': 0x10, 'Win': 0x5B, 'RWin': 0x5C, 'Tab': 0x09}
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x0312
CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x2


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wt.WORD), ('wScan', wt.WORD), ('dwFlags', wt.DWORD), ('time', wt.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):     # only here so the union has the right size
    _fields_ = [('dx', wt.LONG), ('dy', wt.LONG), ('mouseData', wt.DWORD), ('dwFlags', wt.DWORD),
                ('time', wt.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wt.DWORD), ('u', _U)]


def send_keys(*strokes):
    """strokes: (vk, up) pairs, sent as one SendInput batch."""
    arr = (INPUT * len(strokes))()
    for i, (vk, up) in enumerate(strokes):
        arr[i].type = 1
        arr[i].ki = KEYBDINPUT(vk, 0, 0x2 if up else 0, 0, 0)
    return user32.SendInput(len(strokes), arr, ctypes.sizeof(INPUT))


def down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def caps_on():
    return bool(user32.GetKeyState(VK_CAPITAL) & 1)


def clipboard_get():
    """Return the clipboard text, '' if empty, or None if it holds something else (an image, files)."""
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        return None
    try:
        if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            h = user32.GetClipboardData(CF_UNICODETEXT)
            p = kernel32.GlobalLock(h)
            text = ctypes.wstring_at(p)
            kernel32.GlobalUnlock(h)
            return text
        return '' if user32.CountClipboardFormats() == 0 else None
    finally:
        user32.CloseClipboard()


def clipboard_set(text):
    data = ctypes.create_unicode_buffer(text)
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, ctypes.sizeof(data))
    ctypes.memmove(kernel32.GlobalLock(h), data, ctypes.sizeof(data))
    kernel32.GlobalUnlock(h)
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    user32.EmptyClipboard()
    user32.SetClipboardData(CF_UNICODETEXT, h)
    user32.CloseClipboard()


class TapWatcher:
    """Turns the up/down state of one key, sampled every 15 ms, into taps and double taps."""

    def __init__(self, name, vk):
        self.name, self.vk = name, vk
        self.was_down = False
        self.t_down = self.last_up = 0.0
        self.dirty = False
        self.caps_before = None
        self.first_tap = None           # (time up, dirty, caps state before it) of a waiting first tap
        self.taps = self.doubles = self.doubles_clean = self.long_presses = self.restores = 0
        self.missed_fast = 0

    def step(self, now, log):
        state = user32.GetAsyncKeyState(self.vk)      # one read: the low bit resets on every call
        d, pressed_since = bool(state & 0x8000), bool(state & 1)
        if d and not self.was_down:
            self.t_down, self.dirty = now, False
            self.caps_before = caps_on() ^ (self.vk == VK_CAPITAL)   # Windows has already toggled it
        if d:
            self.dirty |= any(down(v) for v in OTHERS.values())
        if not d and self.was_down:
            self.tap(now, now - self.t_down, log)
        elif not d and not self.was_down and pressed_since:
            self.missed_fast += 1       # down and up between two checks: shorter than 15 ms
            self.caps_before = (not caps_on()) if self.vk == VK_CAPITAL else None
            self.dirty = False
            self.tap(now, 0.0, log)
        self.was_down = d

    def tap(self, now, held, log):
        if held > MAX_TAP:
            self.long_presses += 1
            self.first_tap = None
            return
        self.taps += 1
        if self.first_tap and (now - held) - self.first_tap[0] <= DOUBLE:
            gap = (now - held) - self.first_tap[0]
            clean = not (self.dirty or self.first_tap[1])
            self.doubles += 1
            self.doubles_clean += clean
            restored = ''
            if self.vk == VK_CAPITAL and caps_on() != self.first_tap[2]:
                send_keys((VK_CAPITAL, False), (VK_CAPITAL, True))   # put the light back
                time.sleep(0.03)
                user32.GetAsyncKeyState(VK_CAPITAL)                  # so our own press isn't counted as a tap
                self.restores += 1
                restored = ' (Caps Lock put back)'
            flag = '' if clean else '   [Ctrl/Shift/Win/Tab was down: a stricter rule would skip this]'
            print(f'{datetime.datetime.now():%H:%M:%S}  {self.name} double tap #{self.doubles}  '
                  f'gap {gap * 1000:.0f} ms, second tap {held * 1000:.0f} ms{restored}{flag}')
            log.writerow([datetime.datetime.now().isoformat(timespec='milliseconds'), self.name, 'double',
                          round(gap * 1000), round(held * 1000), int(clean), int(bool(restored))])
            self.first_tap = None
        else:
            self.first_tap = (now, self.dirty, self.caps_before)
            log.writerow([datetime.datetime.now().isoformat(timespec='milliseconds'), self.name, 'tap',
                          '', round(held * 1000), int(not self.dirty), ''])


def hold_and_paste(n, holds, log):
    """Ctrl+Alt+Space fired: poll every 15 ms until it is let go, then paste a test line."""
    t0 = time.perf_counter()
    while down(VK_SPACE) and down(VK_CONTROL) and down(VK_MENU):
        time.sleep(TICK)
    held = time.perf_counter() - t0
    # Wait for every key to be up, Shift too (the fallback uses it): a held Shift turns the paste into
    # Ctrl+Shift+V, which VS Code takes as "open Markdown preview".
    while down(VK_CONTROL) or down(VK_MENU) or down(VK_SPACE) or down(VK_SHIFT):
        time.sleep(TICK)
    released = time.perf_counter() - t0 - held
    holds.append(held)
    saved = clipboard_get()
    if saved is None:
        print('  Clipboard holds something other than text; copy some text first so nothing is lost.')
        return
    line = f'MWB P0-2 paste test {n} at {datetime.datetime.now():%H:%M:%S}, held {held:.2f} s'
    clipboard_set(line)
    t1 = time.perf_counter()
    send_keys((VK_CONTROL, False), (0x56, False), (0x56, True), (VK_CONTROL, True))
    time.sleep(0.4)                 # give the app time to read the clipboard before it is put back
    clipboard_set(saved)
    title = ctypes.create_unicode_buffer(200)
    user32.GetWindowTextW(user32.GetForegroundWindow(), title, 200)
    app = title.value.rsplit(' - ', 1)[-1][:40] or '?'
    print(f'{datetime.datetime.now():%H:%M:%S}  hold #{n}: held {held:.2f} s, all keys up {released * 1000:.0f} ms later, '
          f'pasted into "{app}" in {(time.perf_counter() - t1) * 1000:.0f} ms. Check that the line appeared.')
    log.writerow([datetime.datetime.now().isoformat(timespec='milliseconds'), 'push-to-talk', 'hold',
                  round(held * 1000), round(released * 1000), '', app])


def main():
    folder = os.path.join(os.environ['LOCALAPPDATA'], 'MWB', 'p0')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'p0-2-keys.csv')
    new = not os.path.exists(path)
    f = open(path, 'a', newline='', encoding='utf-8')
    log = csv.writer(f)
    if new:
        log.writerow(['time', 'key', 'event', 'gap_or_hold_ms', 'tap_or_release_ms', 'clean', 'caps_restored_or_app'])
    print('P0-2 key test running. Caps Lock is', 'ON' if caps_on() else 'off', 'now.')
    # The fallback is the design's AltGr modifier set (§13.2): Ctrl+Shift+Alt.
    for mods, name in ((MOD_CONTROL | MOD_ALT, 'Ctrl+Alt+Space'), (MOD_CONTROL | MOD_ALT | 0x4, 'Ctrl+Shift+Alt+Space')):
        if user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, VK_SPACE):
            print(f'{name} registered: use it for step 4.')
            break
        print(f'{name} is taken by another app.')
    else:
        print('Hold test unavailable.')
    print(__doc__[__doc__.index('Steps:'):])
    limit = float(sys.argv[sys.argv.index('--seconds') + 1]) if '--seconds' in sys.argv else None
    print('Press Ctrl+C here to finish.\n' if limit is None else f'Stopping by itself after {limit:.0f} s.\n')
    caps, alt = TapWatcher('Caps Lock', VK_CAPITAL), TapWatcher('Alt', VK_MENU)
    holds, msg, ticks, late = [], wt.MSG(), 0, 0
    start = time.perf_counter()
    try:
        while limit is None or time.perf_counter() - start < limit:
            t = time.perf_counter()
            while user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1):
                hold_and_paste(len(holds) + 1, holds, log)
                f.flush()
                caps.was_down = alt.was_down = False
                alt.first_tap = None        # the Alt in Ctrl+Alt+Space is not a tap
                user32.GetAsyncKeyState(VK_MENU)
            now = time.perf_counter()
            caps.step(now, log)
            alt.step(now, log)
            ticks += 1
            spent = time.perf_counter() - t
            late += spent > TICK
            time.sleep(max(0.0, TICK - spent))
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnregisterHotKey(None, 1)
        f.close()
    mins = (time.perf_counter() - start) / 60
    print(f'\nResults after {mins:.1f} minutes ({ticks} checks, average every {(time.perf_counter() - start) / max(ticks, 1) * 1000:.1f} ms):')
    for w in (caps, alt):
        print(f'  {w.name}: {w.doubles} double taps ({w.doubles_clean} clean), {w.taps} taps, '
              f'{w.long_presses} longer presses, {w.missed_fast} taps under 15 ms'
              + (f', Caps Lock put back {w.restores} times' if w.vk == VK_CAPITAL else ''))
    if holds:
        print(f'  Push-to-talk: {len(holds)} holds, {min(holds):.2f}-{max(holds):.2f} s')
    print('  Caps Lock is', 'ON' if caps_on() else 'off', 'now.')
    print('Compare the double-tap counts with how many you did (pass: at least 99 %),'
          ' and count any detected during normal work as false starts (pass: none).')
    print(f'Log: {path.replace(os.environ["USERPROFILE"], "%USERPROFILE%")}')


if __name__ == '__main__':
    main()
