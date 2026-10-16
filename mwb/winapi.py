"""The Win32 calls the core shares, through ctypes (design §13.1, §16.1): key state, SendInput, the clipboard, memory.
No keyboard hook anywhere: MWB reads the state of a few keys and never sees what you type."""
import ctypes, ctypes.wintypes as wt, time

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.OpenClipboard.argtypes = [wt.HWND]
user32.GetClipboardData.restype = wt.HANDLE
user32.GetClipboardData.argtypes = [wt.UINT]
user32.SetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.IsClipboardFormatAvailable.argtypes = [wt.UINT]
user32.CountClipboardFormats.restype = ctypes.c_int
user32.RegisterClipboardFormatW.restype = wt.UINT
user32.RegisterClipboardFormatW.argtypes = [wt.LPCWSTR]
user32.GetClipboardSequenceNumber.restype = wt.DWORD
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalFree.argtypes = [wt.HGLOBAL]
kernel32.GetCurrentProcess.restype = wt.HANDLE
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]

VK_SHIFT, VK_CONTROL, VK_MENU, VK_CAPITAL, VK_ESCAPE, VK_SPACE = 0x10, 0x11, 0x12, 0x14, 0x1B, 0x20
VK_LWIN, VK_RWIN, VK_TAB, VK_V = 0x5B, 0x5C, 0x09, 0x56
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_TIMER, WM_HOTKEY, WM_QUIT, WM_APP = 0x0113, 0x0312, 0x0012, 0x8000
CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x2
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x2, 0x4


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wt.WORD), ('wScan', wt.WORD), ('dwFlags', wt.DWORD), ('time', wt.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):     # only here so the union has the right size
    _fields_ = [('dx', wt.LONG), ('dy', wt.LONG), ('mouseData', wt.DWORD), ('dwFlags', wt.DWORD),
                ('time', wt.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wt.DWORD), ('u', _U)]


user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]


def send_keys(*strokes):
    """strokes: (vk, up) pairs, sent as one SendInput batch so nothing can slip in between."""
    arr = (INPUT * len(strokes))()
    for i, (vk, up) in enumerate(strokes):
        arr[i].type = 1
        arr[i].ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
    return user32.SendInput(len(strokes), arr, ctypes.sizeof(INPUT))


def type_text(text):
    """Type text as Unicode key events, for apps that block paste. Newlines become Enter."""
    events = []
    for ch in text.replace('\r\n', '\n'):
        if ch == '\n':
            events += [(0x0D, 0, 0), (0x0D, 0, KEYEVENTF_KEYUP)]
            continue
        units = ch.encode('utf-16-le')                                  # surrogate pairs go as two units
        for i in range(0, len(units), 2):
            code = int.from_bytes(units[i:i + 2], 'little')
            events += [(0, code, KEYEVENTF_UNICODE), (0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    for start in range(0, len(events), 200):
        chunk = events[start:start + 200]
        arr = (INPUT * len(chunk))()
        for i, (vk, scan, flags) in enumerate(chunk):
            arr[i].type = 1
            arr[i].ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        user32.SendInput(len(chunk), arr, ctypes.sizeof(INPUT))
        time.sleep(0.01)


def down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def caps_on():
    return bool(user32.GetKeyState(VK_CAPITAL) & 1)


def modifiers_down():
    return any(down(vk) for vk in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN, VK_CAPITAL, VK_SPACE))


def wait_keys_up(timeout=3.0):
    """Wait until Ctrl, Alt, Shift, Win, Caps Lock and Space are all up, so a paste never arrives as Ctrl+Alt+V."""
    end = time.monotonic() + timeout
    while modifiers_down() and time.monotonic() < end:
        time.sleep(0.015)
    return not modifiers_down()


# ---- clipboard -------------------------------------------------------------------------------------------------

_NO_HISTORY = None


def _open_clipboard():
    for _ in range(25):                 # another app may hold it for a moment
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def clipboard_get():
    """The clipboard's text; '' when empty; None when it holds something else (an image, files) or can't be opened."""
    if not _open_clipboard():
        return None
    try:
        if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            h = user32.GetClipboardData(CF_UNICODETEXT)
            p = kernel32.GlobalLock(h) if h else None
            if not p:
                return None
            try:
                return ctypes.wstring_at(p)
            finally:
                kernel32.GlobalUnlock(h)
        return '' if user32.CountClipboardFormats() == 0 else None
    finally:
        user32.CloseClipboard()


def clipboard_set(text, private=False):
    """Put text on the clipboard. private=True keeps it out of Windows' clipboard history (Win+V) and cloud sync."""
    global _NO_HISTORY
    if not _open_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        if text:
            data = text.encode('utf-16-le') + b'\0\0'
            h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            p = kernel32.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            kernel32.GlobalUnlock(h)
            if not user32.SetClipboardData(CF_UNICODETEXT, h):
                kernel32.GlobalFree(h)
                return False
        if private:
            if _NO_HISTORY is None:
                _NO_HISTORY = [user32.RegisterClipboardFormatW(n) for n in
                               ('ExcludeClipboardContentFromMonitorProcessing', 'CanIncludeInClipboardHistory',
                                'CanUploadToCloudClipboard')]
            for fmt in _NO_HISTORY:
                h = kernel32.GlobalAlloc(GMEM_MOVEABLE, 4)      # a DWORD 0: "no"
                p = kernel32.GlobalLock(h)
                ctypes.memmove(p, b'\0\0\0\0', 4)
                kernel32.GlobalUnlock(h)
                if not user32.SetClipboardData(fmt, h):
                    kernel32.GlobalFree(h)
        return True
    finally:
        user32.CloseClipboard()


# ---- windows and processes -------------------------------------------------------------------------------------

def foreground_app():
    """(hwnd, exe name such as 'Code.exe') of the window in front. The title is not read: it can hold private text."""
    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    name = ''
    h = kernel32.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        buf, size = ctypes.create_unicode_buffer(520), wt.DWORD(520)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            name = buf.value.rsplit('\\', 1)[-1]
        kernel32.CloseHandle(h)
    return hwnd, name


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [('dwLength', wt.DWORD), ('dwMemoryLoad', wt.DWORD), ('ullTotalPhys', ctypes.c_ulonglong),
                ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong),
                ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong),
                ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


def free_gb():
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(m)
    kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2 ** 30


class PMC(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


_psapi = ctypes.WinDLL('psapi')
_psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]


def process_mb(handle=None):
    """(working set, private bytes) in MB, of this process or of the process handle given."""
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    _psapi.GetProcessMemoryInfo(handle or kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return round(c.WorkingSetSize / 2 ** 20), round(c.PagefileUsage / 2 ** 20)


def single_instance(name='Local\\MWB.core'):
    """Hold a named mutex for the life of the process; False if another MWB already holds it."""
    global _MUTEX
    _MUTEX = kernel32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != 183           # ERROR_ALREADY_EXISTS


_MUTEX = None


def dpi_aware():
    """Per-monitor DPI awareness, so the indicator is sharp and placed right on scaled screens. Call before any window."""
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):      # PER_MONITOR_AWARE_V2
            return
    except AttributeError:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


# ---- child processes end with the core ---------------------------------------------------------------------------

class _BASIC_LIMIT(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                ('LimitFlags', wt.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wt.DWORD),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', wt.DWORD), ('SchedulingClass', wt.DWORD)]


class _EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', _BASIC_LIMIT), ('IoInfo', ctypes.c_ulonglong * 6),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


kernel32.CreateJobObjectW.restype = wt.HANDLE
kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
kernel32.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
kernel32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
_JOB = None


def end_with_me(proc):
    """Put a child process (subprocess.Popen) in a job that Windows ends when the core exits, even by a crash,
    so a speech engine can never be left holding a gigabyte."""
    global _JOB
    if _JOB is None:
        job = kernel32.CreateJobObjectW(None, None)
        info = _EXTENDED_LIMIT()
        info.BasicLimitInformation.LimitFlags = 0x2000          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
        _JOB = job
    return bool(kernel32.AssignProcessToJobObject(_JOB, wt.HANDLE(int(proc._handle))))
