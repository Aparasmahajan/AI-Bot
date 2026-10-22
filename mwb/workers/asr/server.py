"""MWB's speech worker (design §8.3, §8.4): Parakeet TDT 0.6B v2 int8 through onnx-asr, ported from AI-App's
addon\\parakeet\\server.py. It runs in its own Python environment (AI-App's, with numpy and onnxruntime), never in
the core's, and ends itself when idle so Windows gets all of its memory back.

    pythonw.exe server.py --threads 4 [--arena on|off] [--idle-min 15] [--parent PID]

The token comes in the MWB_TOKEN environment variable, not on the command line where any process can read it.
Once the model is loaded and warm, it prints one line, {"port": N}, and serves on 127.0.0.1:N:

    POST /inference   multipart/form-data: "file" = mono 16-bit WAV at any rate; optional "gain" (float)
                      -> {"text": "...", "engine": "parakeet-int8", "audio_s": 4.2, "ms": 910}
    GET  /health      -> {"ok": true, "model": "...", "private_mb": 990, "threads": 4}
    POST /shutdown    -> the process exits

Every request needs the X-MWB-Token header. Nothing heard is logged: only lengths and timings."""
import argparse, ctypes, ctypes.wintypes as wt, io, json, os, sys, threading, time, wave
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np

os.environ.setdefault('HF_HUB_OFFLINE', '1')                  # the model is already in the HF cache; never download
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')

MODEL_ID = 'nemo-parakeet-tdt-0.6b-v2'
ENGINE = 'parakeet-int8'
RATE = 16000


def log(msg):
    """pythonw.exe has no console; stderr is a pipe to the core when there is one. Never let logging crash us."""
    try:
        print(f'[asr] {msg}', file=sys.stderr, flush=True)
    except Exception:
        pass


class PMC(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_k32.GetCurrentProcess.restype = wt.HANDLE
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
_psapi = ctypes.WinDLL('psapi')
_psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]


def private_mb():
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    _psapi.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return round(c.PagefileUsage / 2 ** 20)


def load_model(threads, arena):
    import onnx_asr
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    opts.enable_cpu_mem_arena = arena       # off keeps memory flat for long meeting jobs (§11.4)
    t0 = time.perf_counter()
    model = onnx_asr.load_model(MODEL_ID, quantization='int8', sess_options=opts)
    log(f'{MODEL_ID} int8 loaded in {time.perf_counter() - t0:.1f} s, {threads} threads, arena {"on" if arena else "off"}')
    return model


def _lowpass(x, cutoff):
    """Windowed-sinc low-pass; cutoff is a fraction of the input rate. Keeps decimation from folding hiss into speech."""
    n = np.arange(-32, 33)
    h = np.sinc(2 * cutoff * n) * np.hamming(len(n))
    return np.convolve(x, (h / h.sum()).astype(np.float32), mode='same')


def to_16k(x, sr):
    if sr == RATE or not len(x):
        return x
    x = _lowpass(x, 0.45 * RATE / sr) if sr > RATE else x
    if sr % RATE == 0:
        return x[::sr // RATE].copy()           # 48 kHz mics: keep every third sample
    n = int(round(len(x) * RATE / sr))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def read_wav(data):
    """WAV bytes -> float32 mono at 16 kHz."""
    with wave.open(io.BytesIO(data)) as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f'expected 16-bit PCM, got {width * 8}-bit')
    x = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return to_16k(x, sr)


def multipart_fields(content_type, body):
    """{name: bytes} of a multipart/form-data body."""
    msg = BytesParser(policy=HTTP).parsebytes(b'Content-Type: ' + content_type.encode('latin-1') + b'\r\n\r\n' + body)
    return {part.get_param('name', header='content-disposition'): part.get_payload(decode=True)
            for part in msg.iter_parts()}


class Worker:
    def __init__(self, model, threads, token, idle_s):
        self.model, self.threads, self.token, self.idle_s = model, threads, token, idle_s
        self.last_used = time.monotonic()
        self.lock = threading.Lock()            # one decode at a time keeps latency predictable

    def recognize(self, audio):
        with self.lock:
            self.last_used = time.monotonic()
            try:
                return (self.model.recognize(audio, sample_rate=RATE) or '').strip()
            finally:
                self.last_used = time.monotonic()


def make_handler(worker, stop):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):           # no access log
            pass

        def reply(self, code, obj):
            body = json.dumps(obj).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')     # one request per connection, so the stop flag is seen
            self.close_connection = True
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
            if self.headers.get('X-MWB-Token') == worker.token:
                return True
            self.reply(403, {'error': 'bad token'})
            return False

        def do_GET(self):
            if not self.allowed():
                return
            if self.path.split('?')[0] != '/health':
                return self.reply(404, {'error': 'not found'})
            self.reply(200, {'ok': True, 'model': MODEL_ID, 'engine': ENGINE, 'threads': worker.threads,
                             'private_mb': private_mb(), 'idle_s': round(time.monotonic() - worker.last_used)})

        def do_POST(self):
            if not self.allowed():
                return
            path = self.path.split('?')[0]
            body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
            if path == '/shutdown':
                self.reply(200, {'ok': True})
                stop.set()
                return
            if path != '/inference':
                return self.reply(404, {'error': 'not found'})
            try:
                fields = multipart_fields(self.headers.get('Content-Type', ''), body)
                if not fields.get('file'):
                    return self.reply(400, {'error': "missing 'file' field"})
                audio = read_wav(fields['file'])
                gain = float(fields.get('gain') or 1.0)
                if gain != 1.0:
                    audio = np.clip(audio * gain, -1.0, 1.0)
                secs = len(audio) / RATE
                if len(audio) < RATE // 10:     # under 100 ms: nothing to decode
                    return self.reply(200, {'text': '', 'engine': ENGINE, 'audio_s': round(secs, 2), 'ms': 0})
                t0 = time.perf_counter()
                text = worker.recognize(audio)
                ms = round((time.perf_counter() - t0) * 1000)
                log(f'{secs:.1f} s of audio -> {ms} ms, {len(text)} characters')
                self.reply(200, {'text': text, 'engine': ENGINE, 'audio_s': round(secs, 2), 'ms': ms})
            except Exception as e:
                log(f'error: {type(e).__name__}')
                self.reply(500, {'error': type(e).__name__})

    return Handler


def watchdog(worker, parent, stop):
    """End when idle too long, or when the core that started us is gone (so a crash never leaves 1 GB behind)."""
    handle = _k32.OpenProcess(0x00100000, False, parent) if parent else None     # SYNCHRONIZE
    while not stop.wait(5):
        if handle and _k32.WaitForSingleObject(handle, 0) == 0:
            log('the core has exited; stopping')
            break
        if not worker.lock.locked() and time.monotonic() - worker.last_used > worker.idle_s:
            log(f'idle for {worker.idle_s / 60:.0f} minutes; stopping')
            break
    stop.set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--arena', choices=('on', 'off'), default='on')
    ap.add_argument('--idle-min', type=float, default=15)
    ap.add_argument('--parent', type=int, default=0)
    args = ap.parse_args()
    token = os.environ.pop('MWB_TOKEN', '')
    if not token:
        log('MWB_TOKEN is not set; refusing to start')
        return 2

    model = load_model(args.threads, args.arena == 'on')
    t0 = time.perf_counter()
    model.recognize(np.zeros(RATE, dtype=np.float32), sample_rate=RATE)     # the first decode pays a one-time cost
    log(f'warm-up {time.perf_counter() - t0:.2f} s, {private_mb()} MB private')

    worker, stop = Worker(model, args.threads, token, args.idle_min * 60), threading.Event()
    srv = HTTPServer(('127.0.0.1', 0), make_handler(worker, stop))
    srv.timeout = 0.5
    threading.Thread(target=watchdog, args=(worker, args.parent, stop), daemon=True).start()
    print(json.dumps({'port': srv.server_address[1]}), flush=True)      # the core waits for this line
    while not stop.is_set():
        srv.handle_request()
    srv.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
