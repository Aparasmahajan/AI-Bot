"""Build a portable MWB folder (Phase 5): Python, MWB's approved libraries and MWB itself, ready to copy to another
laptop and start with "Start MWB.cmd". Nothing is downloaded: it copies the Python that .venv was made from (its
standard library, without the test suite) and the libraries already in .venv, pinned by requirements.txt.

What does not travel, because it is not MWB's: the speech engine's environment and whisper-cli (both from AI-App),
the whisper and Qwen model files, and llama.cpp. Their paths are settings; on a new laptop the setup screen lists
what is missing, and MWB asks before anything is downloaded. Your settings (%APPDATA%\\MWB) and history
(%LOCALAPPDATA%\\MWB\\mwb.db) travel only if you copy them yourself.

  .venv\\Scripts\\python.exe tools\\build_portable.py [destination] [--replace]
      default destination: dist\\MWB-portable. --replace moves an existing one to the Recycle Bin first."""
import os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = shutil.ignore_patterns('__pycache__', '*.pyc', '*.pdb', 'test', 'tests', 'idle_test', 'Doc', '*.chm')
START = r'''@echo off
rem Starts MWB from this portable folder, through its watchdog. Settings live in %APPDATA%\MWB, as on any laptop.
cd /d "%~dp0"
set PYTHONNOUSERSITE=1
start "" "%~dp0python\pythonw.exe" -m mwb.watchdog
'''
KEY = r'''@echo off
rem Opens the window for MWB's API key (kept in Windows Credential Manager, never in a file).
cd /d "%~dp0"
set PYTHONNOUSERSITE=1
start "" "%~dp0python\pythonw.exe" -m mwb.ui.api_key
'''
README = '''MWB, portable
=============

Copy this folder anywhere and double-click "Start MWB.cmd". On a new laptop MWB looks at the hardware, suggests an
effort level and opens the setup screen, which lists anything missing.

Not in this folder, because it is not part of MWB:
- the speech engine's environment and whisper-cli, from AI-App;
- the model files: whisper small (%LOCALAPPDATA%\\MWB\\models) and Qwen3.5 (%USERPROFILE%\\Tools\\llamacpp);
- llama.cpp.
Their paths are in Settings (tray menu). MWB never downloads them by itself.

To bring your own things along, copy:
- %APPDATA%\\MWB                for your settings and dictionary;
- %LOCALAPPDATA%\\MWB\\mwb.db    for your history, if you want it;
- Documents\\MWB\\journal        for your journals.
Your API key does not travel: set it again with "Set API key.cmd".

Built {when} from MWB {version}, Python {python}.
'''


def size_of(folder):
    return sum(f.stat().st_size for f in Path(folder).rglob('*') if f.is_file())


def main(argv):
    replace = '--replace' in argv
    args = [a for a in argv if not a.startswith('--')]
    dest = Path(args[0]) if args else ROOT / 'dist' / 'MWB-portable'
    base = Path(sys.base_prefix)
    venv_sp = Path(sys.prefix) / 'Lib' / 'site-packages'
    if sys.prefix == sys.base_prefix:
        sys.exit('Run this with .venv\\Scripts\\python.exe, so it knows which libraries MWB uses.')
    if dest.exists():
        if not replace:
            sys.exit(f'{dest} already exists. Add --replace to move it to the Recycle Bin and build again.')
        sys.path.insert(0, str(ROOT))
        from mwb import winapi
        if not winapi.recycle(dest):
            sys.exit(f'{dest} could not be moved to the Recycle Bin.')
    free = shutil.disk_usage(dest.parent if dest.parent.exists() else ROOT).free / 2 ** 30
    if free < 1.0:
        sys.exit(f'Only {free:.1f} GB free on that disk; the portable folder needs about 0.2 GB, and room to spare.')
    t0 = time.monotonic()
    print(f'Python from {base}')
    shutil.copytree(base, dest / 'python', ignore=lambda d, names: (
        set(SKIP(d, names)) | ({'site-packages'} if Path(d) == base / 'Lib' else set())))
    print('MWB\'s libraries from .venv')
    shutil.copytree(venv_sp, dest / 'python' / 'Lib' / 'site-packages', ignore=SKIP, dirs_exist_ok=True)
    print('MWB')
    shutil.copytree(ROOT / 'mwb', dest / 'mwb', ignore=SKIP)
    for name in ('requirements.txt', 'README.md'):
        shutil.copy2(ROOT / name, dest / name)
    sys.path.insert(0, str(ROOT))
    from mwb import __version__
    (dest / 'Start MWB.cmd').write_text(START, encoding='ascii')
    (dest / 'Set API key.cmd').write_text(KEY, encoding='ascii')
    (dest / 'README-portable.txt').write_text(README.format(
        when=time.strftime('%Y-%m-%d %H:%M'), version=__version__, python=sys.version.split()[0]), encoding='utf-8')
    print('Checking that it starts on its own…')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'VIRTUAL_ENV'))}
    env['PYTHONNOUSERSITE'] = '1'
    check = subprocess.run([str(dest / 'python' / 'python.exe'), '-c',
                            'import sys, mwb.app, mwb.ui.setup, mwb.ui.settings, PIL, pystray, comtypes, pyaudiowpatch; '
                            'print(sys.prefix)'], cwd=str(dest), env=env, capture_output=True, text=True, timeout=120)
    if check.returncode != 0 or Path(check.stdout.strip()).resolve() != (dest / 'python').resolve():
        sys.exit(f'The portable Python did not start cleanly:\n{check.stdout}{check.stderr}')
    print(f'Done in {time.monotonic() - t0:.0f} s: {dest} ({size_of(dest) / 2 ** 20:.0f} MB). It runs its own Python.')


if __name__ == '__main__':
    main(sys.argv[1:])
