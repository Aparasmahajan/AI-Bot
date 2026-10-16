"""Putting text where the cursor is (design §9.1): save the clipboard, put the text on it, send Ctrl+V, then put the
clipboard back. Text MWB places on the clipboard is marked to stay out of Windows' clipboard history (Win+V).

When the clipboard holds something that isn't text (an image, copied files), or the app is on the type-instead list,
the text is typed as Unicode key events instead, so nothing you copied is lost."""
import logging, time

from mwb import winapi

log = logging.getLogger('mwb.insert')


def insert(text, restore_ms=400, type_instead=(), app=''):
    """Returns 'paste', 'type' or 'none'. Call off the main thread: it waits for keys and for the app."""
    if not text:
        return 'none'
    if not winapi.wait_keys_up(timeout=3.0):
        log.warning('keys still held after 3 s; inserting anyway')
    if app.lower() in {a.lower() for a in type_instead}:
        winapi.type_text(text)
        return 'type'
    saved = winapi.clipboard_get()
    if saved is None or not winapi.clipboard_set(text, private=True):
        winapi.type_text(text)
        return 'type'
    ours = winapi.user32.GetClipboardSequenceNumber()
    winapi.send_keys((winapi.VK_CONTROL, False), (winapi.VK_V, False), (winapi.VK_V, True), (winapi.VK_CONTROL, True))
    time.sleep(restore_ms / 1000)                   # the app reads the clipboard after the keys arrive
    if winapi.user32.GetClipboardSequenceNumber() == ours:     # unless something else changed it meanwhile
        winapi.clipboard_set(saved)
    return 'paste'
