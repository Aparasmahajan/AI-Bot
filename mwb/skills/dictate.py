"""Dictation (design §9.1): talk, and the text is already there when you stop.

The mic opens at once and a pre-roll keeps the first sound. Pauses of 500 ms cut the speech into pieces that the
speech worker transcribes while you keep talking, so at the finish only the last piece is left. Then the clean-up
rules run, the text goes in at the cursor, and a row goes into the history.

Start and finish come from the keys: a double tap of Caps Lock (hands-free; a second double tap or a 2 s pause
finishes) or holding the push-to-talk shortcut (letting go finishes). Esc cancels. Nothing heard is ever logged:
the log holds lengths and timings only."""
import datetime, logging, queue, threading, time

from mwb import insert, winapi
from mwb.audio.vad import Segmenter
from mwb.skills import cleanup
from mwb.supervisor import WorkerError

log = logging.getLogger('mwb.dictate')
LIVE_WORDS = 8


class Session:
    def __init__(self, trigger, app, on_text=None):
        self.trigger, self.app, self.on_text = trigger, app, on_text
        self.text_box = None                # is the cursor in a text box? (answer mode, §9.7)
        self.started = datetime.datetime.now()
        self.seg = None                     # made on the first audio, at the mic's own rate
        self.ending = False
        self.pieces = queue.Queue()
        self.texts = []
        self.audio_s = 0.0
        self.count = 0
        self.error = ''
        self.t_finish = None
        self.asr = None


class Dictation:
    """start(), finish() and cancel() may be called from any thread. ui is told the state, level and live words."""

    def __init__(self, cfg, worker, mic, ui, store=None, dictionary=()):
        self.cfg, self.worker, self.mic, self.ui, self.store = cfg, worker, mic, ui, store
        self.dictionary = dictionary
        self.lock = threading.Lock()
        self.session = None
        self.state = 'idle'                 # idle | listening | finishing
        self.paused = False
        self.last = {}                      # numbers from the last dictation, for tests and the tray
        self.assist = None                  # set by the core from Phase 3: decides write or answer

    @property
    def active(self):
        return self.state != 'idle'

    # ---- start -----------------------------------------------------------------------------------------------

    def start(self, trigger, app='', on_text=None):
        """on_text(text) receives what you said instead of it being typed: the instruction for a command."""
        with self.lock:
            if self.paused or self.state != 'idle':
                return False
            self.state = 'listening'
        self.worker.ensure('a dictation')
        try:
            s = Session(trigger, app, on_text)
            self.session = s
            if on_text is None and self.assist is not None:
                from mwb.sensors import focus
                threading.Thread(target=lambda: setattr(s, 'text_box', focus.in_text_box()), daemon=True,
                                 name='focus').start()
            rate = self.mic.start(lambda samples: self._on_audio(s, samples))
        except Exception as e:              # no mic, or the device is busy
            log.error('could not open the microphone: %s', type(e).__name__)
            self.mic.stop()
            with self.lock:
                self.state, self.session = 'idle', None
            self.ui.notify("MWB couldn't open the microphone. Is a headset or mic connected?")
            self.ui.set_state('idle')
            return False
        s.asr = threading.Thread(target=self._transcribe_pieces, args=(s,), daemon=True, name='dictate-asr')
        s.asr.start()
        self.ui.set_state('listening')
        log.info('dictation started (%s) into %s at %d Hz', trigger, app or '?', rate)
        return True

    # ---- while talking ---------------------------------------------------------------------------------------

    def _on_audio(self, s, samples):
        """On PortAudio's thread: cut pieces, feed the meter, and finish by itself when it should."""
        if self.session is not s or self.state != 'listening' or s.ending:
            return
        try:
            self._listen(s, samples)
        except Exception:                   # an error here must never stop the audio stream silently
            log.exception('audio handling failed')

    def _listen(self, s, samples):
        if s.seg is None:
            d = self.cfg['dictation']
            s.seg = Segmenter(self.mic.rate, d['pause_ms'], d['piece_max_s'])
        for piece in s.seg.feed(samples):
            s.count += 1
            s.audio_s += piece.seconds
            s.pieces.put(piece)
        self.ui.set_level(s.seg.meter)
        t, end = self.cfg['triggers'], None
        if s.seg.t >= t['max_s']:
            end = (self.finish, 'time limit')
        elif s.trigger == 'caps':
            if s.seg.last_speech_at is None and s.seg.t >= t['give_up_s']:
                end = (self.cancel, 'nothing heard')
            elif s.seg.last_speech_at is not None and s.seg.t - s.seg.last_speech_at >= t['finish_pause_s']:
                end = (self.finish, 'pause')
        if end:
            s.ending = True
            threading.Thread(target=end[0], args=(end[1],), daemon=True).start()

    def _transcribe_pieces(self, s):
        """One piece at a time, in order. Waits for the worker if it is still loading."""
        while True:
            piece = s.pieces.get()
            if piece is None:
                return
            if s.error:
                continue
            try:
                r = self.worker.transcribe(piece, timeout=90)
            except (WorkerError, OSError) as e:
                s.error = str(e) or type(e).__name__
                log.error('transcription failed: %s', s.error)
                continue
            s.texts.append(r.get('text', ''))
            log.info('piece %.1f s -> %s ms', piece.seconds, r.get('ms'))
            if self.cfg['indicator']['live_words'] and s.t_finish is None:
                words = cleanup.clean(s.texts, self.dictionary).split()
                self.ui.set_words(' '.join(words[-LIVE_WORDS:]))

    # ---- finish ----------------------------------------------------------------------------------------------

    def finish(self, why='keys'):
        with self.lock:
            s = self.session
            if self.state != 'listening' or s is None:
                return
            self.state = 'finishing'
        s.t_finish = time.monotonic()
        self.mic.stop()
        for piece in (s.seg.flush() if s.seg else []):
            s.count += 1
            s.audio_s += piece.seconds
            s.pieces.put(piece)
        s.pieces.put(None)
        self.ui.set_state('working')
        log.info('finishing (%s) after %.1f s', why, s.seg.t if s.seg else 0)
        threading.Thread(target=self._complete, args=(s,), daemon=True, name='dictate-finish').start()

    def _answers(self, final, s):
        """Answer mode (§9.7): hand a question to the assistant instead of typing it."""
        kind, text = self.assist.decide(final.strip(), s.app, s.text_box)
        if kind == 'answer':
            self.assist.answer(text)
            return True
        return False

    def _complete(self, s):
        s.asr.join()
        final = cleanup.clean(s.texts, self.dictionary) if not s.error else ''
        how, into = 'none', ''
        if final and s.on_text:                         # an instruction for a command, not text to type
            how = 'command'
            threading.Thread(target=s.on_text, args=(final,), daemon=True, name='command').start()
        elif final and self.assist is not None and self._answers(final, s):
            how = 'answer'
        elif final:
            if self.cfg['dictation'].get('trailing_space', True) and final[-1] in '.?!,:;':
                final += ' '
            into = winapi.foreground_app()[1]           # where the cursor is now, which may not be where it began
            how = insert.insert(final, self.cfg['dictation']['restore_clipboard_ms'],
                                self.cfg['dictation']['type_instead'], into)
        latency_ms = round((time.monotonic() - s.t_finish) * 1000)
        self.last = {'latency_ms': latency_ms, 'pieces': s.count, 'audio_s': s.audio_s, 'text': final,
                     'how': how, 'error': s.error, 'raw': ' '.join(s.texts)}
        log.info('done: %d pieces, %.1f s of audio, %d characters, %s into %s, finish-to-text %d ms%s', s.count,
                 s.audio_s, len(final), how, into or '?', latency_ms, f', error: {s.error}' if s.error else '')
        if self.store and (final or s.error) and how != 'command':
            try:
                self.store.add_dictation(s.started, s.app, ' '.join(s.texts), final.rstrip(), latency_ms,
                                         s.audio_s, s.count, s.trigger, how)
            except Exception as e:
                log.error('history not saved: %s', type(e).__name__)
        with self.lock:
            self.state, self.session = 'idle', None
        if s.error:
            self.ui.notify(f'Dictation failed: {s.error}')
            self.ui.set_state('idle')
        elif s.on_text and not final:
            threading.Thread(target=s.on_text, args=('',), daemon=True, name='command').start()
            self.ui.set_state('idle')
        else:
            self.ui.set_state('done' if final and how not in ('command', 'answer') else 'idle')

    # ---- cancel ----------------------------------------------------------------------------------------------

    def cancel(self, why='Esc'):
        with self.lock:
            s = self.session
            if self.state != 'listening' or s is None:
                return
            self.state, self.session = 'idle', None
        self.mic.stop()
        s.error = 'cancelled'
        s.pieces.put(None)
        log.info('dictation cancelled (%s)', why)
        self.ui.set_state('idle')
