"""Phase 2 pieces that need no call: the detector's rules on scripted registry data, transcript merging and echo
removal, transcript import, the long-piece segmenter and the recorder's silence filling."""
import io, math, tempfile, time, unittest, zipfile
from array import array
from pathlib import Path

from mwb.audio.vad import Segmenter
from mwb.sensors.meeting_detector import Apps, Detector, Holder
from mwb.skills import transcripts

T0 = 1_800_000_000.0


class FakeRegistry:
    def __init__(self):
        self.mic, self.cam = [], []

    def __call__(self, device):
        return self.mic if device == 'microphone' else self.cam


def detector(titles=lambda exes: [], choices=None):
    reg = FakeRegistry()
    return reg, Detector(Apps(choices=choices or {}), own={'c:#mwb#pythonw.exe'}, read=reg, titles=titles)


class Detection(unittest.TestCase):
    def test_teams_call_starts_after_20_s_and_ends_60_s_after_release(self):
        reg, d = detector()
        reg.mic = [Holder('MSTeams_8wekyb3d8bbwe', 'MSTeams_8wekyb3d8bbwe', True, T0)]
        self.assertEqual(d.poll(T0 + 10), [])
        (kind, call), = d.poll(T0 + 21)
        self.assertEqual((kind, call.app_id, call.policy, call.personal), ('start', 'teams', 'record', False))
        reg.mic = []
        self.assertEqual(d.poll(T0 + 100), [])
        self.assertEqual(d.poll(T0 + 140), [])
        self.assertEqual(d.poll(T0 + 161)[0][0], 'end')

    def test_short_release_does_not_end_the_call(self):
        reg, d = detector()
        reg.mic = [Holder('C:#Program Files#Zoom#bin#Zoom.exe', 'Zoom.exe', False, T0)]
        d.poll(T0 + 30)
        reg.mic = []
        d.poll(T0 + 40)
        reg.mic = [Holder('C:#Program Files#Zoom#bin#Zoom.exe', 'Zoom.exe', False, T0 + 45)]
        self.assertEqual(d.poll(T0 + 50), [])
        reg.mic = []
        self.assertEqual(d.poll(T0 + 100), [])                 # released at 100: the clock starts again

    def test_meeting_tab_in_a_browser(self):
        reg, d = detector(titles=lambda exes: ['Inbox - Brave', 'Sprint review | Microsoft Teams - Brave'])
        reg.mic = [Holder('C:#Program Files#BraveSoftware#Brave-Browser#Application#brave.exe', 'brave.exe', False, T0)]
        (_, call), = d.poll(T0 + 25)
        self.assertEqual((call.app_id, call.title), ('teams', 'Sprint review'))

    def test_browser_without_meeting_tab_asks(self):
        reg, d = detector(titles=lambda exes: ['Inbox - Brave'])
        reg.mic = [Holder('C:#x#brave.exe', 'brave.exe', False, T0)]
        (_, call), = d.poll(T0 + 25)
        self.assertEqual((call.app_id, call.policy), ('browser:brave.exe', 'ask'))

    def test_personal_apps_and_your_choices(self):
        reg, d = detector(choices={'slack': 'never'})
        reg.mic = [Holder('5319275A.WhatsAppDesktop_cv1g1gvanyjgm', '5319275A.WhatsAppDesktop_cv1g1gvanyjgm', True, T0),
                   Holder('C:#x#slack.exe', 'slack.exe', False, T0)]
        calls = {c.app_id: c for _, c in d.poll(T0 + 25)}
        self.assertTrue(calls['whatsapp'].personal)
        self.assertEqual(calls['slack'].policy, 'never')

    def test_mwb_itself_and_dictation_apps_are_not_calls(self):
        reg, d = detector()
        reg.mic = [Holder('C:#MWB#pythonw.exe', 'pythonw.exe', False, T0),
                   Holder('C:#Users#x#Wispr Flow.exe', 'Wispr Flow.exe', False, T0)]
        self.assertEqual(d.poll(T0 + 60), [])

    def test_unknown_app(self):
        reg, d = detector()
        reg.mic = [Holder('C:#x#obs64.exe', 'obs64.exe', False, T0)]
        (_, call), = d.poll(T0 + 25)
        self.assertEqual((call.app_id, call.policy), ('app:obs64.exe', 'ask'))


class Merging(unittest.TestCase):
    def test_lanes_interleave_and_echo_goes(self):
        rows = [('Them', 0.0, 3.0, 'Can you share the release notes?'),
                ('You', 0.4, 3.1, 'Can you share the release notes'),          # the speakers, heard by the mic
                ('You', 3.5, 5.0, 'Sure, by Thursday.'),
                ('Them', 5.5, 6.0, '[BLANK_AUDIO]'),
                ('Them', 6.0, 8.0, 'Thanks.'), ('Them', 8.0, 9.0, 'Thanks.')]
        self.assertEqual([(r[0], r[3]) for r in transcripts.merge(rows)],
                         [('Them', 'Can you share the release notes?'), ('You', 'Sure, by Thursday.'),
                          ('Them', 'Thanks.')])


class Import(unittest.TestCase):
    def test_teams_vtt(self):
        vtt = ('WEBVTT\n\nab12/1-0\n00:00:01.000 --> 00:00:03.500\n<v Asha Rao>Morning all.</v>\n\n'
               'ab12/1-1\n00:00:03.600 --> 00:00:05.000\n<v Asha Rao>Shall we start?</v>\n\n'
               '00:00:06.000 --> 00:00:08.000\n<v Dev>Yes.</v>\n')
        self.assertEqual(transcripts.parse_vtt(vtt), [('Asha Rao', 1.0, 5.0, 'Morning all. Shall we start?'),
                                                      ('Dev', 6.0, 8.0, 'Yes.')])

    def test_zoom_vtt(self):
        vtt = 'WEBVTT\n\n1\n00:00:02.100 --> 00:00:04.000\nDev Kumar: The build is green.\n'
        self.assertEqual(transcripts.parse_vtt(vtt), [('Dev Kumar', 2.1, 4.0, 'The build is green.')])

    def test_teams_docx(self):
        paras = ['Sprint review', 'Asha Rao   0:03', 'Morning all.', 'Dev   1:02:05', 'Yes.']
        body = ''.join(f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paras)
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               f'{body}</w:body></w:document>')
        path = Path(tempfile.mkdtemp()) / 't.docx'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', xml)
        rows = transcripts.parse_file(path)
        self.assertEqual(rows[1:], [('Asha Rao', 3.0, None, 'Morning all.'), ('Dev', 3725.0, None, 'Yes.')])


def tone(rate, s, amp=6000):
    return array('h', (int(amp * math.sin(2 * math.pi * 220 * i / rate)) for i in range(int(rate * s))))


class LongPieces(unittest.TestCase):
    def test_meeting_pieces_wait_for_15_s(self):
        rate = 16000
        seg = Segmenter(rate, pause_ms=800, max_s=28, min_s=15, long_pause_s=4)
        out = []
        for _ in range(4):                                  # four 4 s sentences with 1 s pauses
            out += seg.feed(tone(rate, 4)) + seg.feed(array('h', bytes(2 * rate)))
        self.assertEqual(len(out), 1)                       # one piece of about 16 s, not four short ones
        self.assertGreater(out[0].seconds, 15)
        out = seg.feed(tone(rate, 3)) + seg.feed(array('h', bytes(2 * rate * 5)))
        self.assertEqual(len(out), 1)                       # a lone sentence goes after a 4 s silence


class SilenceFill(unittest.TestCase):
    def test_loopback_gaps_become_silence(self):
        from mwb.audio.recorder import Lane
        cfg = {'meetings': {'piece_min_s': 15, 'piece_max_s': 28}}
        lane = Lane('them', cfg, lambda *a: None)
        lane.begin(16000, time.perf_counter())
        lane.audio(array('h', bytes(2 * 512)))
        time.sleep(0.6)                                     # nothing playing: no packets
        lane.fill_to_now()
        self.assertAlmostEqual(lane.fed_s, 0.6, delta=0.15)


if __name__ == '__main__':
    unittest.main()
