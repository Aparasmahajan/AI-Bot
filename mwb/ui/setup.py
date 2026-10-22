"""The setup screen (design §12.5, Figure 12.3): what MWB found on this laptop, what it measured, and how hard it
should work here. It opens by itself the first time MWB runs on a machine (a new fingerprint, or a memory upgrade),
and from Settings → Performance or the tray at any time. The choice is saved for this machine only, in
%LOCALAPPDATA%\\MWB\\machine\\<fingerprint>.toml, and the running core picks it up within 30 seconds.

MWB never downloads a model from here. Missing models are listed, so you can decide.

  .venv\\Scripts\\pythonw.exe -m mwb.ui.setup"""
import queue, subprocess, sys, threading, tkinter as tk
from tkinter import ttk

from mwb import config, credentials, machine
from mwb.llm.providers import GROQ
from mwb.ui import style

DESCRIBE = {'E1': 'Battery saver. 2 threads, nothing kept warm; meetings are transcribed after the call.',
            'E2': 'Balanced. Speech stays warm while you are active; meetings live on mains power.',
            'E3': 'High. More threads, speech kept warm longer, the larger local model for code and the journal.',
            'E4': 'Max. Every core, everything kept warm.'}
SAME = 'Same as above'


class SetupWindow:
    def __init__(self, root):
        self.root = root
        self.px = px = style.apply(root, 'MWB setup · this laptop')
        root.resizable(False, False)
        root.bind('<Escape>', lambda e: root.destroy())
        self.cfg = config.load()
        self.results = queue.Queue()
        self.hw = self.fp = self.data = None
        self.level = tk.StringVar(value='E2')
        self.auto = tk.BooleanVar(value=True)
        self.battery = tk.BooleanVar(value=True)
        self.features = {f: tk.StringVar(value=SAME) for f in machine.FEATURES}
        self.body = ttk.Frame(root, padding=(px(24), px(20), px(24), px(18)))
        self.body.pack(fill='both', expand=True)
        ttk.Label(self.body, text='How hard should MWB work on this laptop?', style='Title.TLabel').pack(anchor='w')
        self.wait = ttk.Label(self.body, text='Looking at this laptop…', style='Sub.TLabel')
        self.wait.pack(anchor='w', pady=(px(10), px(40)))
        threading.Thread(target=self._probe, daemon=True).start()
        root.after(100, self._poll)

    # ---- in the background -------------------------------------------------------------------------------------

    def _probe(self):
        try:
            hw = machine.probe()
        except RuntimeError as e:
            self.results.put(('error', str(e)))
            return
        self.results.put(('hardware', hw))
        if credentials.read(credentials.api_key_target(GROQ.id)):
            from mwb.llm.router import Router
            r = Router(self.cfg).chat('quick', [{'role': 'user', 'content': 'Reply with the word OK.'}], 64, 0)
            if r.ok and r.first_word_s:
                self.results.put(('api', round(r.first_word_s, 2)))

    def _poll(self):
        try:
            while True:
                kind, value = self.results.get_nowait()
                if kind == 'error':
                    self.wait.configure(text=f'MWB could not look at this laptop: {value}.', style='Bad.TLabel')
                elif kind == 'hardware':
                    self._show(value)
                elif kind == 'api' and self.data is not None:
                    self.data.setdefault('calibration', {})['api_first_words_s'] = value
                    self.tested.configure(text=self._tested())
        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    # ---- the screen --------------------------------------------------------------------------------------------

    def _tested(self):
        c = self.data.get('calibration', {})
        bits = []
        if c.get('speech_5s_phrase_s'):
            bits.append(f'speech {c["speech_5s_phrase_s"]} s for a 5 s phrase')
        bits.append(f'API first words {c["api_first_words_s"]} s' if c.get('api_first_words_s') else
                    'API: measuring…' if credentials.read(credentials.api_key_target(GROQ.id)) else 'no API key yet')
        if c.get('local_tokens_per_s'):
            bits.append(f'local fallback {c["local_tokens_per_s"]} tokens/s')
        return ' · '.join(bits)

    def _show(self, hw):
        px = self.px
        self.hw, self.fp = hw, machine.fingerprint(hw)
        self.data = machine.load(self.fp) or machine.new(hw, self.fp, self.cfg.get('effort_preference', 'suggested'))
        self.data['hardware'] = {**self.data.get('hardware', {}), **hw}
        self.profile = machine.profile_of(hw)
        self.data['profile'] = self.profile
        choice = machine.effort_of(self.data)
        suggest = machine.suggested(self.profile, self.cfg.get('effort_preference', 'suggested'))
        self.level.set(choice['highest'] if choice['chosen'] else suggest)
        self.auto.set(choice['mode'] == 'auto')
        self.battery.set(choice['on_battery'] == 'lower')
        for f, v in choice['by_feature'].items():
            self.features[f].set(f'{v} {machine.NAMES[v]}')
        self.wait.destroy()
        b = self.body

        facts = ttk.Frame(b, style='Paper.TFrame', padding=(px(14), px(10)))
        facts.pack(fill='x', pady=(px(12), px(14)))
        sticks = f'{hw["memory_sticks"]} stick' + ('s' if hw['memory_sticks'] != 1 else '')
        gpu = ', '.join(g.replace('(R)', '').replace('  ', ' ') for g in hw['gpu']) or 'no GPU found'
        rows = (('FOUND', f'{hw["cpu"].replace("(R)", "").replace("(TM)", "")} · {hw["ram_gb"]} GB, {sticks} · '
                          f'{gpu} · {"an NPU" if hw["npu"] else "no NPU"}'),
                ('TESTED', self._tested()),
                ('SUGGESTS', f'{self.profile.capitalize()} profile · {machine.NAMES[suggest]} effort ({suggest})'))
        for i, (head, text) in enumerate(rows):
            ttk.Label(facts, text=head, style='PaperHead.TLabel').grid(row=i, column=0, sticky='nw', padx=(0, px(12)))
            lab = ttk.Label(facts, text=text, style='Paper.TLabel', wraplength=px(520), justify='left')
            lab.grid(row=i, column=1, sticky='w', pady=px(1))
            if head == 'TESTED':
                self.tested = lab

        for lvl in machine.LEVELS:
            note = machine.why_not(lvl, self.profile)
            ok = lvl in machine.available(self.profile)
            row = ttk.Frame(b)
            row.pack(fill='x', pady=px(2))
            text = f'{lvl}  {DESCRIBE[lvl]}' + ('  Suggested for this laptop.' if lvl == suggest else '')
            ttk.Radiobutton(row, text=text, value=lvl, variable=self.level, state='normal' if ok else 'disabled',
                            command=self._levels_changed).pack(side='left')
            if note:
                ttk.Label(row, text=note, style='Warn.TLabel' if ok else 'Small.TLabel').pack(side='left',
                                                                                               padx=(px(8), 0))
        ttk.Checkbutton(b, text='Adjust automatically between Battery saver and my choice: lower when the laptop is '
                                'busy, back up when it is calm.', variable=self.auto,
                        command=self._levels_changed).pack(anchor='w', pady=(px(10), 0))
        self.battery_box = ttk.Checkbutton(b, text='On battery, go one level lower (two below 30 % charge).',
                                           variable=self.battery)
        self.battery_box.pack(anchor='w', padx=(px(24), 0))

        self.more = ttk.Button(b, command=self._toggle_more)
        self.more.pack(anchor='w', pady=(px(10), 0))
        self.grid = grid = ttk.Frame(b)
        self.models_head = None
        self.combos = []
        for i, (f, name) in enumerate(machine.FEATURES.items()):
            ttk.Label(grid, text=name, style='Sub.TLabel').grid(row=i // 2, column=(i % 2) * 2, sticky='w',
                                                                  padx=(0, px(8)), pady=px(2))
            c = ttk.Combobox(grid, textvariable=self.features[f], state='readonly', width=18)
            c.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky='w', padx=(0, px(24)), pady=px(2))
            self.combos.append(c)

        self.models_head = ttk.Label(b, text='Models on this laptop', style='Head.TLabel')
        self.models_head.pack(anchor='w', pady=(px(12), px(2)))
        self.models = ttk.Frame(b)
        self.models.pack(anchor='w', fill='x')
        key = ttk.Frame(b)
        key.pack(anchor='w', fill='x', pady=(px(8), 0))
        has_key = credentials.read(credentials.api_key_target(GROQ.id)) is not None
        ttk.Label(key, text='Writing uses your Groq key: stored.' if has_key else
                  'Writing uses an API key, and none is stored yet.', style='Good.TLabel' if has_key else
                  'Warn.TLabel').pack(side='left')
        if not has_key:
            ttk.Button(key, text='Add API key…', command=self._api_key).pack(side='left', padx=(px(10), 0))

        ttk.Separator(b).pack(fill='x', pady=(px(16), px(12)))
        buttons = ttk.Frame(b)
        buttons.pack(fill='x')
        self.saved = ttk.Label(buttons, text='Saved for this laptop only.' if choice['chosen'] else
                               'Nothing is saved until you press Save.', style='Small.TLabel')
        self.saved.pack(side='left')
        ttk.Button(buttons, text='Save', style='Primary.TButton', command=self.save).pack(side='right')
        ttk.Button(buttons, text='Close', command=self.root.destroy).pack(side='right', padx=(0, px(8)))
        self.show_more = bool(choice['by_feature'])
        self._toggle_more(flip=False)
        self._levels_changed()
        style.place(self.root)

    def _toggle_more(self, flip=True):
        """The per-feature levels fold away, so the screen fits a laptop display."""
        self.show_more = not self.show_more if flip else self.show_more
        self.more.configure(text=('▾' if self.show_more else '▸') + '  A different level for one feature')
        if self.show_more:
            self.grid.pack(anchor='w', pady=(self.px(4), 0), before=self.models_head)
        else:
            self.grid.pack_forget()
        if flip:
            style.place(self.root)

    def _levels_changed(self):
        top = self.level.get()
        names = [SAME] + [f'{l} {machine.NAMES[l]}' for l in machine.available(self.profile)]
        for c in self.combos:
            c.configure(values=names)
        self.battery_box.configure(state='normal' if self.auto.get() else 'disabled')
        for w in self.models.winfo_children():
            w.destroy()
        levels = [top] + [v.get().split()[0] for v in self.features.values() if v.get() != SAME]
        rows = machine.models_needed(self.cfg, levels)
        missing = [(what, path) for what, path, found in rows if not found]
        if not missing:
            ttk.Label(self.models, text=f'✓  All {len(rows)} are here: ' + ', '.join(w.split(' (')[1].rstrip(')')
                                                                                for w, _, _ in rows) + '.',
                      style='Good.TLabel', wraplength=self.px(560)).pack(anchor='w')
        for what, path in missing:
            ttk.Label(self.models, text=f'✗  {what}: not found at {path}', style='Bad.TLabel',
                      wraplength=self.px(560)).pack(anchor='w')
        if missing:
            ttk.Label(self.models, text='MWB never downloads a model by itself. Ask before getting a missing one; '
                                        'until then that feature waits or uses the API.', style='Small.TLabel',
                      wraplength=self.px(560)).pack(anchor='w', pady=(self.px(2), 0))

    def _api_key(self):
        subprocess.Popen([sys.executable, '-m', 'mwb.ui.api_key'], cwd=str(config.HERE.parents[1]))

    def save(self):
        if self.data is None:
            return
        by = {f: v.get().split()[0] for f, v in self.features.items() if v.get() != SAME}
        self.data['effort'] = {'mode': 'auto' if self.auto.get() else 'fixed', 'lowest': 'E1',
                               'highest': self.level.get(), 'on_battery': 'lower' if self.battery.get() else 'keep',
                               'chosen': True, 'by_feature': by}
        machine.save(self.fp, self.data)
        self.saved.configure(text='Saved for this laptop only. MWB uses it within 30 seconds.', style='Good.TLabel')
        self.root.after(1200, self.root.destroy)


def main():
    style.prepare()
    root = tk.Tk()
    SetupWindow(root)
    style.place(root)
    root.mainloop()


if __name__ == '__main__':
    main()
