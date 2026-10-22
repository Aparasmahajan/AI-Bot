"""The two-lane meeting recorder (design §9.3), proven by P0-1: "me" is the microphone and "them" is everything the
laptop plays (WASAPI loopback of the default speakers or headset), so any call app works the same way.

Windows sends loopback packets only while something plays, so the recorder fills those pauses with silence from the
clock and both lanes keep one timeline. Each lane is cut into 15-28 s pieces at pauses (whisper's sweet spot), and
each piece is handed on at once: nothing is kept in memory for long, and nothing is kept at all after transcription."""
import logging, threading, time
from array import array

from mwb.audio.vad import Segmenter

log = logging.getLogger('mwb.recorder')
PACKET_S = 0.032


class Lane:
    def __init__(self, name, cfg, on_piece):
        m = cfg['meetings']
        self.name, self.on_piece = name, on_piece
        self.min_s, self.max_s, self.flush_s = m['piece_min_s'], m['piece_max_s'], m.get('piece_flush_s', 20)
        self.seg = None
        self.rate = 0
        self.lock = threading.Lock()
        self.t0 = None              # perf_counter of the lane's time zero
        self.fed_s = 0.0            # seconds of audio fed so far, real or filled
        self.stream = None
        self.filled_s = 0.0

    def begin(self, rate, t0):
        self.rate, self.t0 = rate, t0
        self.seg = Segmenter(rate, pause_ms=800, max_s=self.max_s, min_s=self.min_s, long_pause_s=self.flush_s)

    def audio(self, samples):
        """From the device thread: real samples, after any silence the clock says is missing."""
        with self.lock:
            now_s = time.perf_counter() - self.t0
            gap = now_s - len(samples) / self.rate - self.fed_s
            if gap > 0.1:
                self._feed(array('h', bytes(2 * int(gap * self.rate))))
                self.filled_s += gap
            self._feed(samples)

    def fill_to_now(self):
        """From the clock thread: silence up to now when the device has sent nothing for a while."""
        with self.lock:
            gap = time.perf_counter() - self.t0 - self.fed_s
            if gap > 0.3:
                n = int((gap - 0.1) * self.rate)
                self._feed(array('h', bytes(2 * n)))
                self.filled_s += n / self.rate

    def _feed(self, samples):
        self.fed_s += len(samples) / self.rate
        for piece in self.seg.feed(samples):
            self.on_piece(self.name, piece)

    def flush(self):
        with self.lock:
            for piece in self.seg.flush():
                self.on_piece(self.name, piece)


class Recorder:
    """start() opens both lanes; stop() closes them and hands on the last pieces. on_piece(lane, vad.Piece)."""

    def __init__(self, cfg, on_piece, sources=None):
        self.cfg, self.on_piece = cfg, on_piece
        self.sources = sources          # tests: {'me': FileSource, 'them': FileSource} in place of the devices
        self.lanes = {}
        self.running = False
        self._pa = None
        self._clock = None
        self.started = None

    def start(self):
        t0 = time.perf_counter()
        self.started = time.time()
        self.lanes = {name: Lane(name, self.cfg, self.on_piece) for name in ('me', 'them')}
        if self.sources:
            for name, src in self.sources.items():
                lane = self.lanes[name]
                lane.begin(src.rate_of(), t0)
                lane.stream = src
                src.start(lane.audio)
        else:
            import pyaudiowpatch as pyaudio
            self._pa = self._pa or pyaudio.PyAudio()
            wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            devices = {'me': self._pa.get_device_info_by_index(wasapi['defaultInputDevice']),
                       'them': self._pa.get_default_wasapi_loopback()}
            for name, dev in devices.items():
                lane = self.lanes[name]
                rate, ch = int(dev['defaultSampleRate']), max(1, dev['maxInputChannels'])
                lane.begin(rate, t0)

                def cb(data, frames, info, status, lane=lane, ch=ch):
                    a = array('h', data)
                    lane.audio(a[0::ch] if ch > 1 else a)
                    return None, pyaudio.paContinue

                lane.stream = self._pa.open(format=pyaudio.paInt16, channels=ch, rate=rate, input=True,
                                            input_device_index=dev['index'], frames_per_buffer=int(rate * PACKET_S),
                                            stream_callback=cb)
                log.info('lane %s: %d Hz, %d channel(s)', name, rate, ch)
        self.running = True
        self._clock = threading.Thread(target=self._tick, daemon=True, name='recorder-clock')
        self._clock.start()

    def _tick(self):
        while self.running:
            time.sleep(0.5)
            for lane in self.lanes.values():
                if lane.seg:
                    lane.fill_to_now()

    def stop(self):
        """Close the devices, then hand on what is left in each lane."""
        self.running = False
        for lane in self.lanes.values():
            s, lane.stream = lane.stream, None
            if s is None:
                continue
            try:
                if hasattr(s, 'stop_stream'):
                    s.stop_stream()
                    s.close()
                else:
                    s.stop()
            except OSError:
                pass
        if self._clock:
            self._clock.join(2)
        for lane in self.lanes.values():
            if lane.seg:
                lane.flush()
        return {n: round(l.fed_s, 1) for n, l in self.lanes.items()}

    def close(self):
        if self.running:
            self.stop()
        if self._pa:
            self._pa.terminate()
            self._pa = None
