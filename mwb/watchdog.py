"""The watchdog (Phase 5, crash recovery): "Start MWB.cmd" runs this small process, which starts the core and starts
it again if it crashes. It imports almost nothing, so it holds only a few MB, and it never touches your data.

What the core's exit code means:
  0   you quit MWB (or another MWB was already running): the watchdog ends too;
  3   the core asks to be started again, for example after you saved new settings: at once;
  any other code is a crash: started again after 2 s, at most 3 times in 10 minutes. After a fourth crash the
  watchdog stops and says so, so a broken setup can't loop forever.

  .venv\\Scripts\\pythonw.exe -m mwb.watchdog [--after PID]     (--after: wait for that process to end first)"""
import ctypes, datetime, os, subprocess, sys, time
from pathlib import Path

RESTART = 3
CRASHES, WINDOW_S = 3, 600
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
LOG = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'MWB' / 'logs' / 'watchdog.log'


def note(text):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(f'{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {text}\n')
    except OSError:
        pass


def wait_for(pid, timeout_s=30):
    h = kernel32.OpenProcess(0x00100000, False, pid)            # SYNCHRONIZE
    if h:
        kernel32.WaitForSingleObject(h, int(timeout_s * 1000))
        kernel32.CloseHandle(h)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--after' in argv:
        wait_for(int(argv[argv.index('--after') + 1]))
    kernel32.CreateMutexW(None, False, 'Local\\MWB.watchdog')
    if ctypes.get_last_error() == 183:                          # a watchdog is already looking after MWB
        return 0
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, MWB_WATCHDOG='1')
    crashes = []
    while True:
        code = subprocess.Popen([sys.executable, '-m', 'mwb'], cwd=str(root), env=env).wait()
        if code == 0:
            return 0
        if code == RESTART:
            note('restart asked for by the core')
            continue
        now = time.monotonic()
        crashes = [t for t in crashes if now - t < WINDOW_S] + [now]
        note(f'the core stopped unexpectedly (exit code {code & 0xFFFFFFFF:#x}); crash {len(crashes)} in 10 minutes')
        if len(crashes) > CRASHES:
            note('not starting it again')
            ctypes.windll.user32.MessageBoxW(
                None, 'MWB stopped unexpectedly 4 times in 10 minutes, so it was not started again.\n\nThe log folder, '
                f'{LOG.parent}, has the details. Start MWB again when you are ready.', 'MWB', 0x30)
            return 1
        time.sleep(2)


if __name__ == '__main__':
    sys.exit(main())
