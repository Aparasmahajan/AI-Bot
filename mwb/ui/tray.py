"""The tray icon and its menu (design §13.2), with pystray. pystray runs its own small message loop on its own
thread; menu clicks are handed to the core's loop through `post`, so all real work happens in one place."""
import pystray

from mwb.ui import art

STATUS = {'idle': 'Ready', 'listening': 'Listening', 'working': 'Writing', 'done': 'Ready', 'paused': 'Paused',
          'loading': 'Loading speech'}


class Tray:
    def __init__(self, post, actions, hotkey_names):
        """post(fn) runs fn on the core's loop; actions maps menu ids to functions; hotkey_names for the labels."""
        self.post, self.actions, self.keys = post, actions, hotkey_names
        self.state, self.detail = 'idle', ''
        self.paused = False
        self.indicator_on = True
        self.recording = False
        self.effort = lambda: 'effort'          # the core puts the governor's status line here
        states =('idle', 'listening', 'working', 'paused', 'loading', 'failed')
        self.icons = {(s, r): art.tray_icon(s, 64, r) for s in states for r in (False, True)}
        self.icon = pystray.Icon('MWB', self.icons['idle', False], self._title(), menu=self._menu())

    def _do(self, name):
        return lambda icon, item: self.post(self.actions[name])

    def _menu(self):
        k = self.keys
        return pystray.Menu(
            pystray.MenuItem(lambda item: f'MWB: {self._status()}', None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f'Talk: double-tap Caps Lock, or hold {k.get("dictate") or "(no shortcut)"}', None,
                             enabled=False),
            pystray.MenuItem('Copy last dictation', self._do('copy_last')),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: (f'Stop recording ({k.get("meeting") or "no shortcut"})' if self.recording
                                           else f'Record this call ({k.get("meeting") or "no shortcut"})'),
                             self._do('meeting')),
            pystray.MenuItem(f'Today page: meetings and transcripts ({k.get("today") or "no shortcut"})',
                             self._do('today'), default=True),
            pystray.MenuItem('Import a transcript…', self._do('import')),
            pystray.MenuItem(f"Write today's journal now ({k.get('journal') or 'no shortcut'})", self._do('journal')),
            pystray.MenuItem('Journal folder', self._do('journal_folder')),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Show indicator (double-tap Alt)', self._do('toggle_indicator'),
                             checked=lambda item: self.indicator_on),
            pystray.MenuItem(f'Pause ({k.get("pause") or "no shortcut"})', self._do('toggle_pause'),
                             checked=lambda item: self.paused),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: f'Performance: {self.effort()}…', self._do('setup')),
            pystray.MenuItem('Settings…', self._do('settings_window')),
            pystray.MenuItem('Set API key…', self._do('api_key')),
            pystray.MenuItem('Settings file', self._do('settings')),
            pystray.MenuItem('Log folder', self._do('logs')),
            pystray.MenuItem('Restart MWB', self._do('restart')),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f'Quit MWB ({k.get("quit") or "no shortcut"})', self._do('quit')))

    def _status(self):
        s = 'Paused' if self.paused else STATUS.get(self.state, self.state.capitalize())
        s = f'{s}. Recording a call' if self.recording else s
        return f'{s}. {self.detail}' if self.detail else s

    def _title(self):
        return f'MWB: {self._status()}'[:127]

    def start(self):
        self.icon.run_detached()
        self.icon.visible = True

    def set_state(self, state, detail=None):
        self.state = state
        if detail is not None:
            self.detail = detail
        shown = 'paused' if self.paused else ('idle' if state == 'done' else state)
        self.icon.icon = self.icons.get((shown, self.recording), self.icons['idle', self.recording])
        self.icon.title = self._title()
        self.icon.update_menu()

    def set_recording(self, on):
        self.recording = on
        self.set_state(self.state)

    def set_paused(self, paused):
        self.paused = paused
        self.set_state(self.state)

    def notify(self, message):
        try:
            self.icon.notify(message, 'MWB')
        except Exception:
            pass

    def stop(self):
        try:
            self.icon.visible = False
            self.icon.stop()
        except Exception:
            pass
