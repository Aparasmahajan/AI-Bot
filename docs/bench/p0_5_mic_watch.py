"""P0-5: which apps hold the microphone, matched against the vc_apps rules in design §9.3.
Reads Windows' mic-usage keys (HKCU ConsentStore\\microphone): no admin rights, no extra libraries.
For a browser holder it also reads that browser's window titles, which show the active tab.

  py -3.14 -I p0_5_mic_watch.py            snapshot: every app that has ever used the mic, with times
  py -3.14 -I p0_5_mic_watch.py --watch    check every 5 s and print each start and stop (Ctrl+C ends)

--watch also appends to %LOCALAPPDATA%\\MWB\\p0\\p0-5-calls.csv, outside the Git folder, because window
titles can hold meeting names. Join a short call in each app you use and note what it prints."""
import csv, ctypes, ctypes.wintypes as wt, datetime, os, sys, time, winreg

MIC = r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone'

# The vc_apps.yaml excerpt from design §9.3. P0-5 confirms or corrects these names.
VC_APPS = [
    {'id': 'teams', 'packaged': ['MSTeams_8wekyb3d8bbwe'], 'exe': ['ms-teams.exe'], 'tabs': ['| Microsoft Teams'], 'policy': 'record'},
    {'id': 'zoom', 'exe': ['Zoom.exe'], 'tabs': ['Zoom'], 'policy': 'record'},
    {'id': 'meet', 'tabs': ['Meet –', 'Meet -'], 'policy': 'record'},
    {'id': 'webex', 'exe': ['Webex.exe', 'CiscoCollabHost.exe'], 'tabs': ['Webex'], 'policy': 'record'},
    {'id': 'slack', 'exe': ['slack.exe'], 'policy': 'ask'},
    {'id': 'whatsapp', 'packaged': ['5319275A.WhatsAppDesktop_cv1g1gvanyjgm'], 'tabs': ['WhatsApp'], 'policy': 'ask', 'personal': True},
    {'id': 'discord', 'exe': ['Discord.exe'], 'policy': 'ask', 'personal': True},
    {'id': 'telegram', 'packaged': ['TelegramMessengerLLP.TelegramDesktop_t4vj0pshhgkwm'], 'exe': ['Telegram.exe'], 'policy': 'ask', 'personal': True},
    {'id': 'phonelink', 'packaged': ['Microsoft.YourPhone_8wekyb3d8bbwe'], 'exe': ['PhoneExperienceHost.exe'], 'policy': 'ask', 'personal': True},
]
BROWSERS = ['chrome.exe', 'msedge.exe', 'brave.exe', 'firefox.exe', 'opera.exe', 'vivaldi.exe']
NOT_CALLS = ['Wispr Flow.exe', 'Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe']


def filetime(v):
    if not v:
        return None
    return datetime.datetime.fromtimestamp((v - 116444736000000000) / 1e7)   # FILETIME (UTC) -> local


def mic_usage():
    """Yield (name, packaged, start, stop) for every app Windows has recorded using the mic."""
    for path, packaged in ((MIC, True), (MIC + r'\NonPackaged', False)):
        try:
            root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            continue
        with root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                name = winreg.EnumKey(root, i)
                if name == 'NonPackaged':
                    continue
                with winreg.OpenKey(root, name) as k:
                    try:
                        start = winreg.QueryValueEx(k, 'LastUsedTimeStart')[0]
                        stop = winreg.QueryValueEx(k, 'LastUsedTimeStop')[0]
                    except FileNotFoundError:
                        continue
                # desktop apps are keyed by exe path with "#" for "\"; keep the exe name
                yield (name if packaged else name.split('#')[-1]), packaged, start, stop


def window_titles(exe):
    """Visible top-level window titles of every process with this exe name."""
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    titles = []

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if not n:
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = kernel32.OpenProcess(0x1000, False, pid.value)      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return True
        buf, size = ctypes.create_unicode_buffer(260), wt.DWORD(260)
        ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        kernel32.CloseHandle(h)
        if ok and os.path.basename(buf.value).lower() == exe.lower():
            t = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, t, n + 1)
            titles.append(t.value)
        return True

    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(callback)
    user32.EnumWindows(proc, 0)
    return titles


def classify(name, packaged, live=True):
    """Return (app id, policy, detail) for one mic holder. Browser tabs only count while live."""
    if name in NOT_CALLS:
        return 'not-a-call', '-', 'dictation or recorder'
    for app in VC_APPS:
        if name in app.get('packaged' if packaged else 'exe', []):
            return app['id'], app['policy'] + (' (personal)' if app.get('personal') else ''), ''
    if not packaged and name.lower() in BROWSERS:
        if not live:
            return 'browser', 'needs a meeting tab', ''
        for title in window_titles(name):
            for app in VC_APPS:
                if any(tab in title for tab in app.get('tabs', [])):
                    return app['id'] + ' (browser)', app['policy'], title
        return 'browser, no meeting tab seen', 'ask after 20 s', ''
    return 'unknown', 'ask after 20 s', ''


def snapshot():
    rows = sorted(mic_usage(), key=lambda r: r[2] or 0, reverse=True)
    print(f'{"App":<55} {"Kind":<9} {"Last start":<17} {"Last stop":<17} Match')
    for name, packaged, start, stop in rows:
        s = filetime(start)
        when = s.strftime('%Y-%m-%d %H:%M') if s else 'never'
        end = 'IN USE NOW' if start and stop == 0 else (filetime(stop).strftime('%Y-%m-%d %H:%M') if stop else '')
        app, policy, _ = classify(name, packaged, live=(stop == 0)) if start else ('', '', '')
        print(f'{name[:55]:<55} {"packaged" if packaged else "desktop":<9} {when:<17} {end:<17} {app} {policy}')


def watch():
    folder = os.path.join(os.environ['LOCALAPPDATA'], 'MWB', 'p0')
    os.makedirs(folder, exist_ok=True)
    log = os.path.join(folder, 'p0-5-calls.csv')
    print('Watching the microphone every 5 s. Leave this window open during your calls; Ctrl+C to stop.')
    print('Each app that starts or stops using the mic appears below as a START or STOP line.\n')
    holding = {}                                   # name -> start time we first saw it
    try:
        while True:
            now = datetime.datetime.now()
            current = {name: packaged for name, packaged, start, stop in mic_usage() if start and stop == 0}
            for name, packaged in current.items():
                if name not in holding:
                    holding[name] = now
                    app, policy, title = classify(name, packaged)
                    event = ('start', name, app, policy, title)
                    print(f'{now:%H:%M:%S}  START  {name}  ->  {app}, {policy}  {title}')
                    with open(log, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow([now.isoformat(timespec='seconds'), *event])
            for name in list(holding):
                if name not in current:
                    held = (now - holding.pop(name)).total_seconds()
                    print(f'{now:%H:%M:%S}  STOP   {name}  after {held:.0f} s'
                          + ('   (under 20 s: MWB would ignore this)' if held < 20 else ''))
                    with open(log, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow([now.isoformat(timespec='seconds'), 'stop', name, f'{held:.0f}s', '', ''])
            time.sleep(5)
    except KeyboardInterrupt:
        print(f'\nLog: {log.replace(os.environ["USERPROFILE"], "%USERPROFILE%")}')


if __name__ == '__main__':
    args = [a.rstrip(':;.,') for a in sys.argv[1:]]          # forgive "--watch:" and similar
    if any(a not in ('--watch', '-w', 'watch') for a in args):
        sys.exit(f'Unknown option {sys.argv[1]!r}. Use no option for a snapshot, or --watch.')
    if args:
        watch()
    else:
        snapshot()
        print('\nThis was a snapshot. To keep watching during calls, add --watch.')
