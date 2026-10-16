"""The effort governor (design §12.5): every 30 seconds it sets a level from E1 to E4 for each feature, from your
choice on the setup screen and the laptop's state, and turns the knobs that level means.

Your choice: a fixed level, or automatic within a range (lowest to highest), what happens on battery, and a
different ceiling for any feature (journal, meetings, dictation, email and code). Automatic goes one level down on
battery and two below 30 % charge, and one more while the CPU stays above 80 % for 30 s or free memory is under
2 GB; it never goes below your lowest level, and comes back up when those end. A fixed level ignores all that; the
memory guard (§11.2) still defers work rather than let MWB run out of memory.

The knobs are settings MWB already reads when it starts a job, so a change applies to the next one: speech and
whisper threads, how long the speech engine stays warm, whether meetings are transcribed during the call, and the
local model's threads and size. A setting you set yourself in config.toml always wins over the governor."""
import logging, os

from mwb import machine, winapi
from mwb.sensors import system

log = logging.getLogger('mwb.effort')
LEVELS = machine.LEVELS
EVERY_S = 30
# 0 means "all physical cores"
KNOBS = {
    'E1': {'speech_threads': 2, 'live_threads': 1, 'after_threads': 2, 'local_threads': 2, 'local_big': False,
           'warm_min': 5, 'live_meetings': False},
    'E2': {'speech_threads': 4, 'live_threads': 2, 'after_threads': 4, 'local_threads': 4, 'local_big': True,
           'warm_min': 15, 'live_meetings': True},
    'E3': {'speech_threads': 4, 'live_threads': 4, 'after_threads': 4, 'local_threads': 4, 'local_big': True,
           'warm_min': 30, 'live_meetings': True},
    'E4': {'speech_threads': 0, 'live_threads': 4, 'after_threads': 0, 'local_threads': 0, 'local_big': True,
           'warm_min': 60, 'live_meetings': True},
}


def level_for(choice, feature, mains=True, percent=None, strained=False):
    """One feature's level now. choice is machine.effort_of(...)."""
    top = choice['by_feature'].get(feature, choice['highest'])
    if choice['mode'] == 'fixed':
        return top
    drop = 0
    if not mains and choice['on_battery'] == 'lower':
        drop += 2 if percent is not None and percent < 30 else 1
    if strained:
        drop += 1
    floor = min(LEVELS.index(choice['lowest']), LEVELS.index(top))
    return LEVELS[max(floor, LEVELS.index(top) - drop)]


class Governor:
    def __init__(self, cfg, cores=None):
        self.cfg = cfg
        self.cores = cores or max(2, (os.cpu_count() or 4) // 2)
        self.choice = machine.effort_of(None)
        self.cpu = system.CpuWatch(limit=80, for_s=30)
        self.levels = {}
        self.why = ''
        self.next = 0.0

    def set_choice(self, choice, cores=None):
        self.choice = choice
        if cores:
            self.cores = cores
        self.update()

    def tick(self, now):
        if now >= self.next:
            self.next = now + EVERY_S
            self.update()
        else:
            self.cpu.sample()

    def update(self, mains=None, percent=None, strained=None):
        """Work out the levels and turn the knobs. The arguments are for tests; normally they are read here."""
        if mains is None:
            mains, percent = system.battery()
        if strained is None:
            self.cpu.sample()
            strained = self.cpu.busy() or winapi.free_gb() < 2.0
        levels = {f: level_for(self.choice, f, mains, percent, strained) for f in machine.FEATURES}
        why = [] if self.choice['mode'] == 'fixed' else (
            (['on battery'] if not mains and self.choice['on_battery'] == 'lower' else []) +
            (['busy or short of memory'] if strained else []))
        if levels != self.levels:
            log.info('effort: %s%s', ', '.join(f'{f} {l}' for f, l in levels.items()),
                     f' ({", ".join(why)})' if why else '')
        self.levels, self.why = levels, ', '.join(why)
        self.apply()
        return levels

    def knobs(self, feature):
        k = dict(KNOBS[self.levels.get(feature, self.choice['highest'])])
        return {n: (self.cores if v == 0 and n.endswith('threads') else v) for n, v in k.items()}

    def _set(self, section, key, value):
        if (section, key) not in self.cfg.get('_user', ()):        # your own setting always wins
            self.cfg[section][key] = value

    def apply(self):
        d, m, e, j = (self.knobs(f) for f in ('dictation', 'meetings', 'email_code', 'journal'))
        self._set('dictation', 'threads', d['speech_threads'])
        self._set('dictation', 'idle_unload_min', d['warm_min'])
        self._set('meetings', 'live_threads', m['live_threads'])
        self._set('meetings', 'after_threads', m['after_threads'])
        self._set('meetings', 'live', m['live_meetings'])
        self._set('llm', 'local_threads', max(e['local_threads'], j['local_threads']))
        self._set('llm', 'local_big_for', [s for s, k in (('code', e), ('journal', j)) if k['local_big']])

    def status(self):
        """One line for the tray: the overall level, and why it is lower than your choice."""
        top = max(self.levels.values(), key=LEVELS.index) if self.levels else self.choice['highest']
        return f'Effort {top} · {machine.NAMES[top]}' + (f' ({self.why})' if self.why else '')
