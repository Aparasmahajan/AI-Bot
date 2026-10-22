"""Is the cursor in a text box? (design §9.7: a double tap writes when it is and answers when it isn't.) Asked once,
when you start talking, through Windows UI Automation with comtypes. It reads only the kind of control that has the
focus, never its text. A slow or odd app gives "don't know", and then MWB writes, the safe choice."""
import logging, threading

log = logging.getLogger('mwb.focus')
EDIT, DOCUMENT, COMBO = 50004, 50030, 50003
VALUE_PATTERN = 10002
_uia = None


def _client():
    global _uia
    if _uia is None:
        import comtypes.client
        mod = comtypes.client.GetModule('UIAutomationCore.dll')
        _uia = comtypes.client.CreateObject('{ff48dba4-60ef-4201-aa87-54103eef594e}', interface=mod.IUIAutomation)
    return _uia


def _ask(out):
    import comtypes
    comtypes.CoInitialize()
    try:
        el = _client().GetFocusedElement()
        kind = el.CurrentControlType
        if kind in (EDIT, DOCUMENT):
            out['answer'] = True
        elif kind == COMBO:
            out['answer'] = True                     # an editable box with a list, like a browser's address bar
        else:
            out['answer'] = False
        out['kind'] = kind
    except Exception as e:
        out['error'] = type(e).__name__
    finally:
        comtypes.CoUninitialize()


def in_text_box(timeout=0.4):
    """True, False, or None when it can't tell in time."""
    out = {}
    t = threading.Thread(target=_ask, args=(out,), daemon=True, name='focus')
    t.start()
    t.join(timeout)
    if 'answer' not in out:
        log.info('focus unknown (%s)', out.get('error', 'slow'))
        return None
    return out['answer']
