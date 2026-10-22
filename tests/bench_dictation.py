"""Phase 1 check without a microphone: plays the synthetic phrases from make_phrases.ps1 through the real dictation
path (pieces, speech worker, clean-up) and reports finish-to-text and word errors. Insertion is recorded, not pasted,
so nothing lands in your windows; tests/test_paste.py covers pasting.

  .venv\\Scripts\\python.exe -I tests\\bench_dictation.py <folder of phrase-NN.wav> [--joined]

--joined plays three phrases back to back with 0.7 s pauses (about 10 s of speech), which is where transcribing
while you talk matters: at the finish only the last piece is left. Pass (design P1): median finish-to-text 1.0 s."""
import argparse, logging, re, statistics, sys, tempfile, time, wave
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mwb import config, insert, winapi                                  # noqa: E402
from mwb.audio.capture import FileSource                                # noqa: E402
from mwb.skills import cleanup                                          # noqa: E402
from mwb.skills.dictate import Dictation                                # noqa: E402
from mwb.supervisor import SpeechWorker                                 # noqa: E402

HERE = Path(__file__).parent


class QuietUI:
    def __init__(self):
        self.states = []

    def set_state(self, s):
        self.states.append(s)

    def set_level(self, x):
        pass

    def set_words(self, w):
        pass

    def notify(self, m):
        print('notify:', m)


NUMBERS = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8',
           'nine': '9', 'ten': '10', 'thirty': '30', 'gigabyte': 'gb', 'gigabytes': 'gb'}


def words(t):
    """Words for counting errors: case, punctuation and number formats ("ten" or "10") don't count."""
    t = re.sub(r'(\d)([a-z])', r'\1 \2', t.lower().replace('-', ' ').replace('.', ' '))
    return [NUMBERS.get(w, w) for w in re.sub(r"[^a-z0-9' ]+", ' ', t).split()]


def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)], len(r)


def power():
    import ctypes

    class SPS(ctypes.Structure):
        _fields_ = [('ac', ctypes.c_ubyte), ('flag', ctypes.c_ubyte), ('pct', ctypes.c_ubyte), ('saver', ctypes.c_ubyte),
                    ('life', ctypes.c_ulong), ('full', ctypes.c_ulong)]
    s = SPS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
    return 'on mains power' if s.ac == 1 else f'on battery ({s.pct} %): expect about half the speed'


def trim(path, out, lead_s=0.3, tail_s=0.05):
    """The voice file without its long silences: speech ends tail_s before the file does, like a real release."""
    with wave.open(str(path)) as w:
        rate = w.getframerate()
        data = array('h', w.readframes(w.getnframes()))
    win = rate // 100
    loud = [i for i in range(0, len(data) - win, win) if max(map(abs, data[i:i + win])) > 600]
    a, b = max(0, loud[0] - int(lead_s * rate)), min(len(data), loud[-1] + win + int(tail_s * rate))
    with wave.open(str(out), 'wb') as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(data[a:b].tobytes())
    return out


def join_wavs(paths, gap_s, out):
    rate, data = None, array('h')
    for p in paths:
        with wave.open(str(p)) as w:
            rate = w.getframerate()
            data.extend(array('h', w.readframes(w.getnframes())))
        data.extend([0] * int(rate * gap_s))
    with wave.open(str(out), 'wb') as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(data.tobytes())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--joined', action='store_true')
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format='%(name)s %(message)s')
    cfg = config.load()
    refs = [l.strip() for l in (HERE / 'phrases.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
    tmp = Path(tempfile.mkdtemp())
    wavs = [trim(w, tmp / w.name) for w in sorted(Path(args.folder).glob('phrase-*.wav'))]
    dictionary = cleanup.load_dictionary(config.dictionary_files())
    cases = [(w, cleanup.clean([refs[i]], dictionary)) for i, w in enumerate(wavs)]     # what should come out
    if args.joined:
        cases = [(join_wavs([c[0] for c in cases[i:i + 3]], 0.7, tmp / f'joined-{i:02d}.wav'),
                  ' '.join(c[1] for c in cases[i:i + 3])) for i in range(0, len(cases) - 2, 3)]

    inserted = []
    insert.insert = lambda text, *a, **k: inserted.append(text) or 'recorded'     # never paste during the bench
    worker = SpeechWorker(cfg)
    print(f'free memory {winapi.free_gb():.1f} GB; {power()}; starting the speech worker ...')
    t0 = time.perf_counter()
    if not worker.ensure('bench') or not worker.wait_ready(120):
        sys.exit(f'speech worker failed: {worker.failed}')
    print(f'ready in {time.perf_counter() - t0:.1f} s')
    lat, errs, total = [], 0, 0
    try:
        for wav, ref in cases:
            src = FileSource(wav, speed=1.0, then_silence_s=0.25)
            d = Dictation(cfg, worker, src, QuietUI(), None, dictionary)
            d.start('hold', 'bench')
            src.done.wait(60)
            d.finish('bench')                  # like letting go of the keys right after the last word
            while d.active:
                time.sleep(0.01)
            r = d.last
            e, n = wer(ref, r['text'])
            errs, total = errs + e, total + n
            lat.append(r['latency_ms'])
            print(f'{r["audio_s"]:5.1f} s audio  {r["pieces"]} piece(s)  finish-to-text {r["latency_ms"]:5d} ms  '
                  f'errors {e}/{n}  {r["text"]!r}')
    finally:
        worker.stop('bench done')
    print(f'\nfinish-to-text: median {statistics.median(lat):.0f} ms, best {min(lat)} ms, worst {max(lat)} ms '
          f'over {len(lat)} dictations; word errors {errs}/{total} = {100 * errs / max(total, 1):.1f} %')
    print('pass' if statistics.median(lat) <= 1000 else 'NOT YET: the design wants a median of 1000 ms or less')


if __name__ == '__main__':
    main()
