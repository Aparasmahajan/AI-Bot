"""The selected text in any app (design §9.2, §9.4, §9.5): wait until the shortcut's keys are up, press Ctrl+C,
read the clipboard, and put your own clipboard back. Nothing is selected: ''."""
import time

from mwb import winapi


def copy_selection(timeout=0.8):
    if not winapi.wait_keys_up(timeout=5.0):
        return ''
    saved = winapi.clipboard_get()
    before = winapi.user32.GetClipboardSequenceNumber()
    winapi.send_keys((winapi.VK_CONTROL, False), (0x43, False), (0x43, True), (winapi.VK_CONTROL, True))
    end = time.monotonic() + timeout
    while winapi.user32.GetClipboardSequenceNumber() == before and time.monotonic() < end:
        time.sleep(0.02)
    if winapi.user32.GetClipboardSequenceNumber() == before:
        return ''                                   # nothing was selected, so nothing was copied
    text = winapi.clipboard_get() or ''
    if saved is not None:
        winapi.clipboard_set(saved)
    return text
