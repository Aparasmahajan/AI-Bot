"""Meetings (design §9.3): detect the call, decide whether to record, record two lanes, transcribe in the
background, and have the transcript ready about a minute after you hang up. No audio is kept.

Recording rules: an app's policy comes from config/vc_apps.toml, overridden by your own answers. During the first
week MWB asks before every recording; personal apps (WhatsApp, Discord, Telegram, Phone Link) always ask.

Transcription runs live only on mains power with a calm CPU (decision of 13 Oct, from P0-8); otherwise the pieces
wait on disk and are transcribed right after the call. Each piece is deleted the moment it is transcribed. Pieces
left over by a crash are picked up at the next start."""
import collections, datetime, logging, queue, re, shutil, threading, time, wave
from array import array
from pathlib import Path

from mwb import config, winapi
from mwb.audio.recorder import Recorder
from mwb.sensors import system
from mwb.sensors.meeting_detector import Apps, Call, Detector
from mwb.skills import transcripts
from mwb.supervisor import Whisper, WorkerError

log = logging.getLogger('mwb.meeting')
AUDIO = config.LOCAL / 'audio'
PIECE = re.compile(r'^(me|them)-(\d{9})\.wav$')
WEEK = datetime.timedelta(days=7)


def _now():
    return datetime.datetime.now().replace(microsecond=0)


class Meetings:
    """poll() every 5 s from the core's loop; toggle() for Ctrl+Alt+M. ui gets recording on/off and notices."""

    def __init__(self, cfg, store, ui, cards, sources=None):
        self.cfg, self.store, self.ui, self.cards = cfg, store, ui, cards
        self.m = cfg['meetings']
        self.apps = Apps(choices=store.app_choices())
        self.detector = Detector(self.apps)
        self.whisper = Whisper(cfg)
        self.cpu = system.CpuWatch()
        self.sources = sources              # tests: lanes from files
        self.lock = threading.Lock()
        self.current = None                 # (meeting id, Call or None, Recorder, start time)
        self.asking = set()                 # call keys with a question on screen
        self.skipped = set()                # call keys you said no to, until the call ends
        self.wake = threading.Event()
        self.running = True
        self.languages = {}                 # meeting id -> Counter of what whisper heard
        self.recovered = 0                  # meetings a crash interrupted, picked up at this start
        self.on_ready = None                # from Phase 3: notes and the label follow a ready transcript
        self.to_write = queue.Queue()       # pieces leave the audio threads at once; this thread writes them
        self._recover()
        threading.Thread(target=self._write_loop, daemon=True, name='meeting-write').start()
        self.worker = threading.Thread(target=self._transcribe_loop, daemon=True, name='meeting-asr')
        self.worker.start()

    # ---- detection and the decision --------------------------------------------------------------------------

    def poll(self):
        if not self.m['detect']:
            return
        self.cpu.sample()
        for kind, call in self.detector.poll():
            log.info('call %s: %s (%s), policy %s%s', kind, call.app_id, call.name, call.policy,
                     ', personal' if call.personal else '')
            if kind == 'start':
                self._decide(call)
            else:
                self.asking.discard(call.key)
                self.skipped.discard(call.key)
                with self.lock:
                    cur = self.current
                if cur and cur[1] is not None and cur[1].key == call.key:
                    self.stop('the call ended')

    def _ask_first(self):
        mode = self.m['ask_before_recording']
        if mode == 'always':
            return True
        if mode == 'never':
            return False
        since = self.store.get_meta('meetings_since')
        if not since:
            self.store.set_meta('meetings_since', _now().isoformat())
            return True
        return _now() - datetime.datetime.fromisoformat(since) < WEEK

    def _decide(self, call):
        if call.policy == 'never' or call.key in self.skipped:
            return
        if self.current:
            log.info('already recording; %s not started', call.app_id)
            return
        if call.personal or call.policy == 'ask' or self._ask_first():
            self.asking.add(call.key)
            note = 'This app is marked personal, so MWB always asks.' if call.personal else (
                'MWB asks before every recording in its first week.' if call.policy == 'record' else '')
            self.cards.ask_record(call, lambda choice: self.ui.post(lambda: self._answer(call, choice)), note)
            return
        self.start(call)

    def _answer(self, call, choice):
        self.asking.discard(call.key)
        log.info('you chose %s for %s', choice, call.app_id)
        if choice == 'never':
            self.store.set_choice(call.app_id, 'never')
            self.apps.choices[call.app_id] = 'never'
            self.ui.notify(f'MWB will not record {call.name} calls. Change this in the settings file.')
        elif choice == 'skip':
            self.skipped.add(call.key)
        elif choice == 'record':
            if call.key in self.detector.calls:            # still on the call
                self.start(call)

    # ---- recording -------------------------------------------------------------------------------------------

    def toggle(self):
        """Ctrl+Alt+M: stop the recording, or record whatever is happening now."""
        if self.current:
            self.stop('you pressed the shortcut')
        else:
            _, exe = winapi.foreground_app()
            self.start(Call('manual', 'manual', 'Manual recording', 'record', False, time.time(),
                            title=f'Recorded by hand in {exe or "?"}'))

    def start(self, call):
        with self.lock:
            if self.current:
                return
            started = datetime.datetime.fromtimestamp(time.time()).replace(microsecond=0)
            mid = self.store.new_meeting(app_id=call.app_id, app_name=call.name, title=call.title or None,
                                         started=started.isoformat(), status='recording', source='recorded',
                                         camera=int(call.camera))
            folder = AUDIO / f'm{mid}'
            folder.mkdir(parents=True, exist_ok=True)
            rec = Recorder(self.cfg, lambda lane, piece: self._piece(mid, folder, lane, piece), self.sources)
            try:
                rec.start()
            except Exception as e:
                log.error('recording could not start: %s', type(e).__name__)
                self.store.update_meeting(mid, status='failed', ended=_now().isoformat())
                self.ui.notify("MWB couldn't open the microphone or the speakers to record.")
                return
            self.current = (mid, None if call.key == 'manual' else call, rec, started)
        log.info('recording meeting %d (%s)', mid, call.app_id)
        self.ui.set_recording(True)
        key = self.ui.hotkey_name('meeting') or 'the tray menu'
        self.ui.notify(f'Recording {call.title or "a call"} ({call.name}). Press {key} to stop.')
        if self.m['outlook'] != 'off' and call.app_id != 'manual':
            threading.Thread(target=self._calendar, args=(mid, started, call), daemon=True,
                             name='calendar').start()

    def _calendar(self, mid, started, call):
        from mwb.collectors import outlook
        found = outlook.meeting_at(started, self.m['outlook'])
        if found and found['subject']:
            self.store.update_meeting(mid, title=found['subject'])
            log.info('meeting %d: title from the calendar', mid)

    def _piece(self, mid, folder, lane, piece):
        """From an audio thread: hand the piece on and return at once, so the recording never skips."""
        self.to_write.put((mid, folder, lane, piece))

    def _write_loop(self):
        while True:
            job = self.to_write.get()
            if isinstance(job, threading.Event):    # stop() waits for everything before this marker
                job.set()
                continue
            mid, folder, lane, piece = job
            samples = piece.samples
            if piece.gain >= 2.0:               # quiet audio (a soft call) is levelled; whisper has no gain option
                g = piece.gain
                samples = array('h', (max(-32768, min(32767, int(x * g))) for x in samples))
            path = folder / f'{lane}-{round(piece.start_s * 1000):09d}.wav'
            tmp = path.with_suffix('.part')
            with wave.open(str(tmp), 'wb') as w:
                w.setnchannels(1), w.setsampwidth(2), w.setframerate(piece.rate)
                w.writeframes(samples.tobytes())
            tmp.replace(path)                   # whole files only, so a crash never leaves half a piece
            self.store.bump_meeting(mid, 'pieces')
            self.wake.set()

    def stop(self, why=''):
        with self.lock:
            cur, self.current = self.current, None
        if not cur:
            return
        mid, call, rec, started = cur
        lanes = rec.stop()
        rec.close()
        written = threading.Event()
        self.to_write.put(written)
        written.wait(15)                        # the last pieces are on disk before the meeting counts as ended
        self.store.update_meeting(mid, ended=_now().isoformat(), status='transcribing')
        log.info('meeting %d stopped (%s); lanes %s s', mid, why, lanes)
        self.ui.set_recording(False)
        self.wake.set()

    # ---- transcription ---------------------------------------------------------------------------------------

    def _recover(self):
        """A crash during a call leaves the meeting 'recording' and its pieces on disk: finish them now. The call
        counts as ended when its last piece was written, not when MWB started again."""
        for m in self.store.meetings(200, status='recording'):
            self.store.update_meeting(m['id'], status='transcribing', ended=m['ended'] or self._last_heard(m))
            self.recovered += 1
            log.info('meeting %d was interrupted; transcribing what was recorded', m['id'])

    def _last_heard(self, m):
        folder = AUDIO / f'm{m["id"]}'
        times = [p.stat().st_mtime for p in folder.iterdir()] if folder.exists() else []
        ends = [s[3] or s[2] for s in self.store.segments(m['id'])]
        started = datetime.datetime.fromisoformat(m['started'])
        when = max([started] + [datetime.datetime.fromtimestamp(t).replace(microsecond=0) for t in times] +
                   [started + datetime.timedelta(seconds=round(e)) for e in ends])
        return when.isoformat()

    def _next_piece(self):
        """(meeting id, path, live?) of the next piece to transcribe, oldest meeting first."""
        live_id = self.current[0] if self.current else None
        for m in sorted(self.store.meetings(200, status='transcribing'), key=lambda x: x['id']) + \
                ([self.store.meeting(live_id)] if live_id else []):
            folder = AUDIO / f'm{m["id"]}'
            pieces = sorted((p for p in folder.glob('*.wav') if PIECE.match(p.name)),
                            key=lambda p: (int(PIECE.match(p.name).group(2)), p.name)) if folder.exists() else []
            if pieces:
                return m['id'], pieces[0], m['id'] == live_id
            if m['status'] == 'transcribing':
                self._finish(m['id'])
        return None

    def _transcribe_loop(self):
        while self.running:
            self.wake.wait(15)
            self.wake.clear()
            while self.running:
                job = self._next_piece()
                if not job:
                    break
                mid, path, live = job
                if live and not (self.m.get('live', True) and system.on_mains() and not self.cpu.busy()):
                    break                       # live only on mains with a calm CPU (and not at effort E1)
                if not self.whisper.memory_ok():
                    log.info('waiting for memory to transcribe (%.2f GB free)', winapi.free_gb())
                    break
                self._transcribe(mid, path, live)

    def _transcribe(self, mid, path, live):
        lane, start_ms = PIECE.match(path.name).groups()
        threads = self.m['live_threads'] if live else self.m['after_threads']
        t0 = time.perf_counter()
        try:
            segs, lang = self.whisper.transcribe(path, threads=threads, low_priority=True)
        except WorkerError as e:
            log.error('piece %s of meeting %d: %s', path.name, mid, e)
            path.rename(path.with_suffix('.failed'))
            return
        offset = int(start_ms) / 1000
        speaker = 'You' if lane == 'me' else 'Them'
        rows = [(speaker, round(offset + a, 2), round(offset + b, 2), text) for a, b, text in segs]
        if rows:
            self.store.add_segments(mid, rows)
        if lang:
            counts = self.languages.setdefault(mid, collections.Counter())
            counts[lang] += 1
        self.store.bump_meeting(mid, 'pieces_done')
        if not self.m['keep_audio']:
            path.unlink(missing_ok=True)
        else:
            path.rename(path.with_suffix('.kept'))
        log.info('meeting %d: %s piece at %.0f s -> %d lines in %.1f s (%s, %d threads)', mid, lane, offset,
                 len(rows), time.perf_counter() - t0, 'live' if live else 'after the call', threads)

    def _finish(self, mid):
        """All pieces done: one timeline, echo removed, and the notice."""
        rows = self.store.segments(mid)
        merged = transcripts.merge([(s, a, b, t) for _, s, a, b, t in rows])
        keep = {(r[0], r[1], r[3]) for r in merged}
        drop = [i for i, s, a, _, t in rows if (s, a, t) not in keep]
        if drop:
            self.store.delete_segments(drop)
        lang = self.languages.pop(mid, collections.Counter()).most_common(1)
        self.store.update_meeting(mid, status='ready', language=lang[0][0] if lang else None)
        folder = AUDIO / f'm{mid}'
        if folder.exists() and not any(folder.glob('*.wav')):
            shutil.rmtree(folder, ignore_errors=True)
        m = self.store.meeting(mid)
        minutes = 0
        if m['ended']:
            minutes = round((datetime.datetime.fromisoformat(m['ended']) -
                             datetime.datetime.fromisoformat(m['started'])).total_seconds() / 60)
        log.info('meeting %d ready: %d lines, %d removed as echo or noise', mid, len(rows) - len(drop), len(drop))
        key = self.ui.hotkey_name('today') or 'the tray menu'
        self.ui.notify(f'Transcript ready: {m["title"] or m["app_name"]} · {minutes} min. Press {key} to open it.')
        if self.on_ready:
            self.on_ready(mid)

    # ---- import ----------------------------------------------------------------------------------------------

    def import_file(self, path):
        rows = transcripts.parse_file(path)
        if not rows:
            self.ui.notify("That file didn't look like a transcript.")
            return None
        p = Path(path)
        started = datetime.datetime.fromtimestamp(p.stat().st_mtime).replace(microsecond=0)
        mid = self.store.new_meeting(app_id='imported', app_name='Imported', title=p.stem[:200],
                                     started=started.isoformat(), status='ready', source='imported')
        self.store.add_segments(mid, transcripts.tidy(rows))
        log.info('imported a transcript as meeting %d: %d lines', mid, len(rows))
        self.ui.notify(f'Imported {len(rows)} lines from {p.name}.')
        if self.on_ready:
            self.on_ready(mid)
        return mid

    def close(self):
        self.stop('MWB quit')
        self.running = False
        self.wake.set()
