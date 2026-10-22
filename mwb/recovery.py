"""Crash recovery (Phase 5). The core writes %LOCALAPPDATA%\\MWB\\run.json when it starts and removes it when it
stops cleanly. Only one core can run at a time, so a file still there at the next start means the last run ended
without shutting down: a crash, the process being ended, or the laptop losing power.

What carries on by itself after a crash: a call that was being recorded is transcribed from the pieces already on
disk (skills/meeting.py), notes that were waiting are written (skills/notes.py), and a journal missed at 18:30 is
written later (skills/journal.py). A dictation that was in progress is lost: its audio was only in memory."""
import datetime, json, logging, os

from mwb import __version__, config

log = logging.getLogger('mwb.recovery')
RUN = config.LOCAL / 'run.json'


def begin():
    """The last run's {'pid', 'started', 'version'} if it didn't stop cleanly, else None; then mark this run."""
    last = None
    if RUN.exists():
        try:
            last = json.loads(RUN.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            last = {}
    RUN.parent.mkdir(parents=True, exist_ok=True)
    RUN.write_text(json.dumps({'pid': os.getpid(), 'version': __version__,
                               'started': datetime.datetime.now().isoformat(timespec='seconds')}), encoding='utf-8')
    return last


def end():
    try:
        RUN.unlink()
    except OSError:
        pass


def message(last, recovered_meetings=0):
    """A plain sentence for the tray after a crash."""
    when = ''
    if last and last.get('started'):
        when = f' (it had been running since {datetime.datetime.fromisoformat(last["started"]):%a %H:%M})'
    extra = (f' {recovered_meetings} interrupted call{"s are" if recovered_meetings != 1 else " is"} being '
             f'transcribed from what was recorded.' if recovered_meetings else '')
    return f'MWB stopped unexpectedly last time{when} and has started again.{extra}'
