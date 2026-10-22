"""Phase 3 rules that need no model: write or answer, citations, the label rules, JSON parsing, the router's
fallback when nothing can answer, and the design's promise that no code path sends mail."""
import datetime, os, re, tempfile, unittest
from pathlib import Path
from unittest import mock

from mwb import config
from mwb.llm.router import Router, json_of, normalize
from mwb.skills import answer
from mwb.skills.assist import Assist, language_of
from mwb.skills.notes import Understanding, series_of
from mwb.store.db import Store

ROOT = Path(__file__).resolve().parents[1]


class FakeCards:
    card_open = False


def assist(**over):
    cfg = config.load()
    cfg['assist'].update(over)
    return Assist(cfg, None, FakeCards(), None, None)


class WriteOrAnswer(unittest.TestCase):
    def test_wake_word(self):
        a = assist()
        self.assertEqual(a.decide("MWB, what's my next meeting?", 'Code.exe', True),
                         ('answer', "What's my next meeting?"))
        self.assertEqual(a.decide('M.W.B. what did I commit today', 'notepad.exe', True)[0], 'answer')

    def test_text_box_writes_and_elsewhere_answers(self):
        a = assist()
        self.assertEqual(a.decide('Ship it today.', 'msedge.exe', True), ('write', 'Ship it today.'))
        self.assertEqual(a.decide('What is a mutex?', 'explorer.exe', False), ('answer', 'What is a mutex?'))
        self.assertEqual(a.decide('Ship it today.', 'msedge.exe', None)[0], 'write')     # unsure: write

    def test_terminals_always_write(self):
        self.assertEqual(assist().decide('git status', 'WindowsTerminal.exe', False)[0], 'write')

    def test_modes(self):
        self.assertEqual(assist(talk_mode='always-write').decide('MWB, hello', 'x.exe', False)[0], 'write')
        self.assertEqual(assist(talk_mode='always-answer').decide('hello', 'x.exe', True)[0], 'answer')

    def test_language_from_window_title(self):
        self.assertEqual(language_of('main.js - AI-App - Visual Studio Code'), 'JavaScript')
        self.assertEqual(language_of('app.py - MWB - Visual Studio Code'), 'Python')


class Citations(unittest.TestCase):
    def test_invented_tags_are_removed(self):
        text, removed = answer.check_citations('You have sprint review [M3 10:04] and a fake one [M9] [A2].',
                                               {'M3 10:04', 'A2'})
        self.assertEqual(removed, 1)
        self.assertIn('[M3 10:04]', text)
        self.assertNotIn('[M9]', text)


class Labels(unittest.TestCase):
    def setUp(self):
        self.store = Store(os.path.join(tempfile.mkdtemp(), 't.db'))
        self.u = Understanding.__new__(Understanding)
        self.u.store = self.store

    def meeting(self, title, app='teams', name='Teams'):
        return self.store.meeting(self.store.new_meeting(app_id=app, app_name=name, title=title,
                                                         started='2026-10-13T10:00:00', status='ready',
                                                         source='recorded'))

    def test_rules(self):
        work, _ = self.u.stage_a(self.meeting('Sprint 43 planning'), [1, 2])
        fun, _ = self.u.stage_a(self.meeting('Diwali celebration', 'whatsapp', 'WhatsApp'), [])
        unsure, _ = self.u.stage_a(self.meeting('Catch up'), [])
        self.assertGreaterEqual(work, 0.6)
        self.assertLessEqual(fun, -0.6)
        self.assertLess(abs(unsure), 0.6)                  # goes to the transcript check

    def test_series(self):
        self.assertEqual(series_of('Sprint 43 planning (Tue)'), series_of('Sprint 44 planning'))

    def test_correction_carries_over_and_counts(self):
        a, b = self.meeting('Friday catch up').get('id'), self.meeting('Friday catch up').get('id')
        for mid in (a, b):
            self.store.save_label(mid, 'work', None, 0.5, None, None, [], 'B', series_of('Friday catch up'))
        self.u.correct(a, 'timepass')
        self.assertEqual(self.store.label(b)['label'], 'timepass')
        self.assertEqual(self.u.agreement(), (0, 2))


class Router_(unittest.TestCase):
    def test_json_in_a_fence(self):
        self.assertEqual(json_of('Sure:\n```json\n{"label": "work", "x": "a}b"}\n```'), {'label': 'work', 'x': 'a}b'})
        self.assertIsNone(json_of('no json here'))

    def test_hyphens(self):
        self.assertEqual(normalize('PAY‑412'), 'PAY-412')

    def test_no_network_and_no_memory_gives_a_reason(self):
        cfg = config.load()
        r = Router(cfg)
        with mock.patch.object(r, '_api') as api, \
                mock.patch('mwb.memory_guard.verdict', return_value=('short', 0.4)):
            api.return_value.chat.return_value = mock.Mock(ok=False, text='', error='OSError: no network', status=0)
            reply = r.chat('answer', [{'role': 'user', 'content': 'hi'}])
        self.assertFalse(reply.ok)
        self.assertIn('no network', reply.error)
        self.assertIn('0.4 GB is free', reply.error)


class NoMailIsSent(unittest.TestCase):
    def test_no_send_anywhere(self):
        """Design P3 exit: no code path that sends mail. MWB opens drafts; you press Send."""
        hits = []
        for path in (ROOT / 'mwb').rglob('*.py'):
            for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                code = line.split('#')[0]
                if re.search(r'\.Send\s*\(|SendMail|smtplib|sendmail|\.SendUsingAccount', code):
                    hits.append(f'{path.relative_to(ROOT)}:{n}')
        self.assertEqual(hits, [])


if __name__ == '__main__':
    unittest.main()
