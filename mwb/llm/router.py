"""The router (design §12.7): every language job goes to the API first and falls back to the local model.

One prompt and one output check per skill, whichever route answers. The API is used unless the route is set to
"local", the skill is local-only, or the API fails: no network, no word within 20 s, a rate limit or a bad key.
Then the same request goes to Qwen3.5 on this laptop, if the memory guard allows it.

The Groq key is read from Credential Manager here, only to send it to Groq. Logs record the skill, the route, the
model, sizes and timings; never the text."""
import json, logging, re, threading, time
from dataclasses import dataclass

from mwb import credentials
from mwb.llm.client import Connection
from mwb.llm.local import LocalModel
from mwb.llm.providers import PROVIDERS

log = logging.getLogger('mwb.llm')
QUICK = {'label', 'classify', 'cleanup', 'quick'}
TYPOGRAPHY = {0x2010: '-', 0x2011: '-', 0x00A0: ' ', 0x202F: ' '}       # P0-4: look-alike hyphens break IDs


@dataclass
class Reply:
    ok: bool
    text: str = ''
    route: str = ''             # api | local
    model: str = ''
    error: str = ''
    seconds: float = 0.0
    first_word_s: float | None = None

    def json(self):
        return json_of(self.text)


def normalize(text):
    return text.translate(TYPOGRAPHY)


def json_of(text):
    """The first JSON object in a reply, or None. Models sometimes wrap it in a ```json fence."""
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    start = t.find('{')
    while start >= 0:
        depth, quoted, escaped = 0, False, False
        for i in range(start, len(t)):
            c = t[i]
            if quoted:
                escaped = c == '\\' and not escaped
                if c == '"' and not escaped:
                    quoted = False
                continue
            if c == '"':
                quoted = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except ValueError:
                        break
        start = t.find('{', start + 1)
    return None


class Router:
    def __init__(self, cfg, make_room=None, usage=None):
        self.cfg = cfg['llm']
        self.provider = PROVIDERS[self.cfg['provider']]
        self.local = LocalModel(cfg)
        self.make_room = make_room          # stops idle workers when the local model needs memory
        self.usage = usage                  # usage(skill, route, model, chars_in, chars_out, seconds, ok)
        self.tls = threading.local()

    def _api(self):
        conn = getattr(self.tls, 'api', None)
        if conn is None:
            stored = credentials.read(credentials.api_key_target(self.provider.id))
            if not stored:
                return None
            conn = Connection(self.provider.base, stored.secret, timeout=self.cfg['api_timeout_s'])
            self.tls.api = conn
        return conn

    def forget_key(self):
        """After the key changes in the key window."""
        conn = getattr(self.tls, 'api', None)
        if conn:
            conn.close()
        self.tls.api = None

    def chat(self, skill, messages, max_tokens=1024, temperature=0.3, on_text=None, json_mode=False,
             allow_local=True):
        """One answer for a skill. on_text(piece) streams the words; a fallback starts the text again.
        allow_local=False keeps batch work off the local model while the laptop is busy (§8.5): it waits instead."""
        chars_in = sum(len(m['content']) for m in messages)
        api_allowed = self.cfg['route'] == 'api' and skill not in self.cfg['local_only']
        first_error = ''
        if api_allowed:
            conn = self._api()
            if conn is None:
                first_error = 'no API key saved (tray menu: Set API key)'
            else:
                model = self.provider.quick_model if skill in QUICK else self.provider.model
                r = conn.chat(model, messages, max_tokens, temperature, on_text=on_text,
                              reasoning_effort=self.cfg['reasoning_effort'])
                if r.ok and r.text.strip():
                    return self._done(skill, Reply(True, normalize(r.text), 'api', model, '', r.total_s,
                                                   r.first_word_s), chars_in)
                first_error = r.error or 'empty answer'
                log.info('API failed for %s (%s); trying the local model', skill, first_error[:120])
                if self.cfg['when_api_fails'] != 'local':
                    return self._done(skill, Reply(False, route='api', model=model, error=first_error), chars_in)
        model = self.local.model_for(skill)
        if not allow_local:
            return self._done(skill, Reply(False, route='local', model=model,
                                           error=f'{first_error}; the local model waits for mains power and a calm CPU'),
                              chars_in)
        t0 = time.perf_counter()
        try:
            base, key = self.local.ensure(model, self.make_room)
        except RuntimeError as e:
            why = f'{first_error}; {e}' if first_error else str(e)
            return self._done(skill, Reply(False, route='local', model=model, error=why), chars_in)
        if on_text and first_error:
            on_text('\x00restart')              # the card clears what the failed API sent
        conn = Connection(base, key, timeout=300)
        extra = {'top_p': 0.8, 'top_k': 20, 'presence_penalty': 0}
        if json_mode:
            extra['response_format'] = {'type': 'json_object'}
        r = conn.chat(model, messages, max_tokens, temperature, on_text=on_text, **extra)
        conn.close()
        self.local.touch()
        reply = Reply(r.ok and bool(r.text.strip()), normalize(r.text), 'local', model,
                      r.error, time.perf_counter() - t0, r.first_word_s)
        return self._done(skill, reply, chars_in)

    def _done(self, skill, reply, chars_in):
        log.info('%s via %s (%s): %s, %d chars in, %d out, %.1f s', skill, reply.route or '-', reply.model or '-',
                 'ok' if reply.ok else 'failed', chars_in, len(reply.text), reply.seconds)
        if self.usage:
            try:
                self.usage(skill, reply.route, reply.model, chars_in, len(reply.text), reply.seconds, reply.ok)
            except Exception:
                pass
        return reply

    def close(self):
        self.local.stop()
