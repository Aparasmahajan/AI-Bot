"""The on-screen indicator (design §13.3): a small layered window with per-pixel transparency, 48 px above the
taskbar on the screen you're working on. It never takes the keyboard focus, so your text still lands in your app.
Clicks pass straight through the pill; while a result panel is open (§8.3) the panel takes clicks for its buttons,
still without taking the focus, so Insert and Replace paste into the app you were in.

It redraws only when something changes: 30 frames a second while listening or working, 60 for the short moments the
pill grows, shrinks or fades, and not at all when idle. The drawing surface is kept between frames.

Create it, and call tick(), on the thread that runs the message loop; mouse messages arrive on that thread too.
set_state(), set_level(), set_words() and result() may be called from any thread: they only store values, which the
next tick draws."""
import ctypes, ctypes.wintypes as wt, logging, math, threading, time

from mwb.ui import art
from mwb.winapi import user32

log = logging.getLogger('mwb.indicator')
gdi32 = ctypes.WinDLL('gdi32')
WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_NOACTIVATE = \
    0x80000, 0x20, 0x80, 0x8, 0x08000000
GWL_EXSTYLE = -20
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
HWND_TOPMOST = wt.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x1, 0x2, 0x10, 0x40
ULW_ALPHA, AC_SRC_ALPHA = 0x2, 0x1
WM_SETCURSOR, WM_MOUSEACTIVATE, WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEWHEEL, WM_MOUSELEAVE = \
    0x20, 0x21, 0x200, 0x201, 0x202, 0x20A, 0x2A3
MA_NOACTIVATE, TME_LEAVE, IDC_ARROW, IDC_HAND = 3, 0x2, 32512, 32649
FRAME_S, FAST_S = 1 / 30, 1 / 60
PANEL_S = 0.08                  # streaming text redraws at most this often
EASE_S, LEVEL_UP_S, LEVEL_DOWN_S = 0.05, 0.035, 0.14        # time constants: pill size, voice bars rising, falling
DONE_S = 1.2                    # the green tick shows this long
SIZES = {'small': 1.0, 'medium': 1.25, 'large': 1.5}
DONE_LABELS = {'Copy': 'Copied', 'Insert': 'Inserted', 'Replace': 'Replaced'}   # buttons that finish the panel

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.CreateWindowExW.restype = wt.HWND
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.MonitorFromWindow.restype = wt.HANDLE
user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
user32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.c_void_p]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetShellWindow.restype = wt.HWND
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.DestroyWindow.argtypes = [wt.HWND]
user32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE), wt.HDC,
                                       ctypes.POINTER(wt.POINT), wt.COLORREF, ctypes.c_void_p, wt.DWORD]
user32.GetWindowLongW.restype = wt.LONG
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, wt.LONG]
user32.LoadCursorW.restype = wt.HANDLE
user32.LoadCursorW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
user32.SetCursor.argtypes = [wt.HANDLE]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE,
                                   wt.DWORD]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [('cbSize', wt.UINT), ('style', wt.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', wt.HINSTANCE), ('hIcon', wt.HICON),
                ('hCursor', wt.HANDLE), ('hbrBackground', wt.HBRUSH), ('lpszMenuName', wt.LPCWSTR),
                ('lpszClassName', wt.LPCWSTR), ('hIconSm', wt.HICON)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('rcMonitor', wt.RECT), ('rcWork', wt.RECT), ('dwFlags', wt.DWORD)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG), ('biPlanes', wt.WORD),
                ('biBitCount', wt.WORD), ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD),
                ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD),
                ('biClrImportant', wt.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [('BlendOp', ctypes.c_ubyte), ('BlendFlags', ctypes.c_ubyte), ('SourceConstantAlpha', ctypes.c_ubyte),
                ('AlphaFormat', ctypes.c_ubyte)]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('dwFlags', wt.DWORD), ('hwndTrack', wt.HWND), ('dwHoverTime', wt.DWORD)]


def _monitor_dpi(hmon):
    try:
        x, y = wt.UINT(), wt.UINT()
        ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(x), ctypes.byref(y))
        return x.value or 96
    except (AttributeError, OSError):
        return 96


def _ease(cur, target, dt, tau):
    """Move cur toward target as a critically damped spring would: fast at first, settling softly."""
    d = target - cur
    return target if abs(d) < 0.01 * max(1.0, abs(target)) else cur + d * (1 - math.exp(-dt / tau))


_windows = {}                   # hwnd -> Indicator, for the window procedure


def _wndproc(h, m, w, l):
    ind = _windows.get(h)
    if ind is not None:
        try:
            r = ind._on_message(m, w, l)
        except Exception:
            log.exception('indicator message failed')
            r = None
        if r is not None:
            return r
    return user32.DefWindowProcW(h, m, w, l)


_proc = WNDPROC(_wndproc)


class ResultPanel:
    """A result shown in the indicator's place: title, streaming text and buttons. Use it from any thread."""

    def __init__(self, indicator, title, note):
        self.indicator, self.title, self.note = indicator, title, note
        self.open, self.busy = True, True
        self.text = ''
        self.buttons = []
        self.scroll, self.follow = 0, True          # follow: keep the newest line in view while text streams in

    def _changed(self):
        self.indicator._panel_changed(self)

    def append(self, piece):
        if piece == '\x00restart':          # the router fell back to the local model: start again
            self.text = ''
            self.note = 'The API did not answer; the local model is writing instead.'
        else:
            self.text += piece
        self._changed()

    def set_text(self, text):
        self.text, self.busy = text, False
        self._changed()

    def set_note(self, note):
        self.note = note
        self._changed()

    def set_buttons(self, buttons):
        """[(label, fn)]; the last one is the main button. fn runs on the message-loop thread: hand real work on."""
        self.buttons, self.busy = list(buttons), False
        self._changed()

    def close(self):
        self.open = False
        self._changed()


class Indicator:
    def __init__(self, cfg):
        c = cfg['indicator']
        self.visible = bool(c['show'])
        self.always = c['visible'] == 'always'
        self.size = SIZES.get(c['size'], 1.0)
        self.opacity = round(255 * min(1.0, max(0.4, float(c['opacity']))))
        self.live_words = bool(c['live_words'])
        self.hide_fullscreen = bool(c['hide_in_fullscreen'])
        self.lock = threading.Lock()
        self.state, self.level, self.words, self.label = 'idle', 0.0, '', ''
        self.paused = False
        self.recording = False
        self.state_since = time.monotonic()
        self.dirty = True
        self.last_frame = self.last_tick = 0.0
        self.last_place = 0.0
        self.shown = False
        self.fullscreen = False
        self.monitor, self.work, self.dpi = None, None, 96
        self.pill_size = None                   # (w, h) now, easing toward the state's size
        self.shown_level = 0.0
        self.panel = None                       # the ResultPanel on screen, or fading out
        self.panel_img, self.panel_regions, self.panel_max = None, [], 0
        self.panel_alpha, self.panel_dirty, self.last_panel = 0.0, False, 0.0
        self.regions = []                       # clickable boxes in window pixels
        self.hover, self.pressed, self.tracking = None, None, False
        self.click_through = True
        self.surface = None                     # (w, h, memory DC, bitmap, bits, old object), kept between frames
        self.arrow = user32.LoadCursorW(None, ctypes.c_void_p(IDC_ARROW))
        self.hand = user32.LoadCursorW(None, ctypes.c_void_p(IDC_HAND))
        self.hwnd = self._create()
        _windows[self.hwnd] = self

    def _create(self):
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.lpfnWndProc = _proc
        wc.hInstance = hinst
        wc.hCursor = self.arrow
        wc.lpszClassName = 'MWB.Indicator'
        user32.RegisterClassExW(ctypes.byref(wc))
        return user32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_TOPMOST |
                                      WS_EX_NOACTIVATE, 'MWB.Indicator', 'MWB indicator', WS_POPUP,
                                      0, 0, 1, 1, None, None, hinst, None)

    # ---- from any thread -------------------------------------------------------------------------------------

    def set_state(self, state, label=''):
        with self.lock:
            if state != self.state or label != self.label:
                self.state, self.label, self.state_since, self.dirty = state, label, time.monotonic(), True
                if state in ('idle', 'listening'):
                    self.words = ''
                if state != 'listening':
                    self.level = 0.0

    def set_level(self, level):
        self.level = level              # read by the animation only; no lock needed for one float

    def set_words(self, words):
        with self.lock:
            self.words, self.dirty = words, True

    def set_recording(self, on):
        with self.lock:
            self.recording, self.dirty = on, True

    def set_paused(self, paused):
        with self.lock:
            self.paused, self.dirty = paused, True

    def toggle(self):
        self.visible = not self.visible
        self.dirty = True
        return self.visible

    def result(self, title, note=''):
        """A result panel above the pill whose text streams in; it replaces any panel already open."""
        panel = ResultPanel(self, title, note)
        with self.lock:
            if self.panel is not None:
                self.panel.open = False
            self.panel, self.panel_dirty, self.dirty = panel, True, True
        return panel

    @property
    def panel_open(self):
        p = self.panel
        return p is not None and p.open

    def close_panel(self):
        p = self.panel
        if p is not None:
            p.close()

    def _panel_changed(self, panel):
        if panel is self.panel:
            self.panel_dirty = self.dirty = True

    # ---- on the message-loop thread --------------------------------------------------------------------------

    def tick(self, now):
        dt, self.last_tick = min(0.1, now - self.last_tick), now
        with self.lock:
            state, words, label = self.state, self.words, self.label
            if state == 'done' and now - self.state_since > DONE_S:
                self.state, state, self.label, label, self.dirty = 'idle', 'idle', '', '', True
            shown_state = 'paused' if self.paused and state == 'idle' else state
            animating = shown_state in ('listening', 'working', 'loading')
            dirty, self.dirty = self.dirty, False
            panel = self.panel if self.panel is not None and self.panel.open else None
        want_pill = self.visible and (self.always or shown_state != 'idle' or self.recording)
        want = want_pill or panel is not None or self.panel_alpha > 0
        if want and (now - self.last_place > 1.0 or self.work is None):     # once a second: which screen, full screen?
            self.last_place = now
            self.fullscreen = self.hide_fullscreen and self._fullscreen_in_front()
            dirty |= self._follow_monitor()
        if not want or (self.fullscreen and panel is None):     # a result you asked for shows even over full screen
            if self.shown:
                user32.ShowWindow(self.hwnd, SW_HIDE)
                self.shown = False
            self.pill_size, self.panel_alpha, self.panel_img = None, 0.0, None
            self._set_click_through(True)
            return

        moving = False
        target = art.size_of(shown_state, label)
        if self.pill_size is None:
            self.pill_size = target
        elif self.pill_size != target:
            self.pill_size = tuple(_ease(c, t, dt, EASE_S) for c, t in zip(self.pill_size, target))
            moving = True
        aim = self.level if shown_state == 'listening' else 0.0
        self.shown_level = _ease(self.shown_level, aim, dt, LEVEL_UP_S if aim > self.shown_level else LEVEL_DOWN_S)

        scale = self.dpi / 96
        if panel is not None and (self.panel_dirty or self.panel_img is None) and now - self.last_panel >= PANEL_S:
            self._draw_panel(panel, scale)
            self.last_panel, dirty = now, True
        alpha_aim = 1.0 if panel is not None else 0.0
        if self.panel_alpha != alpha_aim:
            self.panel_alpha = _ease(self.panel_alpha, alpha_aim, dt, EASE_S)
            if self.panel_alpha < 0.02 and alpha_aim == 0:
                self.panel_alpha, self.panel_img = 0.0, None
                with self.lock:
                    if self.panel is not None and not self.panel.open:
                        self.panel = None
            moving = True
        self._set_click_through(panel is None)

        frame = FAST_S if moving else FRAME_S
        if not (dirty or not self.shown or ((animating or moving) and now - self.last_frame >= frame)):
            return
        self.last_frame = now
        layers, gaps = [], []
        if self.panel_img is not None:
            img = self.panel_img
            if self.panel_alpha < 1:
                img = img.copy()
                img.putalpha(img.getchannel('A').point(lambda v, a=self.panel_alpha: round(v * a)))
            layers.append(('panel', img))
            gaps.append(round((4 + 10 * (1 - self.panel_alpha)) * scale))  # it rises as it fades in, sinks as it goes
        if want_pill:
            pill_scale = self.size * scale
            pill = art.capsule(shown_state, pill_scale, self.shown_level, now, self.pill_size, label)
            if self.recording:
                pill = art.with_ring(pill, pill_scale)
            if self.live_words and words and shown_state in ('listening', 'working'):
                layers.append(('words', art.words_box(words, pill_scale)))
                gaps.append(round(4 * pill_scale))
            layers.append(('pill', pill))
        if not layers:
            return
        img, corners = art.stack([i for _, i in layers], gaps)
        self.regions = []
        if layers[0][0] == 'panel' and panel is not None:
            ox, oy = corners[0]
            self.regions = [(key, (x0 + ox, y0 + oy, x1 + ox, y1 + oy)) for key, (x0, y0, x1, y1) in
                            self.panel_regions]
        self._blit(img, 255 if self.panel_img is not None else self.opacity)

    def _draw_panel(self, panel, scale):
        self.panel_dirty = False
        scroll = 10 ** 6 if panel.follow else panel.scroll
        self.panel_img, self.panel_regions, self.panel_max = art.panel(
            panel.title, panel.note, panel.text, tuple(b[0] for b in panel.buttons), self.hover, scroll, scale,
            panel.busy)
        if panel.follow:
            panel.scroll = self.panel_max

    # ---- the mouse, while a panel is open --------------------------------------------------------------------

    def _set_click_through(self, on):
        if on == self.click_through:
            return
        self.click_through = on
        ex = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT if on else ex & ~WS_EX_TRANSPARENT)
        if on:
            self.hover = self.pressed = None

    def _hit(self, x, y):
        for key, (x0, y0, x1, y1) in self.regions:
            if x0 <= x < x1 and y0 <= y < y1:
                return key
        return None

    def _on_message(self, m, w, l):
        if m == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE                    # a click never takes the focus from your app
        if m == WM_SETCURSOR:
            user32.SetCursor(self.hand if self.hover else self.arrow)
            return 1
        if m in (WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP):
            x, y = ctypes.c_short(l & 0xFFFF).value, ctypes.c_short((l >> 16) & 0xFFFF).value
            hit = self._hit(x, y)
            if m == WM_MOUSEMOVE:
                if not self.tracking:
                    t = TRACKMOUSEEVENT(ctypes.sizeof(TRACKMOUSEEVENT), TME_LEAVE, self.hwnd, 0)
                    self.tracking = bool(user32.TrackMouseEvent(ctypes.byref(t)))
                self._set_hover(hit)
            elif m == WM_LBUTTONDOWN:
                self.pressed = hit
            else:
                if hit is not None and hit == self.pressed:
                    self._click(hit)
                self.pressed = None
            return 0
        if m == WM_MOUSELEAVE:
            self.tracking = False
            self._set_hover(None)
            return 0
        if m == WM_MOUSEWHEEL:
            self._scroll(-ctypes.c_short((w >> 16) & 0xFFFF).value / 120 * 3)
            return 0
        return None

    def _set_hover(self, hit):
        if hit != self.hover:
            self.hover = hit
            self.panel_dirty, self.last_panel = True, 0.0

    def _scroll(self, lines):
        p = self.panel
        if p is None or not p.open or not self.panel_max:
            return
        p.scroll = min(self.panel_max, max(0, round(p.scroll + lines)))
        p.follow = p.scroll >= self.panel_max and p.busy
        self.panel_dirty, self.last_panel = True, 0.0

    def _click(self, hit):
        p = self.panel
        if p is None or not p.open:
            return
        if hit[0] == 'close':
            p.close()
            return
        if hit[1] >= len(p.buttons):
            return
        label, fn = p.buttons[hit[1]]
        done = DONE_LABELS.get(label.split()[0])
        if done:
            p.close()                               # Copy, Insert, Replace finish it; Open… keeps it open
        try:
            fn()
        except Exception:
            log.exception('panel button failed')
            return
        if done:
            self.set_state('done', done)

    # ---- placing and painting --------------------------------------------------------------------------------

    def _follow_monitor(self):
        hmon = user32.MonitorFromWindow(user32.GetForegroundWindow(), 2)       # MONITOR_DEFAULTTONEAREST
        if hmon == self.monitor and self.work is not None:
            return False
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        self.monitor, self.work, self.dpi = hmon, mi.rcWork, _monitor_dpi(hmon)
        return True

    def _fullscreen_in_front(self):
        fg = user32.GetForegroundWindow()
        if not fg or fg == user32.GetShellWindow():
            return False
        r = wt.RECT()
        user32.GetWindowRect(fg, ctypes.byref(r))
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        user32.GetMonitorInfoW(user32.MonitorFromWindow(fg, 2), ctypes.byref(mi))
        m = mi.rcMonitor
        cls = ctypes.create_unicode_buffer(64)
        ctypes.windll.user32.GetClassNameW(fg, cls, 64)
        if cls.value in ('Progman', 'WorkerW'):         # the desktop itself
            return False
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom

    def _surface(self, w, h):
        """A memory DC with a 32-bit bitmap of this size, made again only when the size changes."""
        if self.surface and self.surface[:2] == (w, h):
            return self.surface
        self._free_surface()
        mem = gdi32.CreateCompatibleDC(None)
        bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        hbm = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        self.surface = (w, h, mem, hbm, bits, gdi32.SelectObject(mem, hbm))
        return self.surface

    def _free_surface(self):
        if self.surface:
            _, _, mem, hbm, _, old = self.surface
            gdi32.SelectObject(mem, old)
            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(mem)
            self.surface = None

    def _blit(self, img, opacity):
        w, h = img.size
        work = self.work
        x = (work.left + work.right - w) // 2
        y = work.bottom - round(48 * self.dpi / 96) - h
        data = img.tobytes('raw', 'BGRa')               # premultiplied alpha, as Windows wants it
        _, _, mem, _, bits, _ = self._surface(w, h)
        ctypes.memmove(bits, data, len(data))
        screen = user32.GetDC(None)
        try:
            blend = BLENDFUNCTION(0, 0, opacity, AC_SRC_ALPHA)
            user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(wt.POINT(x, y)), ctypes.byref(wt.SIZE(w, h)),
                                       mem, ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)
        finally:
            user32.ReleaseDC(None, screen)
        if not self.shown:
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
            self.shown = True

    def close(self):
        if self.hwnd:
            _windows.pop(self.hwnd, None)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        self._free_surface()
