"""P0-3 with comtypes: the reads of p0_3_outlook.ps1, from Python, the way MWB's Outlook collector will make them.
Today's calendar (including meeting links in the invitation body, a guarded property) and the newest Sent Items
subjects, late-bound (dynamic=True) so comtypes generates no wrapper modules. Prints counts, timings and this
process's memory, never subjects or names. If Outlook isn't running it is started without a window (decision 4).

  .venv\\Scripts\\python.exe -I docs\\bench\\p0_3_outlook_comtypes.py

Dates in Restrict filters are written in your Windows regional format, as Outlook expects (finding of 12 Oct)."""
import ctypes, ctypes.wintypes as wt, datetime, re, subprocess, time


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD)] + [
        (n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                                       'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                                       'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


_GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
_GetCurrentProcess.restype = wt.HANDLE                       # a 64-bit pseudo-handle: the default int would cut it
_GetProcessMemoryInfo = ctypes.windll.kernel32.K32GetProcessMemoryInfo
_GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wt.DWORD]


def memory_mb():
    """(private, working set) of this process in MB."""
    c = PROCESS_MEMORY_COUNTERS_EX(cb=ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX))
    if not _GetProcessMemoryInfo(_GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise ctypes.WinError()
    return round(c.PrivateUsage / 2**20, 1), round(c.WorkingSetSize / 2**20, 1)


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [(n, wt.WORD) for n in ('wYear', 'wMonth', 'wDayOfWeek', 'wDay', 'wHour', 'wMinute', 'wSecond',
                                       'wMilliseconds')]


def regional(dt):
    """dt as Windows' short date and time for your region, e.g. 13-10-2026 10:30 on en-IN."""
    st = SYSTEMTIME(dt.year, dt.month, 0, dt.day, dt.hour, dt.minute, 0, 0)
    d, t = ctypes.create_unicode_buffer(64), ctypes.create_unicode_buffer(64)
    ctypes.windll.kernel32.GetDateFormatEx(None, 1, ctypes.byref(st), None, d, 64, None)      # DATE_SHORTDATE
    ctypes.windll.kernel32.GetTimeFormatEx(None, 2, ctypes.byref(st), None, t, 64)            # TIME_NOSECONDS
    return f'{d.value} {t.value}'


def items(collection):
    """Every item of an Outlook Items collection. Count is unreliable with IncludeRecurrences, so walk it."""
    it = collection.GetFirst()
    while it is not None:
        yield it
        it = collection.GetNext()


mem_start = memory_mb()
t = time.perf_counter()
from comtypes import COMError                               # noqa: E402  (measured: the import's cost)
from comtypes.client import CreateObject                     # noqa: E402
t_import, mem_import = time.perf_counter() - t, memory_mb()

was_running = b'OUTLOOK.EXE' in subprocess.run(['tasklist', '/FI', 'IMAGENAME eq OUTLOOK.EXE', '/NH'],
                                               capture_output=True).stdout.upper()
t = time.perf_counter()
ol = CreateObject('Outlook.Application', dynamic=True)       # joins the running Outlook, or starts one
ns = ol.GetNamespace('MAPI')
t_connect = time.perf_counter() - t

today = datetime.datetime.combine(datetime.date.today(), datetime.time())
link = re.compile(r'teams\.microsoft\.com|zoom\.us|meet\.google\.com|webex\.com', re.I)


def calendar(days):
    """Meetings overlapping the next `days` days, and how many carry a meeting link in Location or Body."""
    cal = ns.GetDefaultFolder(9).Items                       # 9 = olFolderCalendar
    cal.IncludeRecurrences = True
    cal.Sort('[Start]')
    found = list(items(cal.Restrict(f"[Start] < '{regional(today + datetime.timedelta(days=days))}' "
                                    f"AND [End] > '{regional(today)}'")))
    return found, sum(bool(link.search(f'{m.Location} {m.Body}')) for m in found)   # Body: a guarded property


def guarded_read(m):
    """Read two guarded properties, the body and the first recipient's address; nothing is kept or printed.
    Sent Items also holds meeting replies and reports, which lack some properties: those count as not read."""
    try:
        r = m.Recipients
        return m.Body is not None and (r.Item(1).Address if r.Count else '') is not None
    except (AttributeError, NameError, COMError):
        return False


t = time.perf_counter()
meetings, with_link = calendar(1)
t_cal = time.perf_counter() - t
week, week_link = calendar(7)

t = time.perf_counter()
sent = ns.GetDefaultFolder(5).Items                          # 5 = olFolderSentMail
sent.Sort('[SentOn]', True)
sent_today = list(items(sent.Restrict(f"[SentOn] >= '{regional(today)}'")))
newest = sent.GetFirst()
read_from = sent_today or [m for m, _ in zip(items(sent), range(5))]
subjects = [m.Subject for m in read_from]
guarded = sum(guarded_read(m) for m in read_from)
t_sent = time.perf_counter() - t
mem_end = memory_mb()

print(f'Outlook was running      {was_running}')
print(f'import comtypes          {t_import:.2f} s, process memory {mem_start} -> {mem_import} MB (private, working set)')
print(f'connect                  {t_connect:.2f} s')
print(f'calendar today           {len(meetings)} item(s), {with_link} with a meeting link, read in {t_cal:.2f} s')
print(f'calendar next 7 days     {len(week)} item(s), {week_link} with a meeting link (bodies read: {len(week)})')
print(f'filter dates look like   {regional(today)}')
if newest:
    print(f'sent today               {len(sent_today)}; read {len(read_from)} newest: subjects '
          f'{sum(s is not None for s in subjects)}, guarded body and recipient {guarded}; newest sent '
          f'{newest.SentOn:%Y-%m-%d} ({t_sent:.2f} s)')
else:
    print('sent items               none')
print(f'process memory at end    {mem_end} MB (private, working set)')
if not was_running:
    ol.Quit()
