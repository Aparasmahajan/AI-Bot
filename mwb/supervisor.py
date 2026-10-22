"""Starts, checks and ends the speech worker (design §8.3, §8.4, §11.1).

The worker is a separate process in AI-App's Parakeet environment, so numpy and onnxruntime never enter the core.
It listens on 127.0.0.1 at a port of its own choosing, answers only requests carrying this session's token, and
exits by itself after 15 idle minutes or if the core disappears. Ending the process is what gives the memory back."""
import http.client, json, logging, os, secrets, subprocess, threading, time
from pathlib import Path

from mwb import config, memory_guard, winapi
from mwb.audio.capture import wav_bytes

log = logging.getLogger('mwb.asr')
SERVER = Path(__file__).parent / 'workers' / 'asr' / 'server.py'
CREATE_NO_WINDOW = 0x08000000


class WorkerError(Exception):
    pass


class SpeechWorker:
    """ensure() starts it in the background if needed; transcribe() waits until it is ready."""

    def __init__(self, cfg, on_state=lambda state, detail='': None):
        self.cfg, self.on_state = cfg, on_state
        self.proc, self.port, self.token = None, None, None
        self.ready = threading.Event()
        self.failed = ''
        self.lock = threading.Lock()
        self.started_at = 0.0

    def python(self):
        exe = os.environ.get('MWB_ASR_PYTHON') or config.path(self.cfg['speech']['python'])
        exe = Path(exe)
        if not exe.exists() and exe.name.lower() == 'pythonw.exe' and exe.with_name('python.exe').exists():
            exe = exe.with_name('python.exe')
        return exe

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure(self, reason=''):
        """Start the worker unless it is running or starting. Returns False, with self.failed set, if it can't."""
        with self.lock:
            if self.running:
                return True
            self.ready.clear()
            self.failed = ''
            sp = self.cfg['speech']
            state, free = memory_guard.verdict(sp['model_gb'], sp['margin_gb'])
            if state == 'short':
                self.failed = f'Only {free:.2f} GB of memory is free, and speech needs {sp["model_gb"]:.2f} GB. ' \
                              'Close some windows and try again.'
                log.warning('not starting the speech worker: %.2f GB free', free)
                self.on_state('failed', self.failed)
                return False
            if state == 'tight':
                log.warning('starting the speech worker with only %.2f GB free', free)
            exe = self.python()
            if not exe.exists():
                self.failed = 'The speech engine (AI-App\'s Parakeet environment) was not found. See [speech] python.'
                log.error('speech python not found: %s', exe.name)
                self.on_state('failed', self.failed)
                return False
            self.token = secrets.token_urlsafe(24)
            env = dict(os.environ, MWB_TOKEN=self.token, PYTHONIOENCODING='utf-8')
            d = self.cfg['dictation']
            args = [str(exe), '-I', str(SERVER), '--threads', str(d['threads']), '--arena', 'on',
                    '--idle-min', str(d['idle_unload_min']), '--parent', str(os.getpid())]
            self.started_at = time.monotonic()
            self.proc = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW,
                                         cwd=str(SERVER.parent))
            winapi.end_with_me(self.proc)
            log.info('speech worker starting (%s; %.1f GB free)', reason or 'on request', free)
            self.on_state('loading')
            threading.Thread(target=self._read_stdout, args=(self.proc,), daemon=True, name='asr-out').start()
            threading.Thread(target=self._read_stderr, args=(self.proc,), daemon=True, name='asr-err').start()
            return True

    def _read_stdout(self, proc):
        for line in proc.stdout:
            try:
                self.port = int(json.loads(line)['port'])
            except (ValueError, KeyError, TypeError):
                continue
            log.info('speech worker ready in %.1f s', time.monotonic() - self.started_at)
            self.ready.set()
            self.on_state('ready')
        code = proc.wait()
        if proc is self.proc:
            self.ready.clear()
            self.port = None
            log.info('speech worker exited (code %s)', code)
            self.on_state('stopped')

    def _read_stderr(self, proc):
        for raw in proc.stderr:                 # the worker logs only lengths and timings, never what was said
            line = raw.decode('utf-8', 'replace').rstrip()
            if line:
                log.info('%s', line[:300])

    def _request(self, method, path, body=b'', headers=None, timeout=30):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)
        try:
            conn.request(method, path, body, {'X-MWB-Token': self.token, **(headers or {})})
            r = conn.getresponse()
            data = r.read()
            if r.status != 200:
                raise WorkerError(f'{path}: HTTP {r.status}')
            return json.loads(data)
        finally:
            conn.close()

    def wait_ready(self, timeout):
        end = time.monotonic() + timeout
        while not self.ready.wait(0.1):
            if self.failed or not self.running or time.monotonic() > end:
                return False
        return True

    def transcribe(self, piece, timeout=60):
        """{'text', 'ms', 'audio_s'} for a vad.Piece. Starts the worker if it has gone."""
        if not self.running and not self.ensure('a dictation'):
            raise WorkerError(self.failed)
        if not self.wait_ready(timeout):
            raise WorkerError(self.failed or 'the speech worker did not start')
        boundary = secrets.token_hex(12)
        wav = wav_bytes(piece.samples, piece.rate)
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="gain"\r\n\r\n{piece.gain}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="piece.wav"\r\n'
                f'Content-Type: audio/wav\r\n\r\n').encode() + wav + f'\r\n--{boundary}--\r\n'.encode()
        return self._request('POST', '/inference', body,
                             {'Content-Type': f'multipart/form-data; boundary={boundary}'}, timeout)

    def health(self):
        return self._request('GET', '/health', timeout=5) if self.ready.is_set() else None

    def stop(self, why=''):
        with self.lock:
            proc = self.proc
            if not proc or proc.poll() is not None:
                return
            log.info('stopping the speech worker%s', f' ({why})' if why else '')
            try:
                if self.ready.is_set():
                    self._request('POST', '/shutdown', timeout=3)
                proc.wait(5)
            except (OSError, WorkerError, subprocess.TimeoutExpired, http.client.HTTPException):
                proc.kill()


class Whisper:
    """whisper.cpp's whisper-cli, started once per meeting piece (design §9.3, measured 14 Oct 2026).

    whisper always works on a 30 s window, so pieces are 15-28 s long. One run of whisper small loads in about half a
    second, transcribed 28 s of speech in 19 s on 2 threads on battery, and used 0.79 GB, all of which goes back to
    Windows when it exits. A resident whisper-server held 2.2 GB, which this laptop can't spare during a call."""

    def __init__(self, cfg):
        m = cfg['meetings']
        self.exe = config.path(m['whisper_cli'])
        self.model = config.path(m['whisper_model'])
        self.language = m.get('language', 'auto')
        self.model_gb, self.margin_gb = m.get('model_gb', 0.8), cfg['speech']['margin_gb']

    def available(self):
        return self.exe.exists() and self.model.exists()

    def memory_ok(self):
        return memory_guard.verdict(self.model_gb, 0.3)[0] != 'short'

    def transcribe(self, wav, threads=2, low_priority=True, timeout=900):
        """[(start s, end s, text)] for one WAV file at any rate, and the language whisper heard."""
        out = Path(wav).with_suffix('')
        flags = CREATE_NO_WINDOW | (0x4000 if low_priority else 0)          # BELOW_NORMAL_PRIORITY_CLASS
        p = subprocess.Popen([str(self.exe), '-m', str(self.model), '-f', str(wav), '-t', str(threads), '-l',
                              self.language, '-sns', '-np', '-oj', '-of', str(out)], cwd=str(self.exe.parent),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             creationflags=flags)
        winapi.end_with_me(p)
        try:
            _, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            raise WorkerError('whisper took too long')
        result = out.with_suffix('.json')
        if p.returncode != 0 or not result.exists():
            raise WorkerError(f'whisper failed (exit {p.returncode})')
        try:
            data = json.loads(result.read_text(encoding='utf-8', errors='replace'))
        finally:
            result.unlink(missing_ok=True)
        segs = [(s['offsets']['from'] / 1000, s['offsets']['to'] / 1000, s['text'].strip())
                for s in data.get('transcription', []) if s.get('text', '').strip()]
        return segs, data.get('result', {}).get('language', '')
