"""A meeting end to end, without a call or a microphone: two WAV files play as the "me" and "them" lanes, taking
turns like a conversation. The real Meetings skill records them, whisper small transcribes the pieces, the lanes
are merged, and the transcript must be ready soon after the call ends (design P2: within 2 minutes).
Everything goes to a scratch database and folder; nothing touches your real history.

  .venv\\Scripts\\python.exe -I tests\\e2e_meeting.py <phrase folder from make_phrases.ps1> [--speed 1]"""
import argparse, logging, sys, tempfile, time, wave
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mwb import config, winapi                                  # noqa: E402
from mwb.audio.capture import FileSource                        # noqa: E402
from mwb.sensors import system                                  # noqa: E402
from mwb.sensors.meeting_detector import Call                   # noqa: E402
from mwb.skills import meeting                                  # noqa: E402
from mwb.store.db import Store                                  # noqa: E402


class FakeUI:
    def __init__(self):
        self.notes = []

    def post(self, fn):
        fn()

    def hotkey_name(self, name):
        return 'Ctrl+Alt+M'

    def set_recording(self, on):
        print('  recording', 'on' if on else 'off')

    def notify(self, m):
        self.notes.append(m)
        print('  notice:', m)


class SayYes:
    def ask_record(self, call, answer, note=''):
        print(f'  asked: {call.name} is using the microphone. Record? -> Record')
        answer('record')


def conversation(folder, out):
    """me: phrases 1, 3, 5 ...; them: 2, 4, 6 ...; each waits for the other, with 0.8 s between turns."""
    phrases = sorted(Path(folder).glob('phrase-*.wav'))[:12]
    lanes = {'me': array('h'), 'them': array('h')}
    rate = 48000
    for i, p in enumerate(phrases):
        with wave.open(str(p)) as w:
            rate = w.getframerate()
            a = array('h', w.readframes(w.getnframes()))
        talker, other = ('me', 'them') if i % 2 == 0 else ('them', 'me')
        gap = array('h', bytes(2 * int(0.8 * rate)))
        lanes[talker].extend(a + gap)
        lanes[other].extend(array('h', bytes(2 * len(a))) + gap)
    paths = {}
    for name, data in lanes.items():
        paths[name] = out / f'{name}.wav'
        with wave.open(str(paths[name]), 'wb') as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
            w.writeframes(data.tobytes())
    return paths, len(lanes['me']) / rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--speed', type=float, default=1.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='  %(name)s: %(message)s', stream=sys.stdout)
    tmp = Path(tempfile.mkdtemp())
    meeting.AUDIO = tmp / 'audio'
    paths, seconds = conversation(args.folder, tmp)
    print(f'conversation: {seconds:.0f} s, 12 turns; {winapi.free_gb():.1f} GB free; '
          f'{"mains" if system.on_mains() else "battery: transcription waits for the end of the call"}')
    cfg = config.load()
    store = Store(tmp / 'mwb.db')
    ui = FakeUI()
    sources = {name: FileSource(p, speed=args.speed) for name, p in paths.items()}
    m = meeting.Meetings(cfg, store, ui, SayYes(), sources)
    call = Call('test', 'teams', 'Teams', 'record', False, time.time(), title='Sprint review (test)')
    m.detector.calls['test'] = call
    m._decide(call)
    mid = m.current[0]
    while not all(s.done.is_set() for s in sources.values()):
        time.sleep(0.5)
    t_end = time.monotonic()
    m.stop('the test call ended')
    while store.meeting(mid)['status'] != 'ready' and time.monotonic() - t_end < 900:
        time.sleep(1)
    took = time.monotonic() - t_end
    mt = store.meeting(mid)
    print(f'\nstatus {mt["status"]} {took:.0f} s after the call ended (pass: 120 s or less); '
          f'{mt["pieces_done"]}/{mt["pieces"]} pieces; language {mt["language"]}')
    for _, sp, st, en, text in store.segments(mid):
        print(f'  [{st:5.1f}] {sp:4}: {text}')
    left = list(meeting.AUDIO.glob('**/*.wav'))
    print(f'audio left on disk: {len(left)} files (pass: 0)')
    m.close()


if __name__ == '__main__':
    main()
