"""Cutting speech into pieces (mwb/audio/vad.py) on synthetic audio: tone bursts stand in for speech."""
import math, unittest
from array import array

from mwb.audio.vad import Segmenter

RATE = 48000


def tone(seconds, amp=6000, hz=220):
    return array('h', (int(amp * math.sin(2 * math.pi * hz * i / RATE)) for i in range(int(RATE * seconds))))


def hush(seconds, amp=30):
    return array('h', ((amp if i % 2 else -amp) for i in range(int(RATE * seconds))))


def run(*parts, pause_ms=500, max_s=10.0):
    seg = Segmenter(RATE, pause_ms, max_s)
    pieces = []
    for p in parts:
        for i in range(0, len(p), 1536):                # 32 ms packets, like the mic
            pieces += seg.feed(p[i:i + 1536])
    return seg, pieces, seg.flush()


class Pieces(unittest.TestCase):
    def test_pause_closes_a_piece_while_talking(self):
        seg, during, end = run(hush(1), tone(2), hush(0.7), tone(1.5), hush(0.1))
        self.assertEqual(len(during), 1)                 # the first phrase went off during the pause
        self.assertEqual(len(end), 1)                    # only the last one is left at the finish
        self.assertAlmostEqual(during[0].speech_s, 2.0, delta=0.15)
        self.assertLess(during[0].seconds, 2.0 + 0.45 + 0.26 + 0.07)    # pre-roll and a short tail (whole 64 ms frames), not the pause

    def test_short_pause_does_not_cut(self):
        _, during, end = run(hush(1), tone(1), hush(0.3), tone(1), hush(0.1))
        self.assertEqual((len(during), len(end)), (0, 1))

    def test_long_speech_is_cut_at_the_quietest_point(self):
        quiet_gap = tone(0.2, amp=500)                   # a dip, not a pause
        _, during, end = run(hush(0.5), tone(7), quiet_gap, tone(6), hush(0.1))
        self.assertGreaterEqual(len(during), 1)
        self.assertLessEqual(max(p.seconds for p in during + end), 10.0 + 0.1)
        self.assertAlmostEqual(during[0].seconds, 7.6, delta=0.5)

    def test_blips_are_ignored(self):
        _, during, end = run(hush(1), tone(0.1), hush(1))
        self.assertEqual(during + end, [])

    def test_silence_only(self):
        seg, during, end = run(hush(3))
        self.assertEqual(during + end, [])
        self.assertIsNone(seg.last_speech_at)

    def test_quiet_speech_is_levelled(self):
        _, during, end = run(hush(1), tone(2, amp=800), hush(0.6))
        self.assertGreater(during[0].gain, 2)

    def test_pause_timer_for_hands_free_finish(self):
        seg, _, _ = run(hush(0.5), tone(1), hush(2.1))
        self.assertGreaterEqual(seg.t - seg.last_speech_at, 2.0)


if __name__ == '__main__':
    unittest.main()
