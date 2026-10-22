"""The API key window: paste your Groq key once; MWB checks it with Groq and keeps it in Windows Credential Manager.

Until the tray icon exists (Phase 1), open it with "Set API key.cmd" in the MWB folder; from Phase 1 the tray menu
opens the same window. Or run: .venv\\Scripts\\pythonw.exe -m mwb.ui.api_key

The key is never shown in full, printed, logged or written to a file: only Groq and Credential Manager see it."""
import ctypes, queue, threading, tkinter as tk, webbrowser
from tkinter import messagebox, ttk

from mwb import credentials
from mwb.llm import client
from mwb.llm.providers import GROQ

# The demo's light theme (docs/src/demo/MWB-Demo.html), so MWB's windows look like one product
SHEET, PAPER, INK, INK_2, INK_3, RULE, FADED = '#FFFFFF', '#F3F5F8', '#0E1726', '#465267', '#66738A', '#D3D9E3', '#A7B0BF'
COBALT, COBALT_DARK, COBALT_SOFT = '#2148C9', '#1A3AA3', '#A9B8EA'
OK, OK_WASH, AMBER, AMBER_WASH, SIGNAL = '#21734B', '#DDF2E6', '#946000', '#F7ECD3', '#CF3F0A'
FONT = 'Segoe UI'

WHY_NOT = {     # what a failed check means, in plain words
    'network': "Couldn't reach {host}. Check the internet connection or VPN.",
    'certificate': 'The secure connection to {host} was blocked; the network may be inspecting HTTPS.',
    'timeout': "{host} didn't answer within 15 seconds.",
    'error': '{host} answered with an error.',
}


def clean_key(text):
    """Drop what often comes along when a key is copied: spaces, quotes, line breaks, a "Bearer " prefix."""
    key = text.strip().strip('"\'')
    if key.lower().startswith('bearer '):
        key = key[7:]
    return ''.join(key.split())


def _prepare_process():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)      # sharp text on scaled displays; must run before Tk starts
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('MWB.Settings')   # its own taskbar entry
    except (AttributeError, OSError):
        pass


def _icon(size):
    """MWB's mark, drawn so no image file is needed: a cobalt disc with a white microphone."""
    img = tk.PhotoImage(width=size, height=size)
    r = size / 2
    for y in range(size):
        dy = abs(y + 0.5 - r)
        half = (r * r - dy * dy) ** 0.5
        img.put(COBALT, to=(round(r - half), y, round(r + half), y + 1))
    u = size / 32                                       # drawn on a 32-pixel grid
    for x1, y1, x2, y2 in ((13, 7, 19, 19), (14, 6, 18, 20), (10, 16, 11, 21), (21, 16, 22, 21),
                           (11, 21, 21, 22), (15, 22, 17, 25), (11, 25, 21, 26)):
        img.put('#FFFFFF', to=(round(x1 * u), round(y1 * u), max(round(x2 * u), round(x1 * u) + 1),
                              max(round(y2 * u), round(y1 * u) + 1)))
    return img


def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = (x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1)
    return canvas.create_polygon(pts, smooth=True, **kw)


class ApiKeyWindow:
    def __init__(self, root, provider=GROQ):
        self.root, self.p = root, provider
        self.target = credentials.api_key_target(provider.id)
        self.host = provider.base.split('/')[2]
        self.done = queue.Queue()                           # results from the checking thread
        self.busy = self.stored = False
        self.scale = root.winfo_fpixels('1i') / 96          # 1.0 at 100 % display scaling
        root.title(f'MWB · {provider.label} API key')
        root.configure(bg=SHEET)
        root.resizable(False, False)
        self._icons = (_icon(self.px(32)), _icon(self.px(16)))
        root.iconphoto(True, *self._icons)
        root.report_callback_exception = self._crash
        root.bind('<Escape>', lambda e: root.destroy())
        self._styles()
        self._build()
        self.refresh()
        self._place()

    def px(self, n):
        return round(n * self.scale)

    def _styles(self):
        s, px = ttk.Style(self.root), self.px
        s.theme_use('clam')
        s.configure('.', background=SHEET, foreground=INK, font=(FONT, 10))
        s.configure('Title.TLabel', font=(FONT + ' Semibold', 15))
        s.configure('Sub.TLabel', foreground=INK_2)
        s.configure('Field.TLabel', foreground=INK_3)
        s.configure('Small.TLabel', foreground=INK_3, font=(FONT, 9))
        s.configure('Link.TLabel', foreground=COBALT, font=(FONT, 9, 'underline'))
        s.configure('TSeparator', background=RULE)
        s.configure('TEntry', fieldbackground=SHEET, foreground=INK, insertcolor=INK, bordercolor=RULE,
                    lightcolor=SHEET, darkcolor=SHEET, padding=(px(8), px(6)))
        s.map('TEntry', bordercolor=[('focus', COBALT)], lightcolor=[('focus', COBALT)])
        s.configure('TCheckbutton', foreground=INK_2, indicatorbackground=SHEET, indicatorforeground=COBALT,
                    upperbordercolor=RULE, lowerbordercolor=RULE)
        s.map('TCheckbutton', background=[('active', SHEET)], indicatorbackground=[('pressed', PAPER)])
        s.configure('TButton', padding=(px(16), px(6)), background=SHEET, foreground=INK, bordercolor=RULE,
                    lightcolor=SHEET, darkcolor=SHEET, focuscolor=COBALT_SOFT)
        hover = [('disabled', SHEET), ('pressed', PAPER), ('active', PAPER)]
        s.map('TButton', background=hover, lightcolor=hover, darkcolor=hover, foreground=[('disabled', FADED)],
              bordercolor=[('focus', COBALT)])
        s.configure('Danger.TButton', foreground=SIGNAL)
        s.map('Danger.TButton', foreground=[('disabled', FADED)])
        s.configure('Primary.TButton', background=COBALT, foreground='#FFFFFF', bordercolor=COBALT,
                    lightcolor=COBALT, darkcolor=COBALT, focuscolor='#FFFFFF')
        fill = [('disabled', COBALT_SOFT), ('pressed', COBALT_DARK), ('active', COBALT_DARK)]
        s.map('Primary.TButton', background=fill, bordercolor=fill, lightcolor=fill, darkcolor=fill,
              foreground=[('disabled', '#FFFFFF')])

    def _build(self):
        px, p = self.px, self.p
        outer = ttk.Frame(self.root, padding=(px(24), px(20), px(24), px(18)))
        outer.grid(sticky='nsew')
        wrap = px(440)
        outer.columnconfigure(0, minsize=wrap + px(4))     # same width whatever the status line says

        head = ttk.Frame(outer)
        head.grid(row=0, column=0, sticky='w')
        badge = tk.Canvas(head, width=px(38), height=px(38), bg=SHEET, highlightthickness=0)
        _round_rect(badge, 0, 0, px(38), px(38), px(10), fill=COBALT, outline='')
        badge.create_text(px(19), px(19), text='M', fill='#FFFFFF', font=(FONT + ' Semibold', 14))
        badge.grid(row=0, column=0, rowspan=2, padx=(0, px(12)), sticky='n')
        ttk.Label(head, text='API key', style='Title.TLabel').grid(row=0, column=1, sticky='w')
        ttk.Label(head, style='Sub.TLabel', wraplength=wrap - px(50),
                  text=f'Writing, notes, email and the journal go to {p.label} first. '
                       'Speech never leaves this laptop.').grid(row=1, column=1, sticky='w')

        ttk.Separator(outer).grid(row=1, column=0, sticky='ew', pady=px(16))

        form = ttk.Frame(outer)
        form.grid(row=2, column=0, sticky='ew')
        form.columnconfigure(1, weight=1)
        label = dict(style='Field.TLabel')
        ttk.Label(form, text='Provider', **label).grid(row=0, column=0, sticky='w', padx=(0, px(18)))
        ttk.Label(form, text=f'{p.label}  ·  {p.model}').grid(row=0, column=1, sticky='w')
        ttk.Label(form, text='Status', **label).grid(row=1, column=0, sticky='w', pady=px(12))
        self.chip = tk.Label(form, font=(FONT, 9), padx=px(10), pady=px(3), anchor='w')
        self.chip.grid(row=1, column=1, sticky='w', pady=px(12))
        ttk.Label(form, text='Key', **label).grid(row=2, column=0, sticky='w')
        line = ttk.Frame(form)
        line.grid(row=2, column=1, sticky='ew')
        line.columnconfigure(0, weight=1)
        self.key = tk.StringVar()
        self.entry = ttk.Entry(line, textvariable=self.key, show='•', width=38, font=(FONT, 10))
        self.entry.grid(row=0, column=0, sticky='ew')
        self.show = tk.BooleanVar(value=False)
        ttk.Checkbutton(line, text='Show', variable=self.show,
                        command=lambda: self.entry.configure(show='' if self.show.get() else '•')
                        ).grid(row=0, column=1, padx=(px(10), 0))
        hint = ttk.Frame(form)
        hint.grid(row=3, column=1, sticky='w', pady=(px(6), 0))
        self.hint = ttk.Label(hint, style='Small.TLabel')
        self.hint.grid(row=0, column=0)
        link = ttk.Label(hint, text=p.key_page.split('//')[1], style='Link.TLabel', cursor='hand2')
        link.grid(row=0, column=1)
        link.bind('<Button-1>', lambda e: webbrowser.open(p.key_page))

        buttons = ttk.Frame(outer)
        buttons.grid(row=3, column=0, sticky='ew', pady=(px(20), 0))
        buttons.columnconfigure(1, weight=1)
        self.check_btn = ttk.Button(buttons, text='Check key', command=self.check)
        self.check_btn.grid(row=0, column=0)
        self.remove_btn = ttk.Button(buttons, text='Remove', style='Danger.TButton', command=self.remove)
        self.remove_btn.grid(row=0, column=2, padx=(0, px(8)))
        self.save_btn = ttk.Button(buttons, text='Save', style='Primary.TButton', command=self.save)
        self.save_btn.grid(row=0, column=3)

        self.result = tk.Label(outer, bg=SHEET, font=(FONT, 9), anchor='nw', justify='left', wraplength=wrap, height=2)
        self.result.grid(row=4, column=0, sticky='ew', pady=(px(12), 0))
        self._say(f'Save checks the key with {p.label} first; a key {p.label} rejects is never stored.', INK_3)

        ttk.Separator(outer).grid(row=5, column=0, sticky='ew', pady=(px(10), px(10)))
        ttk.Label(outer, style='Small.TLabel', wraplength=wrap,
                  text=f'Kept in Windows Credential Manager as "{self.target}", protected by your Windows '
                       'sign-in. Never written to a file or shown in full.').grid(row=6, column=0, sticky='w')

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='Paste', command=lambda: self.entry.event_generate('<<Paste>>'))
        menu.add_command(label='Clear', command=lambda: self.key.set(''))
        self.entry.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
        self.entry.bind('<Return>', lambda e: self.save())

    def _place(self):
        r = self.root
        r.update_idletasks()
        w, h = r.winfo_reqwidth(), r.winfo_reqheight()
        r.geometry(f'+{(r.winfo_screenwidth() - w) // 2}+{(r.winfo_screenheight() - h) // 3}')

    def activate(self):
        """Bring the window to the front with the cursor in the key box."""
        r = self.root
        r.lift()
        r.attributes('-topmost', True)
        r.after(400, lambda: r.attributes('-topmost', False))
        self.entry.focus_force()

    def refresh(self):
        """Show what Credential Manager holds now."""
        stored = credentials.read(self.target)
        self.stored = stored is not None
        if stored:
            when = f'{stored.saved.day} {stored.saved:%b %Y, %H:%M}'
            self.chip.configure(text=f'●  Stored, ends in …{stored.secret[-4:]}  ·  saved {when}', fg=OK, bg=OK_WASH)
            self.hint.configure(text='Paste a new key to replace it. Keys are at ')
        else:
            self.chip.configure(text='●  No key yet: until you add one, MWB writes with the local model',
                                fg=AMBER, bg=AMBER_WASH)
            self.hint.configure(text='Paste it with Ctrl+V. Get one at ')
        self._buttons()

    def _buttons(self):
        on, off = ['!disabled'], ['disabled']
        self.check_btn.state(off if self.busy else on)
        self.save_btn.state(off if self.busy else on)
        self.remove_btn.state(off if self.busy or not self.stored else on)

    def _say(self, text, colour):
        self.result.configure(text=text, fg=colour)

    def check(self):
        key = clean_key(self.key.get())
        if not key:
            stored = credentials.read(self.target)
            if not stored:
                return self._say('Paste a key in the box first.', AMBER)
            key = stored.secret
        self._run(key, save=False)

    def save(self):
        key = clean_key(self.key.get())
        if not key:
            return self._say('Paste your key in the box first.', AMBER)
        self._run(key, save=True)

    def _run(self, key, save):
        if self.busy:
            return
        self.busy = True
        self._buttons()
        self._say(f'Checking the key with {self.p.label}…', INK_3)
        threading.Thread(target=lambda: self.done.put((client.check_key(self.p, key), key, save)), daemon=True).start()
        self.root.after(100, self._finish)

    def _finish(self):
        try:
            r, key, save = self.done.get_nowait()
        except queue.Empty:
            self.root.after(100, self._finish)
            return
        self.busy = False
        self._buttons()
        name = self.p.label
        if r.ok:
            model = (f'and {self.p.model} is available' if self.p.model in r.models
                     else f"but {self.p.model} isn't in its model list")
            if save:
                self._store(key)
            self._say(f'✓  {"Saved. " if save else ""}{name} accepted the key in {r.seconds:.2f} s, {model}.', OK)
        elif r.kind == 'rejected':
            prefix = self.p.key_prefix
            hint = f' {name} keys start with {prefix}.' if prefix and not key.startswith(prefix) else ''
            self._say(f'✗  {name} rejected this key ({r.detail}).{hint}{" Nothing was saved." if save else ""}', SIGNAL)
        else:
            why = WHY_NOT[r.kind].format(host=self.host)
            if save and messagebox.askyesno("Couldn't check the key", f'{why}\n\n{r.detail}\n\nSave the key anyway? '
                                            'You can check it later with "Check key".', parent=self.root):
                self._store(key)
                self._say(f'Saved without a check. {why}', AMBER)
            else:
                self._say(f'✗  {why} ({r.detail})', SIGNAL)

    def _store(self, key):
        credentials.write(self.target, key, user=self.p.id, comment=f'MWB: {self.p.label} API key')
        self.key.set('')
        self.show.set(False)
        self.entry.configure(show='•')
        self.refresh()

    def remove(self):
        if messagebox.askyesno(f'Remove the {self.p.label} key?',
                               'MWB will write with the local model until you add a key again.',
                               icon='warning', parent=self.root):
            credentials.delete(self.target)
            self.refresh()
            self._say('Removed from Credential Manager.', INK_2)

    def _crash(self, kind, value, tb):
        self.busy = False
        self._buttons()
        messagebox.showerror('MWB', f'Something went wrong: {kind.__name__}: {value}', parent=self.root)


def main():
    _prepare_process()
    root = tk.Tk()
    ApiKeyWindow(root).activate()
    root.mainloop()


if __name__ == '__main__':
    main()
