"""MWB's core (design §8): one instance, asleep in one Windows message loop, woken by a hotkey, the 15 ms key check,
or a menu click. Heavy work goes to threads and to the speech worker process; the loop never waits on it.

  .venv\\Scripts\\pythonw.exe -m mwb        (or double-click "Start MWB.cmd")

Phase 1: dictation by double-tapping Caps Lock or holding push-to-talk, the tray, the indicator, the speech worker
and its memory guard, and the dictation history. Phases 2 to 4 add meetings, understanding and the daily journal."""
import ctypes, ctypes.wintypes as wt, logging, logging.handlers, os, queue, subprocess, sys, threading, time

from mwb import __version__, config, machine, memory_guard, recovery, winapi
from mwb.effort import Governor
from mwb.winapi import user32

log = logging.getLogger('mwb')
TICK_MS = 15
EXIT_RESTART, EXIT_FAULT = 3, 2     # the watchdog starts a new core at once after 3, and counts 2 as a crash
TICK_FAULTS = 20                    # this many failed ticks in a minute: let the watchdog start a fresh core
user32.SetTimer.restype = ctypes.c_size_t
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, ctypes.c_void_p]
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]


def setup_logging():
    folder = config.LOCAL / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(folder / 'mwb.log', maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.INFO)
    logging.getLogger('comtypes').setLevel(logging.WARNING)      # its cache messages say nothing useful
    if sys.stderr and sys.stderr.isatty():
        root.addHandler(logging.StreamHandler())
    sys.excepthook = lambda t, v, tb: log.critical('crash', exc_info=(t, v, tb))
    threading.excepthook = lambda a: log.error('thread %s crashed', a.thread.name if a.thread else '?',
                                               exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    return folder


class UI:
    """What the skills talk to: the indicator and the tray, both of which accept calls from any thread."""

    def __init__(self, indicator, tray, post, hotkey_names):
        self.indicator, self.tray, self.post, self.names = indicator, tray, post, hotkey_names

    def hotkey_name(self, name):
        return self.names.get(name)

    def set_recording(self, on):
        self.indicator.set_recording(on)
        self.tray.set_recording(on)

    def set_state(self, state):
        self.indicator.set_state(state)
        self.tray.set_state(state)

    def set_level(self, level):
        self.indicator.set_level(level)

    def set_words(self, words):
        self.indicator.set_words(words)

    def notify(self, message):
        self.tray.notify(message)


class App:
    def __init__(self):
        from mwb.audio.capture import FileSource, Mic
        from mwb.hotkeys import HoldWatch, Hotkeys, TapWatcher, pretty
        from mwb.skills import cleanup
        from mwb.skills.dictate import Dictation
        from mwb.llm.router import Router
        from mwb.skills.assist import Assist
        from mwb.skills.meeting import Meetings
        from mwb.skills.journal import Journal
        from mwb.skills.notes import Understanding
        from mwb.sensors.activity import ActivityWatch
        from mwb.store.db import Store
        from mwb.supervisor import SpeechWorker
        from mwb.ui.cards import Cards
        from mwb.ui.indicator import Indicator
        from mwb.ui.today import TodayPage
        from mwb.ui.tray import Tray

        self.HoldWatch = HoldWatch
        self.governor = None                # set up below, once the settings are read
        self.tid = ctypes.windll.kernel32.GetCurrentThreadId()
        self.inbox = queue.Queue()
        self.cfg = cfg = config.load()
        self.logs = setup_logging()
        log.info('MWB %s starting (pid %d, %.1f GB free)', __version__, os.getpid(), winapi.free_gb())
        self.crashed = recovery.begin()
        if self.crashed is not None:
            log.warning('the last run did not stop cleanly (started %s)', self.crashed.get('started', '?'))
        self.exit_code = 0
        self.faults = []
        self.settings_mtime = self._settings_mtime()
        self.next_settings_check = time.monotonic() + 5
        if cfg['_problem']:
            log.warning('settings file not used: %s', cfg['_problem'])
        self.governor = Governor(cfg)
        self.machine_fp, self.machine_mtime = None, None

        self.hotkeys = Hotkeys()
        names = {name: self.hotkeys.register(name, cfg['hotkeys'][name])
                 for name in ('dictate', 'pause', 'quit', 'meeting', 'today', 'rewrite', 'email', 'code', 'note',
                              'journal')}
        self.store = Store()
        self.indicator = Indicator(cfg)
        self.tray = Tray(self.post, {
            'copy_last': self.copy_last, 'toggle_indicator': self.toggle_indicator, 'toggle_pause': self.toggle_pause,
            'api_key': self.open_api_key, 'settings': self.open_settings, 'logs': self.open_logs, 'quit': self.quit,
            'meeting': self.toggle_meeting, 'today': self.open_today, 'import': self.import_transcript,
            'journal': self.write_journal, 'journal_folder': self.open_journal_folder,
            'settings_window': self.open_settings_window, 'setup': self.open_setup, 'restart': self.restart_now,
        }, {k: v and pretty(v) for k, v in names.items()})
        self.tray.indicator_on = self.indicator.visible
        self.tray.effort = self.governor.status
        self.ui = UI(self.indicator, self.tray, self.post, {k: v and pretty(v) for k, v in names.items()})
        self.worker = SpeechWorker(cfg, on_state=self.on_worker)
        test_audio = os.environ.get('MWB_TEST_AUDIO')     # tests only: a WAV file plays in place of the mic
        self.mic = FileSource(test_audio, then_silence_s=3.0) if test_audio else Mic()
        self.dictation = Dictation(cfg, self.worker, self.mic, self.ui, self.store,
                                   cleanup.load_dictionary(config.dictionary_files()))
        self.caps = TapWatcher('Caps Lock', winapi.VK_CAPITAL) if cfg['triggers']['talk'] != 'off' else None
        self.alt = TapWatcher('Alt', winapi.VK_MENU) if cfg['indicator']['toggle'] == 'double-tap alt' else None
        self.hold = None
        self.esc = False
        self.low = memory_guard.LowMemoryWatch()
        self.next_memory_check = 0.0
        self.next_meeting_poll = 0.0
        self.next_sync_check = time.monotonic() + 600       # not in the first ten minutes after start
        self.cards = Cards(self.indicator)
        self.today = TodayPage(self.store)
        test_meeting = os.environ.get('MWB_TEST_MEETING')    # tests only: "me.wav;them.wav" in place of the devices
        sources = None
        if test_meeting:
            me, them = test_meeting.split(';')
            sources = {'me': FileSource(me), 'them': FileSource(them)}
        self.meetings = Meetings(cfg, self.store, self.ui, self.cards, sources)
        self.router = Router(cfg, make_room=self.make_room, usage=self.store.log_usage)
        self.understanding = Understanding(cfg, self.store, self.router, self.ui)
        self.meetings.on_ready = self.understanding.enqueue
        self.today.understanding = self.understanding
        self.assist = Assist(cfg, self.router, self.cards, self.ui, self.store)
        self.dictation.assist = self.assist
        self.activity = ActivityWatch(self.store, cfg)
        self.journal = Journal(cfg, self.store, self.router, self.ui)
        self.journal.on_ready = lambda day, manual: manual and self.post(lambda: self.today.open(f'/journal/{day}'))
        self.today.journal = self.journal
        self.next_journal_check = time.monotonic() + 60
        self.command = None                 # (name, HoldWatch, started voice?) while a command key is down
        self.card_esc = False
        self.running = True
        if not names['dictate']:
            self.post(lambda: self.tray.notify('No push-to-talk shortcut could be registered; double-tap Caps Lock '
                                               'to talk.'))
        if self.crashed is not None:
            text = recovery.message(self.crashed, self.meetings.recovered)
            self.post(lambda: self.tray.notify(text))

    # ---- the loop --------------------------------------------------------------------------------------------

    def post(self, fn):
        """Run fn on the loop's thread (from the tray, or any other thread)."""
        self.inbox.put(fn)
        user32.PostThreadMessageW(self.tid, winapi.WM_APP, 0, 0)

    def run(self):
        self.tray.start()
        if self.cfg['dictation']['load_on_start']:
            sp = self.cfg['speech']
            state, free = memory_guard.verdict(sp['model_gb'], sp['margin_gb'])
            if state == 'ok':
                self.worker.ensure('MWB started')
            else:
                log.info('speech loads on the first dictation (%.1f GB free now)', free)
        threading.Thread(target=self._warm_mic, daemon=True, name='mic-warm').start()
        threading.Thread(target=self._warm_focus, daemon=True, name='focus-warm').start()
        threading.Thread(target=self._find_repos, daemon=True, name='repos').start()
        threading.Thread(target=self._machine_check, daemon=True, name='machine').start()
        user32.SetTimer(None, 0, TICK_MS, None)
        msg = wt.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == winapi.WM_TIMER:
                try:
                    self.tick()
                except Exception:
                    self._tick_fault()
            elif msg.message == winapi.WM_HOTKEY:
                self.on_hotkey(self.hotkeys.name_of(msg.wParam))
            elif msg.message == winapi.WM_APP:
                while not self.inbox.empty():
                    try:
                        self.inbox.get_nowait()()
                    except Exception:
                        log.exception('action failed')
            else:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        self.shutdown()

    def _warm_focus(self):
        """The first UI Automation call builds its wrappers (about 2.6 s); do it now, not on the first question."""
        try:
            from mwb.sensors import focus
            focus.in_text_box(10)
        except Exception as e:
            log.info('focus check not ready: %s', type(e).__name__)

    def _tick_fault(self):
        """One failed tick is logged and the loop goes on; a stream of them means the core is stuck in a bad state,
        so it ends with EXIT_FAULT and the watchdog starts a fresh one."""
        log.exception('tick failed')
        now = time.monotonic()
        self.faults = [t for t in self.faults if now - t < 60] + [now]
        if len(self.faults) >= TICK_FAULTS:
            log.critical('%d failed ticks in a minute; ending so the watchdog can start MWB again', len(self.faults))
            self.exit_code = EXIT_FAULT
            self.quit()

    def _settings_mtime(self):
        try:
            return config.USER_FILE.stat().st_mtime
        except OSError:
            return None

    def idle(self):
        """Nothing in progress that a restart would interrupt."""
        return (self.dictation.state == 'idle' and not self.command and not self.meetings.current
                and not self.journal.lock.locked() and not self.cards.card_open)

    def check_settings(self):
        """Your settings file changed (the Settings window, or your own edit): start again to use it, once nothing
        is in progress. A file that doesn't read is reported instead, and the current settings stay."""
        m = self._settings_mtime()
        if m == self.settings_mtime or not self.idle():
            return
        self.settings_mtime = m
        problem = config.load()['_problem']
        if problem:
            self.tray.notify(f'Your settings file has a mistake, so MWB kept its current settings: {problem}'[:250])
            return
        self.restart('settings changed')

    def restart(self, why):
        log.info('starting again: %s', why)
        self.exit_code = EXIT_RESTART
        if not os.environ.get('MWB_WATCHDOG'):          # started without the watchdog: one takes over once we exit
            subprocess.Popen([self._pythonw(), '-m', 'mwb.watchdog', '--after', str(os.getpid())],
                             cwd=str(config.HERE.parents[1]))
        self.quit()

    def _machine_check(self):
        """Which machine is this? A new fingerprint (another laptop, or more memory) gets a first machine file with
        the suggested level, and the setup screen opens so you can choose (§12.6)."""
        try:
            hw = machine.probe()
        except RuntimeError as e:
            log.warning('machine check: %s', e)
            return
        fp = machine.fingerprint(hw)
        data = machine.load(fp)
        if data is None:
            log.info('a new machine (%s): suggesting %s', fp, machine.suggested(machine.profile_of(hw)))
            data = machine.new(hw, fp, self.cfg.get('effort_preference', 'suggested'))
            machine.save(fp, data)
        choice = machine.effort_of(data)
        self.post(lambda: self._use_machine(fp, choice, hw.get('cores')))
        if not choice['chosen']:
            self.post(self.open_setup)

    def _use_machine(self, fp, choice, cores=None):
        self.machine_fp = fp
        try:
            self.machine_mtime = machine.path_of(fp).stat().st_mtime
        except OSError:
            self.machine_mtime = None
        self.governor.set_choice(choice, cores)
        log.info('machine %s: %s', fp, self.governor.status())

    def _check_machine_file(self):
        """The setup screen saved a new choice: use it now."""
        if not self.machine_fp:
            return
        try:
            m = machine.path_of(self.machine_fp).stat().st_mtime
        except OSError:
            return
        if m != self.machine_mtime:
            data = machine.load(self.machine_fp)
            if data:
                self._use_machine(self.machine_fp, machine.effort_of(data), (data.get('hardware') or {}).get('cores'))

    def _find_repos(self):
        """The repository names, so the activity sampler can tell which project a window belongs to."""
        try:
            self.activity.set_repos(self.journal.repo_names())
        except Exception:
            log.exception('repository scan failed')

    def maybe_sync_check(self):
        """Once a week on mains power with a calm CPU: P0-4's ten saved prompts through both routes (§12.7). The
        script refuses the local half by itself when memory is short; results go to docs/bench/p0_4."""
        import datetime
        from mwb.sensors import system
        if self.cfg['llm'].get('sync_check', 'weekly') != 'weekly' or not system.on_mains() or self.dictation.active:
            return
        last = self.store.get_meta('sync_check_at')
        if last and datetime.datetime.now() - datetime.datetime.fromisoformat(last) < datetime.timedelta(days=7):
            return
        cpu = system.CpuWatch()
        time.sleep(1)
        if cpu.sample() > 60:
            return
        script = config.HERE.parents[1] / 'docs' / 'bench' / 'p0_4_sync_check.py'
        if not script.exists():
            return
        self.store.set_meta('sync_check_at', datetime.datetime.now().isoformat(timespec='seconds'))
        exe = sys.executable.replace('pythonw.exe', 'python.exe')
        p = subprocess.Popen([exe, '-I', str(script), '--routes', 'all', '--no-code'], cwd=str(script.parents[2]),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000 | 0x4000)
        winapi.end_with_me(p)
        log.info('weekly sync check started')

    def make_room(self):
        """Before the local model loads: stop the idle speech worker (§11.2)."""
        if not self.dictation.active:
            self.worker.stop('memory for the local model')

    def _warm_mic(self):
        """Load PortAudio now, so opening the mic later takes only the open itself."""
        if not hasattr(self.mic, '_pa'):
            return
        try:
            import pyaudiowpatch
            self.mic._pa = pyaudiowpatch.PyAudio()
        except Exception as e:
            log.warning('audio not ready: %s', type(e).__name__)

    def tick(self):
        now = time.monotonic()
        d = self.dictation
        if self.hold:
            if self.hold.released():
                self.hold = None
                d.finish('released')
                if self.alt:
                    self.alt.reset()             # the Alt of the shortcut is not a tap
                if self.caps:
                    self.caps.reset()
        else:
            if self.caps and self.caps.step(now):
                if d.state == 'listening':
                    d.finish('double tap')
                elif d.state == 'idle':
                    self.start_dictation('caps')
            if self.alt and self.alt.step(now):
                self.toggle_indicator()
        if self.command:
            self.tick_command()
        want_card_esc = self.cards.card_open and d.state != 'listening'
        if want_card_esc != self.card_esc:
            if want_card_esc:
                self.card_esc = bool(self.hotkeys.register('close_card', ['esc']))
            else:
                self.hotkeys.unregister('close_card')
                self.card_esc = False
        want_esc = d.state == 'listening'
        if want_esc != self.esc:
            if want_esc:
                self.esc = bool(self.hotkeys.register('cancel', ['esc']))
            else:
                self.hotkeys.unregister('cancel')
                self.esc = False
        self.indicator.tick(now)
        self.activity.tick(now, self.dictation.paused)
        if now >= self.next_settings_check:
            self.next_settings_check = now + 5
            self.check_settings()
            self._check_machine_file()
        self.governor.tick(now)
        if now >= self.next_journal_check:
            self.next_journal_check = now + 60
            try:
                self.journal.maybe_run()
            except Exception:
                log.exception('journal check failed')
        if now >= self.next_meeting_poll:
            self.next_meeting_poll = now + 5
            try:
                self.meetings.poll()
            except Exception:
                log.exception('meeting check failed')
        if now >= self.next_sync_check:
            self.next_sync_check = now + 3600
            self.maybe_sync_check()
        if now >= self.next_memory_check:
            self.next_memory_check = now + 10
            if self.worker.running and not d.active and self.low.tick():
                log.warning('free memory under 1 GB for 30 s; stopping the idle speech worker')
                self.worker.stop('low memory')

    def on_hotkey(self, name):
        d = self.dictation
        if name == 'dictate':
            if d.state == 'idle':
                if self.start_dictation('hold'):
                    self.hold = self.HoldWatch(self.hotkeys.held_keys('dictate'))
            elif d.state == 'listening':
                d.finish('push-to-talk')
        elif name == 'cancel':
            d.cancel('Esc')
        elif name == 'close_card':
            self.cards.close_cards()
        elif name == 'journal':
            self.write_journal()
        elif name in ('rewrite', 'email', 'code', 'note'):
            if d.state == 'idle' and not self.command:
                self.command = [name, self.HoldWatch(self.hotkeys.held_keys(name)), False]
        elif name == 'pause':
            self.toggle_pause()
        elif name == 'meeting':
            self.toggle_meeting()
        elif name == 'today':
            self.open_today()
        elif name == 'quit':
            self.quit()

    def tick_command(self):
        """A command key: a quick press explains; holding it records what you say (§9.2, §9.4, §9.5)."""
        name, hold, voice = self.command
        actions = {'email': (self.assist.email_explain, self.assist.email_draft),
                   'code': (self.assist.code_explain, self.assist.code_write),
                   'rewrite': (self._rewrite_hint, self.assist.rewrite),
                   'note': (self._note_hint, self._note)}
        press, spoken = actions[name]
        if not voice and hold.held_s >= 0.35 and not hold.released():
            _, app = winapi.foreground_app()
            if self.dictation.start('command', app, on_text=spoken):
                self.command[2] = True
            else:
                self.command = None
            return
        if hold.released():
            self.command = None
            if self.alt:
                self.alt.reset()
            if voice:
                self.dictation.finish('command released')
            else:
                press()

    def _rewrite_hint(self):
        card = self.cards.result('Rewrite')
        card.set_text('Select some text, then hold the keys and say how to change it: "shorter", "more formal", '
                      '"bullet points", "translate to Hindi".')

    def _note_hint(self):
        card = self.cards.result('Voice note')
        card.set_text("Hold the keys and say your note while holding: it goes into today's journal, under Notes.")

    def _note(self, text):
        """From the command's thread: save the note, then show the tick once the dictation has finished."""
        if self.journal.add_note(text):
            self.post(lambda: self.indicator.set_state('done', 'Noted'))

    def start_dictation(self, trigger):
        _, app = winapi.foreground_app()
        if self.alt:
            self.alt.reset()
        return self.dictation.start(trigger, app)

    def on_worker(self, state, detail=''):
        if state == 'loading':
            self.tray.set_state(self.tray.state, 'Loading speech…')
        elif state == 'ready':
            self.tray.set_state(self.tray.state, '')
        elif state == 'stopped':
            self.tray.set_state(self.tray.state, 'Speech loads when you talk.')
        elif state == 'failed':
            self.tray.set_state(self.tray.state, 'Speech could not start.')
            self.tray.notify(detail)

    # ---- menu actions ----------------------------------------------------------------------------------------

    def toggle_indicator(self):
        self.tray.indicator_on = self.indicator.toggle()
        self.tray.set_state(self.tray.state)

    def toggle_pause(self):
        paused = not self.dictation.paused
        if paused and self.dictation.state == 'listening':
            self.dictation.cancel('paused')
        self.dictation.paused = paused
        self.indicator.set_paused(paused)
        self.tray.set_paused(paused)
        log.info('paused' if paused else 'resumed')

    def toggle_meeting(self):
        self.meetings.toggle()

    def open_today(self):
        self.today.open()

    def write_journal(self):
        threading.Thread(target=self.journal.write, kwargs={'manual': True}, daemon=True, name='journal').start()

    def open_journal_folder(self):
        folder = self.journal.folder()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def import_transcript(self):
        def chosen(path):
            if path:
                self.post(lambda: threading.Thread(target=self.meetings.import_file, args=(path,), daemon=True).start())
        self.cards.pick_transcript(chosen)

    def copy_last(self):
        text = self.store.last_dictation()
        if text:
            winapi.clipboard_set(text, private=True)
        else:
            self.tray.notify('No dictation yet.')

    def _pythonw(self):
        exe = sys.executable
        return exe[:-10] + 'pythonw.exe' if exe.lower().endswith('python.exe') else exe

    def open_api_key(self):
        subprocess.Popen([self._pythonw(), '-m', 'mwb.ui.api_key'], cwd=str(config.HERE.parents[1]))

    def open_settings(self):
        if not config.USER_FILE.exists():
            config.APPDATA.mkdir(parents=True, exist_ok=True)
            config.USER_FILE.write_text(
                '# Your MWB settings. Copy any line from the built-in defaults and change it here; MWB reads this\n'
                '# file when it starts. The defaults, with notes, are in the MWB folder: mwb\\config\\default.toml\n'
                '#\n# Example:\n# [indicator]\n# size = "medium"\n', encoding='utf-8')
        os.startfile(config.USER_FILE)

    def open_settings_window(self):
        subprocess.Popen([self._pythonw(), '-m', 'mwb.ui.settings'], cwd=str(config.HERE.parents[1]))

    def open_setup(self):
        subprocess.Popen([self._pythonw(), '-m', 'mwb.ui.setup'], cwd=str(config.HERE.parents[1]))

    def restart_now(self):
        if self.idle():
            self.restart('you asked')
        else:
            self.tray.notify('MWB will start again once the current dictation, call or journal is finished.')
            self.settings_mtime = None                  # check_settings() restarts it when idle

    def open_logs(self):
        os.startfile(self.logs)

    def quit(self):
        log.info('quitting')
        self.running = False
        user32.PostThreadMessageW(self.tid, winapi.WM_QUIT, 0, 0)

    def shutdown(self):
        if self.dictation.state == 'listening':
            self.dictation.cancel('quit')
        self.activity.flush()
        self.meetings.close()
        self.understanding.close()
        self.router.close()
        self.today.close()
        self.cards.close()
        self.hotkeys.unregister_all()
        self.tray.stop()
        self.indicator.close()
        self.worker.stop('MWB quit')
        self.mic.close()
        self.store.close()
        if self.exit_code != EXIT_FAULT:                # a fault counts as a crash at the next start
            recovery.end()
        log.info('MWB stopped')


def main():
    winapi.dpi_aware()
    if not winapi.single_instance():
        return 0                        # MWB is already running; its tray icon is the one to use
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('MWB.Core')
    except (AttributeError, OSError):
        pass
    app = App()
    app.run()
    return app.exit_code
