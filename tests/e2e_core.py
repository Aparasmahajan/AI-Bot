"""End to end through the real core: MWB starts with a WAV file in place of the mic (MWB_TEST_AUDIO), a double tap
of Caps Lock is sent, and the dictated text must arrive in a small test window of this script's own. Nothing goes
into your apps, and no microphone is opened.

  .venv\\Scripts\\python.exe -I tests\\e2e_core.py <phrase folder from make_phrases.ps1>

Quit any running MWB first (Ctrl+Alt+Shift+W)."""
import ctypes, os, subprocess, sys, tempfile, time, tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mwb import config, winapi                                          # noqa: E402
from tests.bench_dictation import join_wavs, wer                        # noqa: E402

LOG = config.LOCAL / 'logs' / 'mwb.log'


def keys(*strokes, gap=0.0):
    for s in strokes:
        winapi.send_keys(*s)
        time.sleep(gap)


def main():
    folder = Path(sys.argv[1])
    refs = [l.strip() for l in (ROOT / 'tests' / 'phrases.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
    wav = join_wavs(sorted(folder.glob('phrase-*.wav'))[:3], 0.7, Path(tempfile.mkdtemp()) / 'e2e.wav')
    ref = ' '.join(refs[:3])
    caps_before = winapi.caps_on()
    start_line = len(LOG.read_text(encoding='utf-8').splitlines()) if LOG.exists() else 0
    env = dict(os.environ, MWB_TEST_AUDIO=str(wav))
    core = subprocess.Popen([str(ROOT / '.venv' / 'Scripts' / 'pythonw.exe'), '-m', 'mwb'], cwd=ROOT, env=env)

    root = tk.Tk()
    root.title('MWB end-to-end test')
    root.geometry('520x160+40+40')
    root.attributes('-topmost', True)
    text = tk.Text(root, wrap='word')
    text.pack(fill='both', expand=True)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and 'starting (' not in ''.join(LOG.read_text(encoding='utf-8').splitlines()[start_line:]):
        root.update()
        time.sleep(0.1)
    time.sleep(2)
    hwnd = int(root.wm_frame(), 16)
    winapi.send_keys((winapi.VK_MENU, False), (winapi.VK_MENU, True))
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    root.focus_force()
    text.focus_set()
    for _ in range(20):
        root.update()
        time.sleep(0.02)
    if winapi.user32.GetForegroundWindow() != hwnd:
        print('SKIPPED: the test window could not come to the front')
    else:
        caps = winapi.VK_CAPITAL
        keys([(caps, False)], [(caps, True)], [(caps, False)], [(caps, True)], gap=0.07)     # the double tap
        t0 = time.monotonic()
        while time.monotonic() - t0 < 120 and not text.get('1.0', 'end-1c').strip():
            root.update()
            time.sleep(0.02)
        for _ in range(30):
            root.update()
            time.sleep(0.02)
        got = text.get('1.0', 'end-1c')
        e, n = wer(ref, got)
        print(f'arrived after {time.monotonic() - t0:.1f} s (includes {wav.stat().st_size / 96000:.1f} s of audio '
              f'and loading the speech worker if it was not running)')
        print(f'text: {got!r}')
        print(f'word errors {e}/{n}; Caps Lock {"unchanged" if winapi.caps_on() == caps_before else "CHANGED"}')
    root.destroy()
    keys([(winapi.VK_CONTROL, False), (winapi.VK_MENU, False), (winapi.VK_SHIFT, False), (0x57, False), (0x57, True),
          (winapi.VK_SHIFT, True), (winapi.VK_MENU, True), (winapi.VK_CONTROL, True)])      # Ctrl+Alt+Shift+W quits
    try:
        core.wait(15)
    except subprocess.TimeoutExpired:
        core.kill()
    print('\ncore log:')
    for line in LOG.read_text(encoding='utf-8').splitlines()[start_line:]:
        print(' ', line[11:])


if __name__ == '__main__':
    main()
