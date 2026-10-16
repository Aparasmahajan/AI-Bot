"""Double-tap detection (mwb/hotkeys.py) against scripted key states, so no real keys are pressed."""
import unittest
from unittest import mock

from mwb import hotkeys, winapi


class FakeKeys:
    """Replays a timeline of (seconds, key down?) for one key; every other key stays up."""

    def __init__(self, vk, timeline, others_down_at=()):
        self.vk, self.timeline, self.others = vk, timeline, others_down_at
        self.now = 0.0

    def state(self, vk):
        if vk != self.vk:
            return -32768 if any(a <= self.now < b for a, b in self.others) else 0
        down = False
        for t, d in self.timeline:
            if t <= self.now:
                down = d
        return -32768 if down else 0


def taps(*starts, hold=0.08):
    out = []
    for s in starts:
        out += [(s, True), (s + hold, False)]
    return out


def count(timeline, vk=winapi.VK_MENU, others=(), until=3.0):
    keys = FakeKeys(vk, timeline, others)
    w = hotkeys.TapWatcher('test', vk)
    hits = 0
    with mock.patch.object(winapi.user32, 'GetAsyncKeyState', side_effect=keys.state):
        t = 0.0
        while t < until:
            keys.now = t
            hits += w.step(t)
            t += 0.015
    return hits


class DoubleTaps(unittest.TestCase):
    def test_double_tap(self):
        self.assertEqual(count(taps(0.5, 0.68)), 1)

    def test_slow_taps_are_not_a_double(self):
        self.assertEqual(count(taps(0.5, 1.2)), 0)

    def test_long_press_is_not_a_tap(self):
        self.assertEqual(count([(0.5, True), (0.9, False), (1.0, True), (1.08, False)]), 0)

    def test_three_taps_make_one_double(self):
        self.assertEqual(count(taps(0.5, 0.68, 0.86)), 1)

    def test_alt_tab_is_not_a_double(self):
        self.assertEqual(count(taps(0.5, 0.68), others=[(0.52, 0.56)]), 0)     # Tab during the first tap

    def test_parse(self):
        mods, vk, held = hotkeys.parse('ctrl+shift+alt+space')
        self.assertEqual((mods, vk), (winapi.MOD_CONTROL | winapi.MOD_SHIFT | winapi.MOD_ALT, 0x20))
        self.assertEqual(held, [winapi.VK_CONTROL, winapi.VK_SHIFT, winapi.VK_MENU, 0x20])
        self.assertEqual(hotkeys.parse('ctrl+alt+p')[1], ord('P'))


if __name__ == '__main__':
    unittest.main()
