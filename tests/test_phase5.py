"""Phase 5: saving settings, effort levels, the machine file, crash recovery and the watchdog, forgetting, the eight
skins and the settings window's checks. Nothing here opens a visible window or the mic."""
import datetime, tempfile, tomllib, unittest
from pathlib import Path
from unittest import mock

from mwb import config, effort, machine, recovery, watchdog
from mwb.skills import forget
from mwb.store.db import Store
from mwb.ui import art

P0_6 = {'cpu': '11th Gen Intel(R) Core(TM) i7-1185G7 @ 3.00GHz', 'cores': 4, 'threads': 8, 'avx2': True,
        'avx512': True, 'ram_gb': 16, 'memory_sticks': 1, 'memory_mts': 3200, 'bandwidth_peak_gbs': 25.6,
        'gpu': ['Intel(R) Iris(R) Xe Graphics'], 'npu': False}


def tmp():
    return Path(tempfile.mkdtemp(prefix='mwb-test-'))


class SaveSettings(unittest.TestCase):
    def test_only_changed_lines_and_comments_stay(self):
        p = tmp() / 'config.toml'
        p.write_text('# mine\n[indicator]\nsize = "medium"   # bigger\n\n[journal]\nmanager_email = "a#b@x.com"  '
                     '# boss\n', encoding='utf-8')
        config.save_user({'indicator': {'size': 'large', 'skin': 'orb'}, 'journal': {'manager_email': 'c@x.com'},
                          'llm': {'local_only': ['email-style', 'journal']}}, p)
        text = p.read_text(encoding='utf-8')
        self.assertIn('# mine', text)
        self.assertIn("size = 'large'   # bigger", text)
        self.assertIn("manager_email = 'c@x.com'   # boss", text)
        self.assertEqual(tomllib.loads(text)['llm']['local_only'], ['email-style', 'journal'])
        self.assertEqual(tomllib.loads(text)['indicator']['skin'], 'orb')

    def test_windows_paths_and_quotes(self):
        p = tmp() / 'config.toml'
        config.save_user({'journal': {'folder': r'%USERPROFILE%\Documents\Work', 'denylist': ["it's", '*bank*']}}, p)
        d = tomllib.loads(p.read_text(encoding='utf-8'))['journal']
        self.assertEqual(d['folder'], r'%USERPROFILE%\Documents\Work')
        self.assertEqual(d['denylist'], ["it's", '*bank*'])

    def test_your_keys_are_known(self):
        with mock.patch.object(config, 'USER_FILE', tmp() / 'none.toml'):
            self.assertEqual(config.load()['_user'], set())


class Effort(unittest.TestCase):
    def choice(self, **over):
        c = machine.effort_of({'profile': 'lean', 'effort': {'mode': 'auto', 'highest': 'E3', 'lowest': 'E1',
                                                              'on_battery': 'lower'}})
        c.update(over)
        return c

    def test_levels(self):
        c = self.choice()
        self.assertEqual(effort.level_for(c, 'dictation'), 'E3')
        self.assertEqual(effort.level_for(c, 'dictation', mains=False, percent=80), 'E2')
        self.assertEqual(effort.level_for(c, 'dictation', mains=False, percent=20), 'E1')
        self.assertEqual(effort.level_for(c, 'dictation', strained=True), 'E2')
        self.assertEqual(effort.level_for(c, 'dictation', mains=False, percent=10, strained=True), 'E1')   # floor

    def test_fixed_and_per_feature(self):
        c = self.choice(mode='fixed', by_feature={'journal': 'E1'})
        self.assertEqual(effort.level_for(c, 'dictation', mains=False, percent=5, strained=True), 'E3')
        self.assertEqual(effort.level_for(c, 'journal'), 'E1')
        c = self.choice(on_battery='keep')
        self.assertEqual(effort.level_for(c, 'meetings', mains=False, percent=50), 'E3')

    def test_knobs_and_your_settings_win(self):
        cfg = config.load()
        cfg['_user'] = {('dictation', 'threads')}
        cfg['dictation']['threads'] = 6
        g = effort.Governor(cfg, cores=4)
        g.choice = self.choice(highest='E1', lowest='E1')
        g.update(mains=True, strained=False)
        self.assertEqual(cfg['dictation']['threads'], 6)                     # yours
        self.assertEqual(cfg['dictation']['idle_unload_min'], 5)
        self.assertFalse(cfg['meetings']['live'])
        self.assertEqual(cfg['llm']['local_big_for'], [])
        g.choice = self.choice(highest='E3')
        g.update(mains=True, strained=False)
        self.assertTrue(cfg['meetings']['live'])
        self.assertEqual(cfg['llm']['local_big_for'], ['code', 'journal'])
        self.assertIn('E3', g.status())


class Machine(unittest.TestCase):
    def test_same_fingerprint_as_p0_6(self):
        self.assertEqual(machine.fingerprint(P0_6), '530285546f')
        self.assertEqual(machine.profile_of(P0_6), 'lean')
        self.assertEqual(machine.profile_of({**P0_6, 'ram_gb': 32, 'memory_sticks': 2}), 'balanced')
        self.assertEqual(machine.profile_of({**P0_6, 'gpu': ['NVIDIA GeForce RTX 4060']}), 'performance')

    def test_levels_this_laptop_can_run(self):
        self.assertEqual(machine.suggested('lean'), 'E2')
        self.assertNotIn('E4', machine.available('lean'))
        self.assertIn('GPU', machine.why_not('E4', 'lean'))
        self.assertEqual(machine.suggested('lean', 'max-available'), 'E3')
        self.assertEqual(machine.effort_of({'profile': 'lean', 'effort': {'highest': 'E4'}})['highest'], 'E2')

    def test_file_round_trip(self):
        with mock.patch.object(machine, 'FOLDER', tmp()):
            data = machine.new(P0_6, '530285546f')
            data['effort']['by_feature'] = {'journal': 'E3'}
            machine.save('530285546f', data)
            machine.save('530285546f', data)                                   # the second keeps a .bak
            back = machine.load('530285546f')
            self.assertEqual(back['hardware']['gpu'], P0_6['gpu'])
            self.assertEqual(machine.effort_of(back)['by_feature'], {'journal': 'E3'})
            self.assertTrue((machine.FOLDER / '530285546f.toml.bak').exists())


class Recovery(unittest.TestCase):
    def test_a_run_that_did_not_end_is_noticed(self):
        with mock.patch.object(recovery, 'RUN', tmp() / 'run.json'):
            self.assertIsNone(recovery.begin())
            last = recovery.begin()                                            # no end() in between: a crash
            self.assertIn('started', last)
            self.assertIn('2 interrupted calls are being transcribed', recovery.message(last, 2))
            recovery.end()
            self.assertIsNone(recovery.begin())

    def test_watchdog(self):
        class P:
            codes = []

            def __init__(self, *a, **k):
                pass

            def wait(self):
                return P.codes.pop(0)
        with mock.patch.object(watchdog.subprocess, 'Popen', P), mock.patch.object(watchdog.time, 'sleep'), \
                mock.patch.object(watchdog, 'note'), mock.patch.object(watchdog.kernel32, 'CreateMutexW'), \
                mock.patch.object(watchdog.ctypes, 'get_last_error', return_value=0):
            P.codes = [3, 1, 0]                     # restart asked, a crash, then you quit
            self.assertEqual(watchdog.main([]), 0)
            P.codes = [1, 1, 1, 1]                  # four crashes: stop, and say so
            with mock.patch.object(watchdog.ctypes.windll.user32, 'MessageBoxW') as box:
                self.assertEqual(watchdog.main([]), 1)
                box.assert_called_once()


class Forget(unittest.TestCase):
    def setUp(self):
        self.store = Store(tmp() / 'mwb.db')
        self.addCleanup(self.store.close)
        s = self.store
        self.mid = s.new_meeting(app_id='teams', app_name='Teams', title='Sprint review',
                                 started='2026-10-05T11:00:00', ended='2026-10-05T11:30:00', status='ready',
                                 source='recorded')
        s.add_segments(self.mid, [('You', 0, 3, 'the zebrafish migration is done')])
        s.replace_actions(self.mid, [('You', 'Send the notes', '', None)])
        self.busy = s.new_meeting(app_id='teams', app_name='Teams', started='2026-10-05T15:00:00',
                                  status='transcribing', source='recorded')
        s.add_dictation(datetime.datetime(2026, 10, 5, 12), 'Code.exe', 'x', 'x', 1, 1.0, 1, 'caps', 'paste')
        s.run("INSERT INTO activity (started, ended, app, project) VALUES ('2026-10-05T10:00:00', "
              "'2026-10-05T10:30:00', 'Code.exe', 'MWB')")
        s.run("INSERT INTO journal_notes (ts, text) VALUES ('2026-10-06T01:00:00', 'late note')")   # still the 5th

    def found(self, word):
        return self.store.rows('SELECT rowid FROM segments_fts WHERE segments_fts MATCH ?', (word,))

    def test_forget_a_meeting(self):
        self.assertTrue(self.found('zebrafish'))
        self.assertTrue(forget.meeting(self.store, self.mid))
        self.assertIsNone(self.store.meeting(self.mid))
        self.assertFalse(self.found('zebrafish'))                              # gone from search too
        self.assertEqual(self.store.actions(), [])
        self.assertFalse(forget.meeting(self.store, self.busy))                # still transcribing: kept

    def test_forget_a_day(self):
        j = tmp() / '2026-10-05.md'
        j.write_text('journal', encoding='utf-8')
        self.store.run("INSERT INTO journals (day, path) VALUES ('2026-10-05', ?)", (str(j),))
        with mock.patch.object(forget.winapi, 'recycle') as recycle:
            n = forget.day(self.store, datetime.date(2026, 10, 5))
            recycle.assert_called_once_with(str(j))
        self.assertEqual(n, {'meetings': 1, 'dictations': 1, 'activity': 1, 'journal_notes': 1, 'journal': 1})
        self.assertIsNotNone(self.store.meeting(self.busy))
        self.assertEqual(self.store.rows('SELECT COUNT(*) n FROM journals')[0]['n'], 0)


class Skins(unittest.TestCase):
    def test_every_skin_and_state(self):
        for skin in art.SKINS:
            for state in ('idle', 'listening', 'working', 'loading', 'done', 'paused'):
                img = art.capsule(state, 1.25, 0.5, 1.0, skin=skin)
                self.assertEqual(img.mode, 'RGBA')
                self.assertGreater(img.getchannel('A').getextrema()[1], 200, (skin, state))
            self.assertEqual(art.capsule('done', 1.0, label='Copied', skin=skin).size,
                             art.capsule('done', 1.0, label='Copied').size)
        self.assertEqual(art.capsule('idle', skin='nonsense').size, art.capsule('idle').size)


class SettingsChecks(unittest.TestCase):
    def test_changes_and_bad_values(self):
        import tkinter as tk
        from mwb.ui import settings
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest('no display')
        root.withdraw()
        self.addCleanup(root.destroy)
        with mock.patch.object(config, 'USER_FILE', tmp() / 'none.toml'):
            w = settings.SettingsWindow(root)
        self.assertEqual(w.changes(), {})
        w.vars[('indicator', 'skin')][2].set('pixel')
        w.vars[('journal', 'time')][2].set('7:05')
        self.assertEqual(w.changes(), {'indicator': {'skin': 'pixel'}, 'journal': {'time': '07:05'}})
        w.vars[('indicator', 'opacity')][2].set('3')
        with self.assertRaises(ValueError):
            w.changes()


if __name__ == '__main__':
    unittest.main()
