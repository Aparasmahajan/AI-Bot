"""Phase 4, the journal: the sentence checker, time per project, the 06:00 day, the activity sampler, scheduling,
the Markdown page, and a whole journal written from a scratch database with a fake model and fake git."""
import datetime, json, tempfile, unittest
from pathlib import Path
from unittest import mock

from mwb import config
from mwb.llm.router import Reply
from mwb.sensors import activity
from mwb.sensors.activity import ActivityWatch, project_of
from mwb.skills import journal
from mwb.skills.journal import Journal, check_sentence, day_of, time_by_project
from mwb.store.db import Store
from mwb.ui.today import markdown

D = datetime.datetime
DAY = datetime.date(2026, 10, 5)
COMMITS = [{'sha': 'ce945ae0123456789abcdef0123456789abcdef0', 'short': 'ce945ae', 'time': D(2026, 10, 5, 23, 47),
            'repo': 'AI-App', 'branch': 'main', 'message': 'more ui', 'files': 3, 'added': 138, 'removed': 14},
           {'sha': 'a445845aaaa456789abcdef0123456789abcdef0', 'short': 'a445845', 'time': D(2026, 10, 5, 22, 45),
            'repo': 'AI-App', 'branch': 'main', 'message': 'added glass mode', 'files': 1, 'added': 44, 'removed': 2}]


class FakeUI:
    def __init__(self):
        self.notes, self.states = [], []

    def notify(self, m):
        self.notes.append(m)

    def set_state(self, s):
        self.states.append(s)


class FakeRouter:
    def __init__(self, data=None, ok=True):
        self.data, self.ok, self.prompts = data, ok, []

    def chat(self, skill, messages, *a, **k):
        self.prompts.append(messages[-1]['content'])
        if not self.ok:
            return Reply(False, route='api', error='no network')
        return Reply(True, json.dumps(self.data), 'api', 'gpt-oss-120b', '', 1.0)


def scratch():
    folder = tempfile.mkdtemp(prefix='mwb-test-')
    cfg = config.load()
    cfg['journal'].update(folder=folder, email='off')
    cfg['meetings']['outlook'] = 'off'
    return cfg, Store(Path(folder) / 'mwb.db'), Path(folder)


class Checker(unittest.TestCase):
    known = {'c:ce945ae': '23:47 AI-App (branch main): "more ui" +138 -14, 3 files',
             'm:2': '11:00 "Sprint 42 planning", 50 m. Work (planning)', 'a:MTMS': 'MTMS 3 h 40 m'}
    shas = {c['sha'] for c in COMMITS}
    facts = 'Commits (2, +182 -16) 23:47 more ui Meetings 11:00 50 m MTMS 3 h 40 m'

    def test_good_sentence_keeps_its_tags(self):
        s = check_sentence('You shipped the glass layout in AI-App. [c:ce945ae]', self.known, self.shas, self.facts)
        self.assertEqual(s, 'You shipped the glass layout in AI-App. [c:ce945ae]')

    def test_no_valid_tag_is_dropped(self):
        self.assertIsNone(check_sentence('A great day overall.', self.known, self.shas, self.facts))
        self.assertIsNone(check_sentence('You met the client. [m:9]', self.known, self.shas, self.facts))

    def test_unknown_tag_removed_known_kept(self):
        s = check_sentence('Planning took most of the day. [m:2, m:7]', self.known, self.shas, self.facts)
        self.assertEqual(s, 'Planning took most of the day. [m:2]')

    def test_invented_commit_id_drops_it(self):
        self.assertIsNone(check_sentence('You pushed 1a2b3c4 to main. [c:ce945ae]', self.known, self.shas,
                                         self.facts))
        self.assertIsNotNone(check_sentence('Commit ce945ae added more UI. [c:ce945ae]', self.known, self.shas,
                                            self.facts))

    def test_number_not_in_facts_drops_it(self):
        self.assertIsNone(check_sentence('You spent 5 hours on MTMS. [a:MTMS]', self.known, self.shas, self.facts))
        self.assertIsNotNone(check_sentence('MTMS took 3 h 40 m. [a:MTMS]', self.known, self.shas, self.facts))
        self.assertIsNone(check_sentence('You spent seven hours on MTMS. [a:MTMS]', self.known, self.shas,
                                         self.facts))
        self.assertIsNotNone(check_sentence('MTMS took three hours and more. [a:MTMS]', self.known, self.shas,
                                            self.facts))

    def test_tag_must_support_the_sentence(self):
        self.assertIsNone(check_sentence('You have 12 uncommitted changes. [d:day]',
                                         {'d:day': 'Dictation: 3 times, 40 words.'}, set(), '12 3 40'))
        s = check_sentence('Planning ran long and AI-App got more UI. [m:2] [a:MTMS]', self.known, self.shas,
                           self.facts)
        self.assertEqual(s, 'Planning ran long and AI-App got more UI. [m:2]')

    def test_gpt_oss_brackets(self):
        s = check_sentence('Planning ran long.【m:2†L1】', self.known, self.shas, self.facts)
        self.assertEqual(s, 'Planning ran long. [m:2]')


class Day(unittest.TestCase):
    def test_late_night_belongs_to_the_day_before(self):
        self.assertEqual(day_of(D(2026, 10, 6, 0, 30)), DAY)
        self.assertEqual(day_of(D(2026, 10, 6, 6, 1)), datetime.date(2026, 10, 6))

    def test_time_adds_up_to_the_working_day(self):
        acts = [{'started': '2026-10-05T09:00:00', 'ended': '2026-10-05T12:00:00', 'project': 'MTMS', 'idle': 0},
                {'started': '2026-10-05T12:00:00', 'ended': '2026-10-05T13:00:00', 'project': '', 'idle': 1},
                {'started': '2026-10-05T13:00:00', 'ended': '2026-10-05T13:03:00', 'project': 'Tiny', 'idle': 0},
                {'started': '2026-10-05T13:03:00', 'ended': '2026-10-05T15:00:00', 'project': 'AI-App', 'idle': 0}]
        meetings = [{'start': D(2026, 10, 5, 11), 'end': D(2026, 10, 5, 11, 30)}]
        totals, first, last, away = time_by_project(acts, meetings, *journal.bounds(DAY))
        self.assertEqual(totals['MTMS'], 2.5 * 3600)                  # the meeting's half hour is not MTMS
        self.assertEqual(totals['Meetings'], 1800)
        self.assertEqual(totals['Other'], 180)                        # under 5 minutes goes to Other
        self.assertEqual((first, last), (D(2026, 10, 5, 9), D(2026, 10, 5, 15)))
        self.assertEqual(sum(totals.values()) + away, 6 * 3600)


class Activity(unittest.TestCase):
    def test_projects(self):
        repos = ['BroPlus', 'MWB']
        self.assertEqual(project_of('Code.exe', 'app.py - MWB - Visual Studio Code', repos), ('Code.exe', 'MWB'))
        self.assertEqual(project_of('Code.exe', 'x.ts - Orders - Visual Studio Code', repos)[1], 'Orders')
        self.assertEqual(project_of('msedge.exe', 'Mail - Outlook', repos)[1], 'Email')
        self.assertEqual(project_of('chrome.exe', 'HDFC Bank', repos, ['*bank*']), ('', 'Private'))

    def test_samples_merge_and_away_is_backdated(self):
        cfg, store, _ = scratch()
        w = ActivityWatch(store, cfg)
        self.addCleanup(store.close)
        t = D(2026, 10, 5, 10)
        with mock.patch.object(activity.winapi, 'foreground_app', return_value=(1, 'Code.exe')), \
                mock.patch.object(activity, '_title', return_value='a.py - MWB - Visual Studio Code'), \
                mock.patch.object(activity, 'idle_seconds', return_value=1):
            for i in range(60):
                w.sample(t + datetime.timedelta(seconds=10 * i))
        with mock.patch.object(activity.winapi, 'foreground_app', return_value=(1, 'Code.exe')), \
                mock.patch.object(activity, 'idle_seconds', return_value=310):
            w.sample(t + datetime.timedelta(seconds=600))
        w.flush()
        rows = store.rows('SELECT * FROM activity ORDER BY id')
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]['project'], rows[1]['idle']), ('MWB', 1))
        self.assertEqual(rows[1]['started'], '2026-10-05T10:04:50')     # away since the last input, 310 s back
        self.assertEqual(rows[0]['ended'], '2026-10-05T10:04:50')


class WholeJournal(unittest.TestCase):
    def setUp(self):
        self.cfg, self.store, self.folder = scratch()
        s = self.store
        mid = s.new_meeting(app_id='teams', app_name='Teams', title='Sprint 42 planning', started='2026-10-05T11:00:00',
                            ended='2026-10-05T11:50:00', status='ready', source='recorded')
        s.save_notes(mid, 'ready', ['Planned sprint 42.'], ['Caching moves to the next sprint.'], [], 'api', 'm')
        s.replace_actions(mid, [('You', 'Share the demo build', 'by Wednesday', '2026-10-07')])
        s.save_label(mid, 'work', 'planning', 0.9, 50, 0, [], 'A', 'sprint planning')
        s.run("INSERT INTO activity (started, ended, app, project, idle) VALUES "
              "('2026-10-05T09:00:00', '2026-10-05T12:40:00', 'Code.exe', 'MTMS', 0)")
        s.run("INSERT INTO journal_notes (ts, text) VALUES ('2026-10-05T14:05:00', 'Staging Kafka access is still "
              "blocked.')")
        self.mid = mid
        self.addCleanup(s.close)

    def journal(self, data, ok=True):
        j = Journal(self.cfg, self.store, FakeRouter(data, ok), FakeUI())
        j.calendar = lambda a, b: [{'subject': 'Design review', 'start': D(2026, 10, 6, 10), 'end': D(2026, 10, 6, 11)}]
        return j

    def write(self, j, **k):
        with mock.patch.object(journal.git, 'author', return_value='me@example.com'), \
                mock.patch.object(journal.git, 'day', return_value=(COMMITS, {'AI-App': 3})), \
                mock.patch.object(journal.Journal, '_calm', return_value=False), \
                mock.patch('mwb.skills.journal.datetime') as dt:
            dt.datetime.now.return_value = D(2026, 10, 6, 1, 0)
            dt.datetime.combine, dt.datetime.fromisoformat = datetime.datetime.combine, datetime.datetime.fromisoformat
            dt.date, dt.time, dt.timedelta = datetime.date, datetime.time, datetime.timedelta
            return j.write(DAY, **k)

    def test_facts_prose_and_checker(self):
        m = f'm:{self.mid}'
        j = self.journal({'summary': [f'Most of the day went to MTMS and sprint planning. [a:MTMS] [{m}]',
                                      'You shipped commit 9999abc. [c:ce945ae]', 'It was a productive day.'],
                          'projects': [{'project': 'AI-App', 'sentences': ['You added the glass mode. [c:a445845]']},
                                       {'project': 'Invented', 'sentences': ['Nothing. [a:MTMS]']}],
                          'blockers': ['Staging Kafka access is still blocked. [n:1]'],
                          'tomorrow': ['Share the demo build before the design review. [i:1] [t:1]']})
        path = self.write(j, manual=True)
        md = path.read_text(encoding='utf-8')
        self.assertIn('Most of the day went to MTMS and sprint planning.', md)
        self.assertNotIn('9999abc', md)
        self.assertNotIn('productive', md)
        self.assertNotIn('Invented', md)
        self.assertIn('| `ce945ae` | 23:47 | AI-App | main | more ui | +138 −14 |', md)     # the 23:47 commit
        self.assertIn('## Code · 2 commits · +182 −16', md)
        self.assertIn('Not committed yet: AI-App (3 files).', md)
        self.assertIn('**Sprint 42 planning** · 50 m · Work', md)
        self.assertIn('| MTMS | 2 h 50 m |', md)                    # 3 h 40 m less the meeting's 50 minutes
        self.assertIn('- 10:00 Design review', md)
        self.assertIn('3 sentences that did not were removed', md)
        self.assertIn('Kafka', j.router.prompts[0])                  # the voice note reached the facts
        row = self.store.rows('SELECT * FROM journals')[0]
        self.assertEqual((row['day'], row['route'], row['dropped']), ('2026-10-05', 'api', 3))
        html = markdown(md)
        self.assertIn('<span class="tag">c:a445845</span>', html)
        self.assertIn('<td><code>ce945ae</code></td>', html)

    def test_no_model_still_writes_the_facts_when_you_ask(self):
        path = self.write(self.journal(None, ok=False), manual=True)
        md = path.read_text(encoding='utf-8')
        self.assertIn('facts only', md)
        self.assertIn('ce945ae', md)

    def test_scheduled_run_waits_then_gives_up(self):
        j = self.journal(None, ok=False)
        self.assertIsNone(self.write(j))
        self.assertEqual(len(j.ui.notes), 1)                     # it says why, once
        j.tries[DAY] = (journal.TRIES - 1, 0.0)
        self.assertIsNotNone(self.write(j))                       # the last try writes the facts alone

    def test_your_edits_are_kept(self):
        j = self.journal({'summary': []})
        first = self.write(j, manual=True)
        first.write_text('my own words', encoding='utf-8')
        second = self.write(j, manual=True)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_text(encoding='utf-8'), 'my own words')

    def test_schedule(self):
        j = self.journal({'summary': []})
        with mock.patch.object(journal.threading, 'Thread') as thread:
            self.assertIsNone(j.maybe_run(D(2026, 10, 5, 18, 0)))           # before 18:30
            self.assertEqual(j.maybe_run(D(2026, 10, 5, 18, 31)), DAY)
            self.assertEqual(j.maybe_run(D(2026, 10, 6, 9, 0)), DAY)        # missed yesterday: catch up
            self.store.run("INSERT INTO journals (day) VALUES ('2026-10-05')")
            self.assertIsNone(j.maybe_run(D(2026, 10, 6, 9, 0)))            # done, and today isn't due yet
            self.assertEqual(thread.call_count, 2)

    def test_voice_note(self):
        j = self.journal({})
        self.assertIsNone(j.add_note('  '))
        self.assertTrue(j.add_note('Ask Rahul about the release'))


if __name__ == '__main__':
    unittest.main()
