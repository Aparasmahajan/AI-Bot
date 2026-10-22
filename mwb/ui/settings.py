"""The Settings window (Phase 5): the common settings from mwb\\config\\default.toml, in tabs. Saving writes only the
settings you changed into %APPDATA%\\MWB\\config.toml, keeping your comments, and MWB starts again by itself to use
them as soon as nothing is in progress. Shortcuts and rarer settings stay in the settings file, which a button opens.
How hard MWB works on this laptop is on the setup screen (Performance tab), because it belongs to the machine.

  .venv\\Scripts\\pythonw.exe -m mwb.ui.settings"""
import os, re, subprocess, sys, tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from mwb import config, machine
from mwb.ui import art, style

SKILLS = {'answer': 'Answers', 'email': 'Email', 'code': 'Code', 'rewrite': 'Rewrite', 'notes': 'Meeting notes',
          'label': 'Meeting labels', 'journal': 'Journal', 'email-style': 'Learning your email style'}
# (tab, section, key, label, kind, options, help)
FIELDS = [
    ('General', 'triggers', 'talk', 'Talk by double-tapping Caps Lock', 'choice',
     {'double-tap caps lock': 'On', 'off': 'Off'}, 'Push-to-talk always works too.'),
    ('General', 'triggers', 'finish_pause_s', 'Finish after a pause of (seconds)', 'float', (0.8, 5.0), ''),
    ('General', 'assist', 'talk_mode', 'When you talk', 'choice',
     {'decide': 'Write in text boxes, answer elsewhere', 'always-write': 'Always write',
      'always-answer': 'Always answer'}, ''),
    ('General', 'assist', 'wake_word', 'Wake word for questions', 'text', None, '"MWB, what\'s my next meeting?"'),
    ('General', 'assist', 'my_name', 'Your name in action items', 'text', None, 'Empty: "You".'),
    ('Indicator', 'indicator', 'skin', 'Skin', 'skin', None, ''),
    ('Indicator', 'indicator', 'show', 'Show the indicator', 'bool', None, 'Double-tap Alt shows or hides it.'),
    ('Indicator', 'indicator', 'visible', 'When', 'choice', {'always': 'Always', 'while-active': 'Only while busy'}, ''),
    ('Indicator', 'indicator', 'size', 'Size', 'choice', {'small': 'Small', 'medium': 'Medium', 'large': 'Large'}, ''),
    ('Indicator', 'indicator', 'opacity', 'Opacity', 'float', (0.4, 1.0), ''),
    ('Indicator', 'indicator', 'live_words', 'Show your words as you speak', 'bool', None, ''),
    ('Indicator', 'indicator', 'hide_in_fullscreen', 'Hide over full-screen apps', 'bool', None, ''),
    ('Dictation', 'dictation', 'load_on_start', 'Load speech when MWB starts (if memory allows)', 'bool', None,
     'The first dictation is then quick.'),
    ('Dictation', 'dictation', 'trailing_space', 'Add a space after each dictation', 'bool', None, ''),
    ('Dictation', 'dictation', 'type_instead', 'Apps that get typed text instead of a paste', 'csv', None,
     'Program names, comma-separated, e.g. putty.exe'),
    ('Meetings', 'meetings', 'detect', 'Notice calls in any app', 'bool', None, ''),
    ('Meetings', 'meetings', 'ask_before_recording', 'Ask before recording', 'choice',
     {'first-week': 'In the first week', 'always': 'Always', 'never': 'Never'},
     'Personal apps such as WhatsApp always ask.'),
    ('Meetings', 'meetings', 'language', 'Meeting language', 'choice',
     {'auto': 'Find out (English, Hindi, Hinglish)', 'en': 'English', 'hi': 'Hindi'}, ''),
    ('Meetings', 'meetings', 'outlook', 'Meeting titles from classic Outlook', 'choice',
     {'start': 'Yes, and start Outlook if needed', 'if-running': 'Only if Outlook is open', 'off': 'No'}, ''),
    ('Meetings', 'meetings', 'keep_audio', 'Keep meeting audio', 'bool', None,
     'Off: each piece is deleted the moment it is transcribed.'),
    ('Journal', 'journal', 'time', 'Write the journal at (HH:MM)', 'time', None, 'Or press Ctrl+Alt+Shift+J.'),
    ('Journal', 'journal', 'folder', 'Journal folder', 'text', None, r'Empty: Documents\MWB\journal'),
    ('Journal', 'journal', 'repo_roots', 'Git repositories under', 'lines', None, 'One folder per line.'),
    ('Journal', 'journal', 'email', 'Sent mail in the journal', 'choice',
     {'off': 'No', 'classic-outlook': 'From classic Outlook (subjects and people only)'}, ''),
    ('Journal', 'journal', 'manager_email', 'Your manager\'s email, for the draft', 'text', None, 'MWB never sends.'),
    ('Journal', 'journal', 'denylist', 'Apps and titles kept private', 'lines', None,
     'One pattern per line, e.g. *bank*. They count only as "Private".'),
    ('Language', 'llm', 'route', 'Language work goes to', 'choice',
     {'api': 'The API first (Groq), the laptop if it fails', 'local': 'This laptop only'}, ''),
    ('Language', 'llm', 'local_only', 'Never send these to the API', 'skills', None,
     'Their text stays on this laptop; they use the local model.'),
]


class SettingsWindow:
    def __init__(self, root):
        self.root = root
        self.px = px = style.apply(root, 'MWB · Settings')
        root.bind('<Escape>', lambda e: self.close())
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.cfg = config.load()
        self.vars, self.images = {}, []
        outer = ttk.Frame(root, padding=(px(18), px(16), px(18), px(14)))
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Settings', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text='Changes apply when you press Save: MWB starts again by itself once nothing is in '
                              'progress.', style='Sub.TLabel').pack(anchor='w', pady=(px(2), px(10)))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both', expand=True)
        self.tabs.enable_traversal()                # Ctrl+Tab and Ctrl+Shift+Tab move between tabs
        pages = {}
        for tab, section, key, label, kind, options, help_ in FIELDS:
            if tab not in pages:
                pages[tab] = ttk.Frame(self.tabs, padding=(px(16), px(12)))
                pages[tab].columnconfigure(1, weight=1)
                self.tabs.add(pages[tab], text=tab)
            self._field(pages[tab], section, key, label, kind, options, help_)
        self._performance()
        self.problem = ttk.Label(outer, text='', style='Bad.TLabel')
        self.problem.pack(anchor='w', pady=(px(8), 0))
        buttons = ttk.Frame(outer)
        buttons.pack(fill='x', pady=(px(6), 0))
        ttk.Button(buttons, text='Open the settings file', command=self.open_file).pack(side='left')
        ttk.Button(buttons, text='Save', style='Primary.TButton', command=self.save).pack(side='right')
        ttk.Button(buttons, text='Cancel', command=self.close).pack(side='right', padx=(0, px(8)))
        if self.cfg['_problem']:
            self.problem.configure(text=f'Your settings file has a mistake, so the defaults are shown: '
                                        f'{self.cfg["_problem"]}'[:200])

    def value(self, section, key):
        return self.cfg.get(section, {}).get(key)

    def _row(self, page, label, help_):
        r = page.grid_size()[1]
        ttk.Label(page, text=label, style='Sub.TLabel').grid(row=r, column=0, sticky='nw', padx=(0, self.px(14)),
                                                             pady=(self.px(6), 0))
        cell = ttk.Frame(page)
        cell.grid(row=r, column=1, sticky='we', pady=(self.px(4), 0))
        if help_:
            ttk.Label(page, text=help_, style='Small.TLabel').grid(row=r + 1, column=1, sticky='w')
        return cell

    def _field(self, page, section, key, label, kind, options, help_):
        px, v = self.px, self.value(section, key)
        cell = self._row(page, label, help_)
        if kind == 'bool':
            var = tk.BooleanVar(value=bool(v))
            ttk.Checkbutton(cell, variable=var).pack(anchor='w')
        elif kind == 'choice':
            var = tk.StringVar(value=options.get(v, v))
            ttk.Combobox(cell, textvariable=var, values=list(options.values()), state='readonly',
                         width=42).pack(anchor='w')
        elif kind in ('text', 'time', 'float'):
            var = tk.StringVar(value='' if v is None else str(v))
            ttk.Entry(cell, textvariable=var, width=44 if kind == 'text' else 10).pack(anchor='w')
        elif kind == 'csv':
            var = tk.StringVar(value=', '.join(v or []))
            ttk.Entry(cell, textvariable=var, width=44).pack(anchor='w')
        elif kind == 'lines':
            box = tk.Text(cell, width=48, height=3, font=(style.FONT, 10), relief='solid', bd=1,
                          highlightthickness=0, wrap='none')
            box.insert('1.0', '\n'.join(v or []))
            box.pack(anchor='w', fill='x')
            var = box
        elif kind == 'skills':
            var = {s: tk.BooleanVar(value=s in (v or [])) for s in SKILLS}
            for i, (s, name) in enumerate(SKILLS.items()):
                ttk.Checkbutton(cell, text=name, variable=var[s]).grid(row=i // 2, column=i % 2, sticky='w',
                                                                       padx=(0, px(16)))
        elif kind == 'skin':
            var = tk.StringVar(value=v if v in art.SKINS else 'capsule')
            grid = ttk.Frame(cell)
            grid.pack(anchor='w')
            for i, skin in enumerate(art.SKINS):
                img = art.preview(skin, scale=self.px(80) / 100)
                bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
                bg.alpha_composite(img)
                photo = ImageTk.PhotoImage(bg.convert('RGB'))
                self.images.append(photo)
                ttk.Radiobutton(grid, text=skin.capitalize(), image=photo, compound='top', value=skin,
                                variable=var).grid(row=i // 4, column=i % 4, padx=px(4), pady=px(2))
        self.vars[(section, key)] = (kind, options, var)

    def _performance(self):
        px = self.px
        page = ttk.Frame(self.tabs, padding=(px(16), px(12)))
        self.tabs.add(page, text='Performance')
        ttk.Label(page, text='How hard MWB works is set for this laptop only, on the setup screen: a level from '
                             'Battery saver to Max, whether it adjusts by itself, and a level per feature.',
                  style='Sub.TLabel', wraplength=px(520), justify='left').pack(anchor='w')
        summary = 'Not chosen yet on this laptop.'
        files = sorted(machine.FOLDER.glob('*.toml'), key=lambda p: p.stat().st_mtime) if machine.FOLDER.exists() \
            else []
        if files:
            data = machine.load(files[-1].stem)
            e = machine.effort_of(data)
            summary = (f'Now: {e["highest"]} {machine.NAMES[e["highest"]]}, '
                       f'{"adjusting by itself" if e["mode"] == "auto" else "fixed"}'
                       + (f'; {", ".join(f"{machine.FEATURES[f]} {v}" for f, v in e["by_feature"].items())}'
                          if e['by_feature'] else '') + '.')
        ttk.Label(page, text=summary, style='Small.TLabel').pack(anchor='w', pady=(px(8), px(8)))
        ttk.Button(page, text='Open the setup screen…', command=lambda: subprocess.Popen(
            [sys.executable, '-m', 'mwb.ui.setup'], cwd=str(config.HERE.parents[1]))).pack(anchor='w')

    # ---- saving ------------------------------------------------------------------------------------------------

    def read(self, section, key):
        """The field's value as TOML wants it. Raises ValueError with a plain reason."""
        kind, options, var = self.vars[(section, key)]
        if kind == 'bool':
            return var.get()
        if kind == 'choice':
            back = {label: value for value, label in options.items()}
            return back.get(var.get(), var.get())
        if kind == 'float':
            lo, hi = options
            x = float(var.get().replace(',', '.'))
            if not lo <= x <= hi:
                raise ValueError(f'between {lo} and {hi}')
            return round(x, 2)
        if kind == 'time':
            t = var.get().strip()
            if not re.fullmatch(r'([01]?\d|2[0-3]):[0-5]\d', t):
                raise ValueError('a time like 18:30')
            h, m = t.split(':')
            return f'{int(h):02d}:{m}'
        if kind == 'csv':
            return [x.strip() for x in var.get().split(',') if x.strip()]
        if kind == 'lines':
            return [x.strip() for x in var.get('1.0', 'end').splitlines() if x.strip()]
        if kind == 'skills':
            return [s for s, b in var.items() if b.get()]
        return var.get().strip()

    def changes(self):
        out, labels = {}, {(s, k): label for _, s, k, label, *_ in FIELDS}
        for (section, key) in self.vars:
            try:
                new = self.read(section, key)
            except ValueError as e:
                raise ValueError(f'{labels[(section, key)]}: please use {e}.')
            if new != self.value(section, key):
                out.setdefault(section, {})[key] = new
        return out

    def save(self):
        try:
            changes = self.changes()
        except ValueError as e:
            self.problem.configure(text=str(e))
            return
        if not changes:
            self.root.destroy()
            return
        try:
            config.save_user(changes)
        except Exception as e:
            self.problem.configure(text=f'Not saved: {e}'[:200])
            return
        n = sum(len(v) for v in changes.values())
        self.problem.configure(text=f'Saved {n} change{"s" if n != 1 else ""}. MWB starts again by itself to use '
                                    f'them.', style='Good.TLabel')
        self.root.after(1400, self.root.destroy)

    def close(self):
        try:
            pending = self.changes()
        except ValueError:
            pending = True
        if pending and not messagebox.askyesno('MWB', 'Close without saving your changes?', parent=self.root):
            return
        self.root.destroy()

    def open_file(self):
        if not config.USER_FILE.exists():
            config.save_user({})
        os.startfile(config.USER_FILE)


def main():
    style.prepare()
    root = tk.Tk()
    SettingsWindow(root)
    style.place(root)
    root.mainloop()


if __name__ == '__main__':
    main()
