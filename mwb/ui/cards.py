"""Small Tkinter cards (design §8.3, §13.2): "Record this call?" and the transcript file picker. They run on a Tk
thread of their own, started on first use, so the core's loop never waits on them. A card never takes the keyboard
focus, so whatever you type in your call app keeps going there; you answer with the mouse.

Results (answers, drafts, rewrites) are not Tk windows: they open in the indicator's place, above the pill
(ui/indicator.py), the way Wispr Flow keeps everything in its bar."""
import ctypes, logging, queue, threading

log = logging.getLogger('mwb.cards')
SHEET, PAPER, INK, INK_2, INK_3, RULE = '#FFFFFF', '#F3F5F8', '#0E1726', '#465267', '#66738A', '#D3D9E3'
COBALT, SIGNAL, AMBER = '#2148C9', '#CF3F0A', '#946000'
FONT = 'Segoe UI'
ASK_TIMEOUT_S = 120             # no answer means "not this one"


class Cards:
    def __init__(self, results):
        self.results = results              # the indicator, which shows result panels
        self.jobs = queue.Queue()
        self.thread = None
        self.root = None

    def _ensure(self):
        if self.thread and self.thread.is_alive():
            return
        ready = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(ready,), daemon=True, name='cards')
        self.thread.start()
        ready.wait(10)

    def _run(self, ready):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.root = tk.Tk()
        self.root.withdraw()
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Card.TFrame', background=SHEET)
        style.configure('Card.TLabel', background=SHEET, foreground=INK, font=(FONT, 10))
        style.configure('Title.TLabel', background=SHEET, foreground=INK, font=(FONT, 11, 'bold'))
        style.configure('Note.TLabel', background=SHEET, foreground=INK_3, font=(FONT, 9))
        style.configure('Go.TButton', background=COBALT, foreground='white', font=(FONT, 10, 'bold'), padding=(12, 5))
        style.map('Go.TButton', background=[('active', '#1A3AA3')])
        style.configure('Plain.TButton', background=PAPER, foreground=INK, font=(FONT, 10), padding=(10, 5))
        ready.set()
        self._poll()
        self.root.mainloop()

    def _poll(self):
        try:
            while True:
                self.jobs.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def run(self, fn):
        self._ensure()
        self.jobs.put(fn)

    # ---- "Record this call?" ---------------------------------------------------------------------------------

    def ask_record(self, call, answer, personal_note=''):
        """answer('record' | 'skip' | 'never') is called exactly once, from the cards thread."""
        self.run(lambda: self._ask(call, answer, personal_note))

    def _ask(self, call, answer, personal_note):
        tk, ttk = self.tk, self.ttk
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.configure(background=RULE)
        win.attributes('-topmost', True)
        done = [False]

        def reply(choice):
            if done[0]:
                return
            done[0] = True
            win.destroy()
            try:
                answer(choice)
            except Exception:
                log.exception('answer failed')

        body = ttk.Frame(win, style='Card.TFrame', padding=(16, 12, 16, 12))
        body.pack(padx=1, pady=1)
        ttk.Label(body, text=f'{call.name} is using the microphone', style='Title.TLabel').pack(anchor='w')
        if call.title:
            ttk.Label(body, text=call.title[:70], style='Card.TLabel').pack(anchor='w', pady=(2, 0))
        ttk.Label(body, text='Record this call? MWB transcribes it on this laptop and keeps no audio.',
                  style='Card.TLabel', wraplength=360, justify='left').pack(anchor='w', pady=(6, 0))
        if personal_note:
            ttk.Label(body, text=personal_note, style='Note.TLabel', wraplength=360).pack(anchor='w', pady=(4, 0))
        row = ttk.Frame(body, style='Card.TFrame')
        row.pack(anchor='e', pady=(12, 0))
        ttk.Button(row, text=f'Never for {call.name[:20]}', style='Plain.TButton',
                   command=lambda: reply('never')).pack(side='left', padx=(0, 6))
        ttk.Button(row, text='Not this one', style='Plain.TButton', command=lambda: reply('skip')).pack(side='left',
                                                                                                       padx=(0, 6))
        ttk.Button(row, text='Record', style='Go.TButton', command=lambda: reply('record')).pack(side='left')
        win.update_idletasks()
        # bottom right, above the taskbar: the work area, from Windows
        rect = (ctypes.c_long * 4)()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, rect, 0)          # SPI_GETWORKAREA
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f'+{rect[2] - w - 16}+{rect[3] - h - 16}')
        hwnd = int(win.wm_frame(), 16)
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x08000000 | 0x80)    # no activate, no taskbar button
        # not win.deiconify(): Tk would activate the window and take the focus from your app
        ctypes.windll.user32.ShowWindow(hwnd, 4)                                 # SW_SHOWNOACTIVATE
        win.after(ASK_TIMEOUT_S * 1000, lambda: reply('skip'))

    # ---- results (§8.3, §9.2-§9.7) ----------------------------------------------------------------------------

    def result(self, title, note=''):
        """A panel above the indicator whose text streams in. Returns a ResultPanel; use it from any thread."""
        return self.results.result(title, note)

    @property
    def card_open(self):
        return self.results.panel_open

    def close_cards(self):
        self.results.close_panel()

    # ---- import ----------------------------------------------------------------------------------------------

    def pick_transcript(self, chosen):
        """chosen(path or None), from the cards thread."""
        def pick():
            from tkinter import filedialog
            self.root.attributes('-topmost', True)
            path = filedialog.askopenfilename(
                parent=self.root, title='Import a meeting transcript',
                filetypes=[('Transcripts', '*.vtt *.docx *.txt'), ('All files', '*.*')])
            chosen(path or None)
        self.run(pick)

    def close(self):
        if self.root:
            self.run(self.root.quit)

