"""Microphone capture with PyAudioWPatch (design §16.1, proven by P0-1). The mic is open only while you dictate,
so Windows' "microphone in use" mark shows exactly when MWB listens. Audio stays in memory and is never saved.

Windows shares the mic at its own rate and channel count (48 kHz and 4 channels on this laptop); the core keeps one
channel and leaves the conversion to 16 kHz to the speech worker, which has numpy."""
import io, threading, time, wave
from array import array

import pyaudiowpatch as pyaudio

PACKET_S = 0.032


class Mic:
    """start(callback) opens the default mic; callback(samples: array('h'), mono) runs on PortAudio's thread."""

    def __init__(self):
        self._pa = None
        self._stream = None
        self.rate = 0
        self.device_name = ''

    def start(self, callback):
        if self._pa is None:
            self._pa = pyaudio.PyAudio()
        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        dev = self._pa.get_device_info_by_index(wasapi['defaultInputDevice'])   # follows a headset plugged in later
        self.rate, channels = int(dev['defaultSampleRate']), max(1, dev['maxInputChannels'])
        self.device_name = dev['name']

        def on_audio(data, frame_count, time_info, status):
            samples = array('h', data)
            callback(samples[0::channels] if channels > 1 else samples)
            return None, pyaudio.paContinue

        self._stream = self._pa.open(format=pyaudio.paInt16, channels=channels, rate=self.rate, input=True,
                                     input_device_index=dev['index'], frames_per_buffer=int(self.rate * PACKET_S),
                                     stream_callback=on_audio)
        return self.rate

    def stop(self):
        s, self._stream = self._stream, None
        if s:
            try:
                s.stop_stream()
                s.close()
            except OSError:
                pass

    def close(self):
        self.stop()
        if self._pa:
            self._pa.terminate()
            self._pa = None


class FileSource:
    """Plays a WAV file into the same callback, at real-time pace or faster: for tests without a microphone."""

    def __init__(self, path, speed=1.0, then_silence_s=0.0):
        self.path, self.speed, self.then_silence_s = path, speed, then_silence_s
        self._stop = threading.Event()
        self.rate = 0
        self.device_name = f'file {path}'
        self.done = threading.Event()

    def rate_of(self):
        with wave.open(str(self.path)) as w:
            return w.getframerate()

    def start(self, callback):
        with wave.open(str(self.path)) as w:
            self.rate, ch = w.getframerate(), w.getnchannels()
            data = array('h', w.readframes(w.getnframes()))
        mono = data[0::ch] if ch > 1 else data
        mono.extend([0] * int(self.rate * self.then_silence_s))
        step = int(self.rate * PACKET_S)

        def run():
            t0 = time.perf_counter()
            for i in range(0, len(mono), step):
                if self._stop.is_set():
                    break
                callback(mono[i:i + step])
                if self.speed:
                    delay = t0 + (i + step) / self.rate / self.speed - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
            self.done.set()

        self._stop.clear()
        threading.Thread(target=run, daemon=True, name='file-source').start()
        return self.rate

    def stop(self):
        self._stop.set()

    def close(self):
        self.stop()


def wav_bytes(samples, rate):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return buf.getvalue()
