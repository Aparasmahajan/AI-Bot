"""Power and CPU state for the scheduler (design §8.5): meeting transcription runs live only on mains power, and
backs off when the CPU stays above 80 % for 30 s."""
import ctypes, ctypes.wintypes as wt, time

from mwb.winapi import kernel32


class _SPS(ctypes.Structure):
    _fields_ = [('ACLineStatus', ctypes.c_ubyte), ('BatteryFlag', ctypes.c_ubyte),
                ('BatteryLifePercent', ctypes.c_ubyte), ('SystemStatusFlag', ctypes.c_ubyte),
                ('BatteryLifeTime', wt.DWORD), ('BatteryFullLifeTime', wt.DWORD)]


def on_mains():
    s = _SPS()
    kernel32.GetSystemPowerStatus(ctypes.byref(s))
    return s.ACLineStatus == 1 or s.BatteryFlag == 128         # 128: no battery at all


def _times():
    idle, k, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
    kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(k), ctypes.byref(u))
    v = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime
    return v(idle), v(k) + v(u)                     # kernel time includes idle time


class CpuWatch:
    """sample() now and then; busy() is True once the CPU has stayed above `limit` % for `for_s` seconds."""

    def __init__(self, limit=80, for_s=30):
        self.limit, self.for_s = limit, for_s
        self.prev = _times()
        self.load = 0.0
        self.high_since = None

    def sample(self):
        idle, total = _times()
        di, dt = idle - self.prev[0], total - self.prev[1]
        self.prev = (idle, total)
        if dt > 0:
            self.load = 100.0 * (1 - di / dt)
        now = time.monotonic()
        if self.load > self.limit:
            self.high_since = self.high_since or now
        else:
            self.high_since = None
        return self.load

    def busy(self):
        return self.high_since is not None and time.monotonic() - self.high_since >= self.for_s
