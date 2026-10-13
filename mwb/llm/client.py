"""One OpenAI-compatible client for Groq, other APIs and the local llama-server (design §5). Standard library only.
check_key() proves a key works; Connection.chat() streams an answer and times it. The router that picks the API or
the local fallback arrives in Phase 3."""
import http.client, json, ssl, time, urllib.error, urllib.parse, urllib.request
from dataclasses import dataclass, field

USER_AGENT = 'MWB/0.1'      # some API front ends refuse Python's default user agent


@dataclass
class KeyCheck:
    ok: bool
    kind: str               # ok | rejected | network | certificate | timeout | error
    detail: str = ''
    seconds: float = 0.0
    models: list = field(default_factory=list)


@dataclass
class ChatResult:
    ok: bool
    text: str = ''
    error: str = ''
    status: int = 0                     # HTTP status; 429 means rate-limited
    retry_after: float = 0.0            # seconds, when the server asked to wait
    first_word_s: float | None = None   # request sent -> first visible token
    total_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0          # includes hidden reasoning tokens on reasoning models
    reasoning_tokens: int = 0
    finish: str = ''                    # stop | length | ...
    server: dict = field(default_factory=dict)  # the server's own timings (Groq usage times, llama-server timings)
    rate: dict = field(default_factory=dict)    # x-ratelimit-* headers


def _api_message(raw):
    """The short message an OpenAI-compatible API puts in its error body, if any."""
    try:
        return str(json.loads(raw).get('error', {}).get('message', ''))[:200]
    except (ValueError, AttributeError):
        return raw[:200]


def check_key(provider, key, timeout=15):
    """Ask for the provider's model list with this key: the cheapest call that proves a key works. Never raises."""
    req = urllib.request.Request(provider.base + '/models',
                                 headers={'Authorization': f'Bearer {key}', 'User-Agent': USER_AGENT})
    t0 = time.perf_counter()
    took = lambda: time.perf_counter() - t0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        return KeyCheck(True, 'ok', seconds=took(), models=sorted(m['id'] for m in data.get('data', [])))
    except urllib.error.HTTPError as e:
        return KeyCheck(False, 'rejected' if e.code == 401 else 'error',
                        f'HTTP {e.code} {_api_message(e.read().decode("utf-8", "replace"))}'.strip(), took())
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            return KeyCheck(False, 'certificate', e.reason.verify_message or str(e.reason), took())
        if isinstance(e.reason, TimeoutError):
            return KeyCheck(False, 'timeout', f'no answer within {timeout} s', took())
        return KeyCheck(False, 'network', str(e.reason), took())
    except TimeoutError:
        return KeyCheck(False, 'timeout', f'no answer within {timeout} s', took())
    except (ValueError, KeyError, TypeError, OSError) as e:
        return KeyCheck(False, 'error', f'{type(e).__name__}: {e}', took())


class Connection:
    """A kept-alive connection to one OpenAI-compatible server, so requests after the first skip the TCP and TLS
    handshakes. One per thread; not thread-safe."""

    def __init__(self, base, key='', timeout=180):
        u = urllib.parse.urlsplit(base)
        self.https, self.host, self.port, self.prefix = u.scheme == 'https', u.hostname, u.port, u.path.rstrip('/')
        self.key, self.timeout, self.conn = key, timeout, None

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _send(self, method, path, body=None):
        headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json, text/event-stream'}
        if self.key:
            headers['Authorization'] = f'Bearer {self.key}'
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        for attempt in (1, 2):              # the server may have closed an idle kept-alive connection
            if self.conn is None:
                self.conn = (http.client.HTTPSConnection(self.host, self.port or 443, timeout=self.timeout,
                                                         context=ssl.create_default_context()) if self.https else
                             http.client.HTTPConnection(self.host, self.port or 80, timeout=self.timeout))
            try:
                self.conn.request(method, self.prefix + path, body=data, headers=headers)
                return self.conn.getresponse()
            except (http.client.RemoteDisconnected, http.client.CannotSendRequest, ConnectionResetError,
                    BrokenPipeError):
                self.close()
                if attempt == 2:
                    raise

    def get(self, path):
        """GET a JSON endpoint such as /models. Returns (status, parsed body or text)."""
        r = self._send('GET', path)
        raw = r.read().decode('utf-8', 'replace')
        try:
            return r.status, json.loads(raw)
        except ValueError:
            return r.status, raw

    def chat(self, model, messages, max_tokens=1024, temperature=0.3, **extra):
        """Stream one chat completion. API errors come back as ChatResult(ok=False, ...), never as exceptions,
        so the caller can wait, retry or fall back to the local model."""
        body = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature, stream=True,
                    **extra)
        t0 = time.perf_counter()
        took = lambda: time.perf_counter() - t0
        try:
            resp = self._send('POST', '/chat/completions', body)
        except (OSError, http.client.HTTPException) as e:
            self.close()
            return ChatResult(False, error=f'{type(e).__name__}: {e}', total_s=took())
        rate = {k.lower(): v for k, v in resp.getheaders() if k.lower().startswith('x-ratelimit')}
        if resp.status != 200:
            raw = resp.read().decode('utf-8', 'replace')
            try:
                wait = float(resp.getheader('retry-after') or 0)
            except ValueError:
                wait = 0.0
            return ChatResult(False, error=f'HTTP {resp.status} {_api_message(raw)}'.strip(), status=resp.status,
                              retry_after=wait, total_s=took(), rate=rate)
        parts, first, usage, timings, finish = [], None, {}, {}, ''
        try:
            while line := resp.readline():
                line = line.strip()
                if not line.startswith(b'data:'):
                    continue
                payload = line[5:].strip()
                if payload == b'[DONE]':
                    break
                chunk = json.loads(payload)
                if 'error' in chunk:
                    return ChatResult(False, text=''.join(parts), error=_api_message(json.dumps(chunk)),
                                      status=200, total_s=took(), rate=rate)
                for choice in chunk.get('choices') or []:
                    piece = (choice.get('delta') or {}).get('content')
                    if piece:
                        if first is None:
                            first = took()
                        parts.append(piece)
                    finish = choice.get('finish_reason') or finish
                usage = chunk.get('usage') or (chunk.get('x_groq') or {}).get('usage') or usage
                timings = chunk.get('timings') or timings
            resp.read()                     # drain, so the connection can be reused
        except (OSError, http.client.HTTPException, ValueError) as e:
            self.close()
            return ChatResult(False, text=''.join(parts), error=f'{type(e).__name__}: {e}', status=200,
                              total_s=took(), rate=rate)
        server = {k: usage[k] for k in ('queue_time', 'prompt_time', 'completion_time', 'total_time') if k in usage}
        server.update({k: timings[k] for k in ('prompt_n', 'prompt_ms', 'predicted_n', 'predicted_ms') if k in timings})
        return ChatResult(True, text=''.join(parts), status=200, first_word_s=first, total_s=took(),
                          prompt_tokens=usage.get('prompt_tokens', timings.get('prompt_n', 0)),
                          completion_tokens=usage.get('completion_tokens', timings.get('predicted_n', 0)),
                          reasoning_tokens=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens', 0),
                          finish=finish, server=server, rate=rate)
