"""Memory guard v0 (design §11.2): check free memory before loading a model, and end idle workers when it runs low.

A model may load when the free memory covers its size plus a 1 GB margin. Dictation is interactive, so between the
model size and that line it still loads, with a warning; below the model size it would push the laptop into paging,
so it refuses and says how much is free."""
import time

from mwb import winapi

LOW_GB, LOW_FOR_S = 1.0, 30         # free memory under 1 GB for 30 s: idle workers exit at once


def verdict(model_gb, margin_gb, free=None):
    """('ok' | 'tight' | 'short', free GB)."""
    free = winapi.free_gb() if free is None else free
    if free >= model_gb + margin_gb:
        return 'ok', free
    return ('tight' if free >= model_gb else 'short'), free


class LowMemoryWatch:
    """Call tick() now and then; it returns True once free memory has stayed under LOW_GB for LOW_FOR_S seconds."""

    def __init__(self):
        self.since = None

    def tick(self, free=None):
        free = winapi.free_gb() if free is None else free
        if free >= LOW_GB:
            self.since = None
            return False
        self.since = self.since or time.monotonic()
        return time.monotonic() - self.since >= LOW_FOR_S
