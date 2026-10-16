"""Finds calls in any app (design §9.3), from Windows' own record of which apps use the microphone.

Every 5 seconds the core reads ...\\CapabilityAccessManager\\ConsentStore\\microphone: Windows keeps a start and stop
time there for each Store app and each desktop program, and a stop time of 0 means "using the mic now". Reading it
takes microseconds and needs no admin rights. A holder is matched against config/vc_apps.toml; a browser counts when
one of its window titles shows a meeting site, read only at that moment. A call starts once an app has held the mic
for 20 s and ends once it has let go for 60 s. MWB's own process (dictation, recording) is never a call."""
import ctypes, ctypes.wintypes as wt, os, sys, time, tomllib, winreg
from dataclasses import dataclass, field
from pathlib import Path

from mwb.winapi import kernel32, user32

CONSENT = r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore'
START_AFTER_S, END_AFTER_S = 20, 60
APPS_FILE = Path(__file__).resolve().parents[1] / 'config' / 'vc_apps.toml'


@dataclass(frozen=True)
class Holder:
    key: str            # the registry key: a Store app's name, or a program's path with '#' for '\'
    name: str           # the Store app's name, or the program's file name
    packaged: bool
    since: float        # when it started using the device, in time.time() seconds


@dataclass
class Call:
    key: str
    app_id: str
    name: str           # what MWB calls it in messages: "Teams", "Brave"
    policy: str         # record | ask | never
    personal: bool
    since: float
    title: str = ''     # from a meeting tab or window, when there is one
    camera: bool = False
    released_at: float | None = None
    extra: dict = field(default_factory=dict)


def _filetime(v):
    return (v - 116444736000000000) / 1e7 if v else 0.0


def holders(device='microphone'):
    """Every app using the device right now."""
    found = []
    base = f'{CONSENT}\\{device}'
    for path, packaged in ((base, True), (base + r'\NonPackaged', False)):
        try:
            root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            continue
        with root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                key = winreg.EnumKey(root, i)
                if key == 'NonPackaged':
                    continue
                try:
                    with winreg.OpenKey(root, key) as k:
                        start = winreg.QueryValueEx(k, 'LastUsedTimeStart')[0]
                        stop = winreg.QueryValueEx(k, 'LastUsedTimeStop')[0]
                except OSError:
                    continue
                if start and stop == 0:
                    found.append(Holder(key, key if packaged else key.split('#')[-1], packaged, _filetime(start)))
    return found


def own_keys():
    """MWB's own process, as the registry would name it, so its recording and dictation never look like a call."""
    names = {sys.executable}
    buf, size = ctypes.create_unicode_buffer(520), wt.DWORD(520)
    if kernel32.QueryFullProcessImageNameW(kernel32.GetCurrentProcess(), 0, buf, ctypes.byref(size)):
        names.add(buf.value)
    return {n.replace('\\', '#').lower() for n in names}


EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def window_titles(exe_names):
    """Visible window titles of every process with one of these file names."""
    wanted = {e.lower() for e in exe_names}
    titles, names = [], {}

    def each(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if not n:
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in names:
            name = ''
            h = kernel32.OpenProcess(0x1000, False, pid.value)
            if h:
                b, s = ctypes.create_unicode_buffer(520), wt.DWORD(520)
                if kernel32.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(s)):
                    name = b.value.rsplit('\\', 1)[-1].lower()
                kernel32.CloseHandle(h)
            names[pid.value] = name
        if names[pid.value] in wanted:
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, b, n + 1)
            titles.append(b.value)
        return True

    user32.EnumWindows(EnumWindowsProc(each), 0)
    return titles


def _clean_title(title, marker):
    t = title.replace(marker, '')
    for junk in (' - Brave', ' - Google Chrome', ' - Microsoft Edge', ' — Mozilla Firefox', ' - Personal',
                 ' - Work', ' - Microsoft​ Edge', '| Microsoft Teams'):
        t = t.replace(junk, '')
    return t.strip(' -|–')


class Apps:
    def __init__(self, path=APPS_FILE, choices=None):
        with open(path, 'rb') as f:
            data = tomllib.load(f)
        self.apps = data.get('app', [])
        self.browsers = {b.lower() for b in data.get('browsers', [])}
        self.not_calls = {n.lower() for n in data.get('not_calls', [])}
        self.choices = choices if choices is not None else {}     # app id -> policy you chose

    def _policy(self, app_id, default):
        return self.choices.get(app_id, default)

    def match(self, h, titles=window_titles):
        """(app id, name, policy, personal, title) for a holder; None for something that is never a call."""
        name = h.name.lower()
        if name in self.not_calls:
            return None
        for app in self.apps:
            if name in {n.lower() for n in app.get('packaged' if h.packaged else 'exe', [])}:
                title = ''
                if app.get('tabs') and app.get('exe'):          # the app's own window may name the meeting
                    for t in titles(app['exe']):
                        hit = next((m for m in app['tabs'] if m in t), None)
                        if hit:
                            title = _clean_title(t, hit)
                            break
                return (app['id'], app['name'], self._policy(app['id'], app['policy']), app.get('personal', False),
                        title)
        if not h.packaged and name in self.browsers:
            for t in titles([h.name]):
                for app in self.apps:
                    hit = next((m for m in app.get('tabs', []) if m in t), None)
                    if hit:
                        return (app['id'], f'{app["name"]} in {Path(h.name).stem.capitalize()}',
                                self._policy(app['id'], app['policy']), app.get('personal', False),
                                _clean_title(t, hit))
            app_id = f'browser:{name}'
            return app_id, Path(h.name).stem.capitalize(), self._policy(app_id, 'ask'), False, ''
        app_id = f'app:{name}'
        return app_id, Path(h.name).stem, self._policy(app_id, 'ask'), False, ''


class Detector:
    """poll() every 5 s returns [('start', Call) | ('end', Call)]."""

    def __init__(self, apps, own=None, read=holders, titles=window_titles):
        self.apps, self.own, self.read, self.titles = apps, own if own is not None else own_keys(), read, titles
        self.calls = {}

    def poll(self, now=None):
        now = time.time() if now is None else now
        events = []
        mic = [h for h in self.read('microphone') if h.key.lower() not in self.own]
        cam = {h.name.lower() for h in self.read('webcam')}
        live = {h.key for h in mic}
        for h in mic:
            call = self.calls.get(h.key)
            if call:
                call.released_at = None
                call.camera |= h.name.lower() in cam
                continue
            if now - h.since < START_AFTER_S:
                continue
            m = self.apps.match(h, self.titles)
            if m is None:
                continue
            app_id, name, policy, personal, title = m
            call = Call(h.key, app_id, name, policy, personal, h.since, title, h.name.lower() in cam)
            self.calls[h.key] = call
            events.append(('start', call))
        for key, call in list(self.calls.items()):
            if key in live:
                continue
            if call.released_at is None:
                call.released_at = now
            elif now - call.released_at >= END_AFTER_S:
                del self.calls[key]
                events.append(('end', call))
        return events
