"""Voice activity and cutting into pieces (design §9.1), ported from AI-App's adaptive VAD (src/renderer/app.js).

The speech threshold follows the room: a frame is speech when it is 3 times louder than the learned noise floor.
A pause of 500 ms or more closes a piece, so it can be transcribed while you keep talking; a piece never grows past
10 s, and a long run of speech is cut at its quietest frame instead of mid-word. Pure Python on 16-bit samples:
math.sumprod does the arithmetic in C, so the core never needs numpy."""
import math
from array import array
from dataclasses import dataclass

FRAME_S = 0.064            # 64 ms frames: fine enough not to clip word edges
MIN_THRESHOLD = 0.0015     # floor for the adaptive threshold (near-silent input)
NOISE_RATIO = 3.0          # speech = this many times louder than the noise floor
MIN_SPEECH_S = 0.25        # ignore blips shorter than this
PREROLL_S = 0.4            # audio kept from before the speech starts, so the first sound isn't clipped
TAIL_S = 0.2               # silence kept after the last word of a piece; the rest isn't worth transcribing
SPLIT_SEARCH_S = 3.0       # a piece at its length limit is cut at the quietest frame this far back
TARGET_RMS = 0.08          # each piece's speech is levelled to about -22 dBFS ...
MAX_GAIN = 20.0            # ... but quiet input is never boosted more than this


def level(samples):
    """RMS of 16-bit samples, 0..1."""
    return math.sqrt(math.sumprod(samples, samples) / len(samples)) / 32768.0 if samples else 0.0


@dataclass
class Frame:
    samples: array
    level: float
    speech: bool


@dataclass
class Piece:
    samples: array          # mono 16-bit at the capture rate
    rate: int
    gain: float             # applied by the speech worker
    start_s: float          # from the start of the dictation
    seconds: float
    speech_s: float


class Segmenter:
    """Dictation: pause_ms=500, max_s=10. Meetings: whisper always works on a 30 s window, so short pieces cost as much
    as long ones; there a pause closes a piece only once it is min_s long, or after long_pause_s of silence."""

    def __init__(self, rate, pause_ms=500, max_s=10.0, min_s=0.0, long_pause_s=None):
        self.rate, self.pause_s, self.max_s = rate, pause_ms / 1000, max_s
        self.min_s, self.long_pause_s = min_s, long_pause_s
        self.frame_n = int(rate * FRAME_S)
        self.noise_floor = 0.002
        self.frames, self.speech_s, self.silence_s = [], 0.0, 0.0
        self.t = 0.0                    # seconds of audio seen
        self.piece_start = 0.0
        self.last_speech_at = None      # seconds into the dictation; None until someone speaks
        self.total_speech_s = 0.0
        self.meter = 0.0                # 0..1 for the indicator
        self._pending = array('h')

    def feed(self, samples):
        """Add mono 16-bit samples of any length; returns the pieces that closed."""
        self._pending.extend(samples)
        out = []
        while len(self._pending) >= self.frame_n:
            frame = self._pending[:self.frame_n]
            del self._pending[:self.frame_n]
            piece = self._frame(frame)
            if piece:
                out.append(piece)
        return out

    def _frame(self, samples):
        lv = level(samples)
        speech = lv >= max(MIN_THRESHOLD, self.noise_floor * NOISE_RATIO)
        # Noise floor: drop fast to quieter frames, creep up slowly otherwise, so speech barely moves it
        # but a fan switching on is learned in seconds.
        self.noise_floor = (self.noise_floor * 0.9 + lv * 0.1 if lv < self.noise_floor
                            else self.noise_floor * 0.998 + lv * 0.002)
        db = 20 * math.log10(max(lv, 1e-5) / max(self.noise_floor, 1e-4))
        self.meter = min(1.0, max(0.0, db / 30))
        self.frames.append(Frame(samples, lv, speech))
        self.t += FRAME_S
        if speech:
            self.speech_s += FRAME_S
            self.total_speech_s += FRAME_S
            self.silence_s = 0.0
            self.last_speech_at = self.t
        else:
            self.silence_s += FRAME_S

        if self.speech_s == 0:          # before any speech, keep only the pre-roll
            keep = math.ceil(PREROLL_S / FRAME_S)
            if len(self.frames) > keep:
                del self.frames[:len(self.frames) - keep]
            self.piece_start = self.t - len(self.frames) * FRAME_S
            return None
        if self.silence_s >= self.pause_s and (len(self.frames) * FRAME_S >= self.min_s or (
                self.long_pause_s is not None and self.silence_s >= self.long_pause_s)):
            return self._close(len(self.frames))
        if len(self.frames) * FRAME_S >= self.max_s:
            search = math.ceil(SPLIT_SEARCH_S / FRAME_S)
            cut = min(range(len(self.frames) - search, len(self.frames)), key=lambda i: self.frames[i].level)
            return self._close(cut + 1, carry=True)
        return None

    def _close(self, n, carry=False):
        frames, rest = self.frames[:n], self.frames[n:]
        enough = sum(f.speech for f in frames) * FRAME_S >= MIN_SPEECH_S
        if not carry:                   # trim the trailing silence down to a short tail
            last = max(i for i, f in enumerate(frames) if f.speech) if any(f.speech for f in frames) else -1
            frames = frames[:last + 1 + math.ceil(TAIL_S / FRAME_S)]
        start = self.piece_start
        self.piece_start += n * FRAME_S
        self.frames = rest if carry else []
        self.speech_s = sum(f.speech for f in self.frames) * FRAME_S
        self.silence_s = 0.0
        return self._piece(frames, start) if enough else None

    def _piece(self, frames, start):
        samples = array('h')
        sq = n = 0
        for f in frames:
            samples.extend(f.samples)
            if f.speech:
                sq += f.level * f.level * len(f.samples)
                n += len(f.samples)
        speech_rms = math.sqrt(sq / n) if n else 0.0
        peak = max(max(samples), -min(samples)) / 32768.0 if samples else 0.0
        gain = min(MAX_GAIN, TARGET_RMS / speech_rms, 0.95 / peak) if speech_rms > 0 and peak > 0 else 1.0
        return Piece(samples, self.rate, round(gain, 3) if not 0.95 < gain < 1.05 else 1.0, start,
                     len(samples) / self.rate, sum(f.speech for f in frames) * FRAME_S)

    def flush(self):
        """At the finish: whatever is left becomes the last pieces, if they hold any speech."""
        out = []
        if self._pending:
            self._pending.extend([0] * (self.frame_n - len(self._pending)))
            out += self.feed(array('h'))
        if self.frames and self.speech_s > 0:
            out.append(self._close(len(self.frames)))
        return [p for p in out if p]
