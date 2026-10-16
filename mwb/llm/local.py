"""The local fallback (design §12.7): llama.cpp's llama-server with Qwen3.5, thinking off, from the build already in
%USERPROFILE%\\Tools\\llamacpp (your own launchers there are left alone). It speaks the same OpenAI-compatible API
as Groq, so the router only changes the address and the model.

It starts only when the API can't be used, with a random port and a key of its own, and exits 5 minutes after its
last job, which gives its 1.3-2.4 GB back. The memory guard decides whether it may load at all."""
import json, logging, os, secrets, socket, subprocess, threading, time, urllib.request

from mwb import config, memory_guard, winapi

log = logging.getLogger('mwb.local')
SIZE_GB = {'Qwen3.5-2B-Q4_K_M.gguf': 1.25, 'Qwen3.5-4B-Q4_K_M.gguf': 2.42}       # measured 12 Oct 2026


class LocalModel:
    def __init__(self, cfg):
        self.cfg = cfg['llm']
        self.margin = cfg['speech']['margin_gb']
        self.root = config.path(self.cfg['llamacpp'])
        self.proc, self.port, self.key, self.model = None, None, None, None
        self.lock = threading.Lock()
        self.last_used = time.monotonic()
        threading.Thread(target=self._idle, daemon=True, name='local-llm-idle').start()

    def model_for(self, skill):
        return self.cfg['local_model_big'] if skill in self.cfg['local_big_for'] else self.cfg['local_model']

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure(self, model, make_room=None):
        """(base URL, key) of a ready server with this model, or raises RuntimeError with a plain reason."""
        with self.lock:
            self.last_used = time.monotonic()
            if self.running and self.model == model:
                return f'http://127.0.0.1:{self.port}/v1', self.key
            self._stop()
            need = SIZE_GB.get(model, 2.5)
            state, free = memory_guard.verdict(need, self.margin)
            if state == 'short' and make_room:
                make_room()                     # stop idle workers first (§11.2)
                state, free = memory_guard.verdict(need, self.margin)
            if state == 'short':
                raise RuntimeError(f'the local model needs {need:.1f} GB and only {free:.1f} GB is free')
            exe = self.root / 'cpu' / 'llama-server.exe'
            path = self.root / 'models' / model
            if not exe.exists() or not path.exists():
                raise RuntimeError('the local model or llama-server was not found in Tools\\llamacpp')
            s = socket.socket()
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
            s.close()
            self.key = secrets.token_urlsafe(24)
            args = [str(exe), '-m', str(path), '-t', str(self.cfg['local_threads']), '-c', '8192',
                    '--host', '127.0.0.1', '--port', str(self.port), '--api-key', self.key,
                    '--chat-template-kwargs', '{"enable_thinking":false}', '--no-webui']
            t0 = time.monotonic()
            self.proc = subprocess.Popen(args, cwd=str(exe.parent), stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         creationflags=0x08000000)
            winapi.end_with_me(self.proc)
            self.model = model
            while time.monotonic() - t0 < 120:
                if self.proc.poll() is not None:
                    self.proc = None
                    raise RuntimeError('the local model stopped while loading')
                try:
                    req = urllib.request.Request(f'http://127.0.0.1:{self.port}/health',
                                                 headers={'Authorization': f'Bearer {self.key}'})
                    with urllib.request.urlopen(req, timeout=2) as r:
                        if json.load(r).get('status') == 'ok':
                            log.info('local model %s ready in %.1f s (%.1f GB was free)', model,
                                     time.monotonic() - t0, free)
                            return f'http://127.0.0.1:{self.port}/v1', self.key
                except OSError:
                    time.sleep(0.4)
            self._stop()
            raise RuntimeError('the local model did not start within 2 minutes')

    def touch(self):
        self.last_used = time.monotonic()

    def _idle(self):
        while True:
            time.sleep(30)
            with self.lock:
                if self.running and time.monotonic() - self.last_used > self.cfg['local_idle_min'] * 60:
                    log.info('local model idle; stopping it')
                    self._stop()

    def _stop(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()

    def stop(self):
        with self.lock:
            self._stop()
