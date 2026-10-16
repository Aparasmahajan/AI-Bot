"""The classic Outlook calendar through COM with comtypes (design §9.3, proven by P0-3 with no security pop-up).
At the start of a call MWB looks for a calendar item running within 10 minutes either side and takes its subject
and meeting platform. Decision 4: MWB may start Outlook when it isn't running. Nothing else is read."""
import ctypes, ctypes.wintypes as wt, datetime, logging, re

log = logging.getLogger('mwb.outlook')
LINK = re.compile(r'(teams\.microsoft\.com|zoom\.us|meet\.google\.com|webex\.com)', re.I)
PLATFORM = {'teams.microsoft.com': 'teams', 'zoom.us': 'zoom', 'meet.google.com': 'meet', 'webex.com': 'webex'}


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [(n, wt.WORD) for n in ('wYear', 'wMonth', 'wDayOfWeek', 'wDay', 'wHour', 'wMinute', 'wSecond',
                                       'wMilliseconds')]


def regional(dt):
    """dt in Windows' short date and time format, which Outlook's filters expect (finding of 12 Oct 2026)."""
    st = SYSTEMTIME(dt.year, dt.month, 0, dt.day, dt.hour, dt.minute, 0, 0)
    d, t = ctypes.create_unicode_buffer(64), ctypes.create_unicode_buffer(64)
    ctypes.windll.kernel32.GetDateFormatEx(None, 1, ctypes.byref(st), None, d, 64, None)
    ctypes.windll.kernel32.GetTimeFormatEx(None, 2, ctypes.byref(st), None, t, 64)
    return f'{d.value} {t.value}'


def meeting_at(when, mode='start'):
    """{'subject', 'platform'} of the calendar item running at `when`, or None. Call off the main thread."""
    if mode == 'off':
        return None
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    try:
        if mode == 'if-running':
            ol = comtypes.client.GetActiveObject('Outlook.Application', dynamic=True)
        else:
            ol = comtypes.client.CreateObject('Outlook.Application', dynamic=True)
        items = ol.GetNamespace('MAPI').GetDefaultFolder(9).Items         # 9 = the calendar
        items.IncludeRecurrences = True
        items.Sort('[Start]')
        pad = datetime.timedelta(minutes=10)
        found = items.Restrict(f"[Start] <= '{regional(when + pad)}' AND [End] >= '{regional(when - pad)}'")
        best, best_gap = None, None
        it = found.GetFirst()
        while it is not None:
            start = it.Start
            start = datetime.datetime(start.year, start.month, start.day, start.hour, start.minute)
            gap = abs((start - when).total_seconds())
            if best is None or gap < best_gap:
                best, best_gap = it, gap
            it = found.GetNext()
        if best is None:
            return None
        link = LINK.search(f'{best.Location or ""}')
        return {'subject': (best.Subject or '').strip()[:200],
                'platform': PLATFORM.get(link.group(1).lower()) if link else None}
    except Exception as e:                  # Outlook not running (if-running), busy, or not set up
        log.info('no calendar match: %s', type(e).__name__)
        return None
    finally:
        comtypes.CoUninitialize()


def _outlook(mode):
    import comtypes.client
    if mode == 'if-running':
        return comtypes.client.GetActiveObject('Outlook.Application', dynamic=True)
    return comtypes.client.CreateObject('Outlook.Application', dynamic=True)


def upcoming(hours=12, mode='start', limit=5):
    """[{'subject', 'start', 'end', 'organizer', 'attendees'}] for calendar items from now on, for answer mode."""
    if mode == 'off':
        return []
    import comtypes
    comtypes.CoInitialize()
    try:
        items = _outlook(mode).GetNamespace('MAPI').GetDefaultFolder(9).Items
        items.IncludeRecurrences = True
        items.Sort('[Start]')
        now = datetime.datetime.now()
        found = items.Restrict(f"[End] >= '{regional(now)}' AND [Start] <= "
                               f"'{regional(now + datetime.timedelta(hours=hours))}'")
        out, it = [], found.GetFirst()
        while it is not None and len(out) < limit:
            s, e = it.Start, it.End
            out.append({'subject': (it.Subject or '').strip()[:200],
                        'start': datetime.datetime(s.year, s.month, s.day, s.hour, s.minute),
                        'end': datetime.datetime(e.year, e.month, e.day, e.hour, e.minute),
                        'organizer': (it.Organizer or '')[:80],
                        'attendees': (it.RequiredAttendees or '')[:300]})
            it = found.GetNext()
        return out
    except Exception as e:
        log.info('calendar not read: %s', type(e).__name__)
        return []
    finally:
        comtypes.CoUninitialize()


def current_mail():
    """(subject, sender, body) of the email open or selected in classic Outlook, or None. Untrusted text."""
    import comtypes
    comtypes.CoInitialize()
    try:
        ol = _outlook('if-running')
        insp = ol.ActiveInspector()
        item = insp.CurrentItem if insp else ol.ActiveExplorer().Selection.Item(1)
        return (item.Subject or ''), (getattr(item, 'SenderName', '') or ''), (item.Body or '')[:8000]
    except Exception as e:
        log.info('no open email: %s', type(e).__name__)
        return None
    finally:
        comtypes.CoUninitialize()


def open_reply_draft(text):
    """Open a reply to the current email as a draft window with this text on top. It never sends: there is no
    Send() anywhere in MWB, and you decide in Outlook. True if the draft opened."""
    import comtypes
    comtypes.CoInitialize()
    try:
        ol = _outlook('if-running')
        insp = ol.ActiveInspector()
        item = insp.CurrentItem if insp else ol.ActiveExplorer().Selection.Item(1)
        reply = item.Reply()
        reply.Body = text + '\r\n\r\n' + (reply.Body or '')
        reply.Display()
        return True
    except Exception as e:
        log.info('no draft opened: %s', type(e).__name__)
        return False
    finally:
        comtypes.CoUninitialize()
