"""P0-1: capture both sides of a call at once with PyAudioWPatch: your mic ("me") and everything the laptop plays
("them", WASAPI loopback of the default speakers or headset). Checks the two lanes for gaps. Saves no audio unless
you add --save; it only counts frames and measures levels.

  .venv\\Scripts\\python.exe -I docs\\bench\\p0_1_two_lane.py                  10 minutes: the pass test, run during a call
  .venv\\Scripts\\python.exe -I docs\\bench\\p0_1_two_lane.py --seconds 60     a short check
  add --save to keep both lanes as WAV files in %LOCALAPPDATA%\\MWB\\p0 (outside Git) to listen to them
  add --self-test to check the loopback lane without a call: it plays an inaudible signal (±1 step of 16-bit audio,
      about -90 dBFS) on the speakers, so "them" has something to capture

Every 10 s it prints each lane's frames against the clock, its longest pause between audio packets and its level.
Windows sends loopback packets only while something plays, so "them" pauses in silence: MWB's recorder fills
those pauses with silence from the clock. Pass (design §17): no overflow and no dropouts for 10 minutes of a call.
Ctrl+C ends early with the summary. The per-interval numbers go to %LOCALAPPDATA%\\MWB\\p0\\p0-1-lanes.csv."""
import argparse, array, csv, datetime, math, os, time, wave

import pyaudiowpatch as pyaudio

OUT = os.path.join(os.environ['LOCALAPPDATA'], 'MWB', 'p0')
PACKET_S = 0.02                     # 20 ms buffers, like AI-App's capture


class Lane:
    def __init__(self, name, device, save):
        self.name, self.device = name, device
        self.rate = int(device['defaultSampleRate'])
        self.channels = max(1, device['maxInputChannels'])  # shared mode wants the device's own channel count
        self.frames = self.packets = self.flags = 0
        self.start = self.last = None
        self.gap = self.longest_gap = self.paused = 0.0     # gap: longest pause this interval
        self.sumsq = self.samples = self.peak = 0
        self.wav = None
        if save:
            self.wav = wave.open(os.path.join(OUT, f'p0-1-{name}-{datetime.datetime.now():%Y%m%d-%H%M%S}.wav'), 'wb')
            self.wav.setnchannels(self.channels)
            self.wav.setsampwidth(2)
            self.wav.setframerate(self.rate)

    def callback(self, data, frame_count, time_info, status):
        now = time.perf_counter()
        if self.start is None:
            self.start = now
        elif now - self.last > 0.1:                         # a pause of more than five packets
            self.paused += now - self.last - PACKET_S
        if self.last is not None:
            self.gap = max(self.gap, now - self.last)
        self.last = now
        self.frames += frame_count
        self.packets += 1
        self.flags += bool(status)                          # paInputOverflow and friends
        a = array.array('h')
        a.frombytes(data)
        self.sumsq += math.sumprod(a, a)
        self.samples += len(a)
        self.peak = max(self.peak, max(a, default=0), -min(a, default=0))
        if self.wav:
            self.wav.writeframes(data)
        return None, pyaudio.paContinue

    def interval(self, now):
        """Numbers since the lane's first packet, plus this interval's level and longest pause; resets the interval."""
        span = (now - self.start) if self.start else 0.0
        clock = self.frames / (self.rate * span) if span else 0.0
        level = 20 * math.log10(math.sqrt(self.sumsq / self.samples) / 32768) if self.sumsq else float('-inf')
        peak = 20 * math.log10(self.peak / 32768) if self.peak else float('-inf')
        row = dict(lane=self.name, seconds=round(span, 1), frames=self.frames, vs_clock=round(clock, 4),
                   longest_pause_ms=round(self.gap * 1000), paused_s=round(self.paused, 1), flags=self.flags,
                   level_dbfs=round(level, 1), peak_dbfs=round(peak, 1))
        self.longest_gap = max(self.longest_gap, self.gap)
        self.gap, self.sumsq, self.samples, self.peak = 0.0, 0, 0, 0
        return row


def main():
    ap = argparse.ArgumentParser(description='P0-1 two-lane capture check')
    ap.add_argument('--seconds', type=int, default=600)
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--self-test', action='store_true', help='play an inaudible -90 dBFS signal for the loopback lane')
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    pa = pyaudio.PyAudio()
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    mic = pa.get_device_info_by_index(wasapi['defaultInputDevice'])
    loop = pa.get_default_wasapi_loopback()
    lanes = [Lane('me', mic, args.save), Lane('them', loop, args.save)]
    streams = []
    if args.self_test:
        # A 1 kHz square wave of +1/-1 (the smallest step 16-bit audio has): far below anything a speaker makes audible
        spk = pa.get_device_info_by_index(wasapi['defaultOutputDevice'])
        rate, ch = int(spk['defaultSampleRate']), spk['maxOutputChannels']
        period, cache = rate // 1000, {}         # a 20 ms buffer holds whole cycles, so buffers join seamlessly

        def play(_, frame_count, time_info, status):
            if frame_count not in cache:
                cache[frame_count] = array.array('h', [1 if (i % period) < period // 2 else -1
                                                       for i in range(frame_count) for _ in range(ch)]).tobytes()
            return cache[frame_count], pyaudio.paContinue

        streams.append(pa.open(format=pyaudio.paInt16, channels=ch, rate=rate, output=True,
                               output_device_index=spk['index'], frames_per_buffer=int(rate * PACKET_S),
                               stream_callback=play))
        print(f'self-test: playing an inaudible -90 dBFS signal on {spk["name"]}')
    for lane in lanes:
        print(f'{lane.name:4} {lane.device["name"]}: {lane.rate} Hz, {lane.channels} channel(s)')
        streams.append(pa.open(format=pyaudio.paInt16, channels=lane.channels, rate=lane.rate, input=True,
                               input_device_index=lane.device['index'], frames_per_buffer=int(lane.rate * PACKET_S),
                               stream_callback=lane.callback))
    log = open(os.path.join(OUT, 'p0-1-lanes.csv'), 'a', newline='', encoding='utf-8')
    writer = csv.DictWriter(log, fieldnames=['time', 'lane', 'seconds', 'frames', 'vs_clock', 'longest_pause_ms',
                                             'paused_s', 'flags', 'level_dbfs', 'peak_dbfs'])
    if log.tell() == 0:
        writer.writeheader()
    print(f'Capturing for {args.seconds} s; no audio is saved{" except the --save files" if args.save else ""}.')
    end = time.perf_counter() + args.seconds
    rows = []
    try:
        while time.perf_counter() < end:
            time.sleep(min(10, max(0, end - time.perf_counter())))
            now = time.perf_counter()
            for lane in lanes:
                r = lane.interval(now)
                rows.append(r)
                writer.writerow(dict(time=f'{datetime.datetime.now():%H:%M:%S}', **r))
                print(f'{r["seconds"]:6.0f} s  {lane.name:4} frames vs clock {r["vs_clock"]:.4f}  longest pause '
                      f'{r["longest_pause_ms"]:5} ms  paused {r["paused_s"]:5.1f} s  flags {r["flags"]}  '
                      f'level {r["level_dbfs"]:6.1f} dBFS', flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        for s in streams:
            s.stop_stream()
            s.close()
        pa.terminate()
        log.close()
        for lane in lanes:
            if lane.wav:
                lane.wav.close()

    print('\nSummary')
    for lane in lanes:
        span = (lane.last - lane.start) if lane.start else 0.0
        audible = span - lane.paused
        clock = lane.frames / (lane.rate * audible) if audible > 0 else 0.0
        print(f'  {lane.name:4} {lane.packets} packets over {span:.0f} s; paused {lane.paused:.1f} s in all; '
              f'longest pause {lane.longest_gap * 1000:.0f} ms; overflow flags {lane.flags}; '
              f'frames against the clock while audio flowed {clock:.4f}')
    print('Pass needs: flags 0 on both lanes, and "me" never paused. Pauses on "them" are fine when nothing played.')
    if args.self_test:
        print('Self-test: "them" should have packets for the whole run, at about -90 dBFS.')


if __name__ == '__main__':
    main()
