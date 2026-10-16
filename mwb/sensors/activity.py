"""Time per app and project for the journal (design §9.6, JNL-2): every 10 s, the program in front and the project
its window title points to. The title is read only to find the project and is never stored or logged. Five minutes
without keyboard or mouse, or a locked screen, counts as away. Apps and titles on the denylist are kept as
"Private" with no app name, and nothing is recorded while MWB is paused.

Consecutive samples with the same app and project make one row, so a day is a few hundred rows; a row's end time
is written at most once a minute. Call tick() from the core's loop."""
import ctypes, ctypes.wintypes as wt, datetime, fnmatch, logging, re, time

from mwb import winapi
from mwb.winapi import user32

log = logging.getLogger('mwb.activity')
IDLE_S = 300
SAVE_S = 60
EDITORS = {'code.exe', 'cursor.exe', 'code - insiders.exe', 'windsurf.exe'}       # "file - folder - Visual Studio Code"
IDES = {'idea64.exe', 'pycharm64.exe', 'webstorm64.exe', 'rider64.exe', 'studio64.exe', 'goland64.exe',
        'clion64.exe', 'devenv.exe', 'sublime_text.exe', 'notepad++.exe', 'eclipse.exe'}
MAIL = {'outlook.exe', 'olk.exe', 'hxoutlook.exe', 'thunderbird.exe'}
CHAT = {'ms-teams.exe', 'teams.exe', 'slack.exe', 'whatsapp.exe', 'whatsapp.root.exe', 'telegram.exe',
        'discord.exe', 'zoom.exe', 'webex.exe'}
BROWSERS = {'msedge.exe', 'chrome.exe', 'brave.exe', 'firefox.exe', 'opera.exe', 'vivaldi.exe', 'arc.exe'}
TERMINALS = {'windowsterminal.exe', 'conhost.exe', 'cmd.exe', 'powershell.exe', 'pwsh.exe', 'mintty.exe',
             'wezterm-gui.exe', 'alacritty.exe'}
AWAY_APPS = {'', 'lockapp.exe', 'logonui.exe'}


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', wt.UINT), ('dwTime', wt.DWORD)]


def idle_seconds():
    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000


def _title(hwnd):
    buf = ctypes.create_unicode_buffer(300)
    user32.GetWindowTextW(hwnd, buf, 300)
    return buf.value


def project_of(app, title, repos=(), deny=()):
    """(app to keep, project) for one sample. repos: repository names, longest first."""
    a, t = app.lower(), title.lower()
    if any(fnmatch.fnmatch(a, d) or fnmatch.fnmatch(t, d) for d in deny):
        return '', 'Private'
    for name in repos:
        if re.search(rf'(?<![\w-]){re.escape(name.lower())}(?![\w-])', t):
            return app, name
    if a in EDITORS:
        parts = [p.strip() for p in title.split(' - ')]
        return app, (parts[-2] if len(parts) >= 3 else 'Coding')
    if a in IDES:
        return app, 'Coding'
    if a in MAIL or (a in BROWSERS and re.search(r'\boutlook\b|\bmail\b|gmail|inbox', t)):
        return app, 'Email'
    if a in CHAT or (a in BROWSERS and re.search(r'\bteams\b|slack|whatsapp', t)):
        return app, 'Chat'
    if a in BROWSERS:
        return app, 'Browsing'
    if a in TERMINALS:
        return app, 'Terminal'
    return app, 'Other'


class ActivityWatch:
    def __init__(self, store, cfg):
        j = cfg['journal']
        self.store = store
        self.every = max(2, int(j['activity_sample_s']))
        self.deny = [d.lower() for d in j['denylist']]
        self.repos = []                     # repository names, set by the journal once it has scanned
        self.cur = None                     # {'id', 'key', 'start', 'last', 'saved'}
        self.next = 0.0

    def set_repos(self, names):
        self.repos = sorted(set(names), key=len, reverse=True)

    def tick(self, now, paused=False):
        if now < self.next:
            return
        self.next = now + self.every
        if paused:
            self.flush()
            self.cur = None
            return
        try:
            self.sample(datetime.datetime.now())
        except Exception:
            log.exception('activity sample failed')

    def sample(self, t):
        hwnd, app = winapi.foreground_app()
        away = idle_seconds()
        if away >= IDLE_S or app.lower() in AWAY_APPS:
            key, start = ('', '', 1), t - datetime.timedelta(seconds=away if away >= IDLE_S else 0)
        else:
            keep, project = project_of(app, _title(hwnd), self.repos, self.deny)
            key, start = (keep, project, 0), t
        c = self.cur
        if c and key == c['key'] and (t - c['last']).total_seconds() <= 3 * self.every:
            c['last'] = t
            if (t - c['saved']).total_seconds() >= SAVE_S:
                self._save_end()
            return
        if c and key[2] and start < c['last']:          # the 5 minutes before going away were away, too
            c['last'] = max(c['start'], start)
        self.flush()
        start = max(start, c['last']) if c else start
        rid = self.store.run('INSERT INTO activity (started, ended, app, project, idle) VALUES (?, ?, ?, ?, ?)',
                             (start.isoformat(timespec='seconds'), t.isoformat(timespec='seconds'), *key))
        self.cur = {'id': rid, 'key': key, 'start': start, 'last': t, 'saved': t}

    def _save_end(self):
        c = self.cur
        self.store.run('UPDATE activity SET ended = ? WHERE id = ?', (c['last'].isoformat(timespec='seconds'), c['id']))
        c['saved'] = c['last']

    def flush(self):
        if self.cur:
            self._save_end()
