"""The skills you call with a key (design §9.2, §9.4, §9.5, §9.7): explain an email or draft a reply, explain or
write code, rewrite the selection by voice, and answer questions. Each shows a result card near the mouse with the
text streaming in. Selected text is copied with your clipboard put back afterwards.

Rules from §15: MWB never sends email (a draft opens for you to edit), never runs code a model wrote, and treats the
text of mail and code as data, not instructions."""
import datetime, logging, os, re, subprocess, tempfile, threading, time

from mwb import insert, winapi
from mwb.collectors import outlook
from mwb.collectors.selection import copy_selection
from mwb.llm import prompts
from mwb.skills import answer, dates

log = logging.getLogger('mwb.assist')
WAKE = re.compile(r'^\s*(?:m\s*\.?\s*w\s*\.?\s*b\s*\.?|em double ?you bee|mwb)[\s,.:!?-]+', re.I)
FENCE = re.compile(r'```[a-zA-Z0-9+#-]*\n(.*?)```', re.S)
LANGS = {'.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'TypeScript', '.jsx': 'JavaScript',
         '.java': 'Java', '.kt': 'Kotlin', '.cs': 'C#', '.cpp': 'C++', '.c': 'C', '.go': 'Go', '.rs': 'Rust',
         '.sql': 'SQL', '.sh': 'shell', '.ps1': 'PowerShell', '.rb': 'Ruby', '.php': 'PHP', '.html': 'HTML',
         '.css': 'CSS', '.yaml': 'YAML', '.yml': 'YAML', '.json': 'JSON', '.xml': 'XML', '.scala': 'Scala'}
FOLLOW_UP_S = 30


def _title_of_foreground():
    hwnd = winapi.user32.GetForegroundWindow()
    buf = __import__('ctypes').create_unicode_buffer(300)
    winapi.user32.GetWindowTextW(hwnd, buf, 300)
    return buf.value


def language_of(title):
    """VS Code and most editors put the file name first: "main.js - AI-App - Visual Studio Code"."""
    m = re.search(r'(\.[A-Za-z0-9]+)\b', title.split(' - ')[0] if title else '')
    return LANGS.get(m.group(1).lower(), 'the') if m else 'the'


class Assist:
    def __init__(self, cfg, router, cards, ui, store):
        self.cfg, self.router, self.cards, self.ui, self.store = cfg, router, cards, ui, store
        self.a = cfg['assist']
        self.conversation, self.last_answer_at = [], 0.0
        self.calendar = None                # tests: a function returning calendar items

    def _thread(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True, name=f'assist-{fn.__name__}').start()

    def _restore(self, text):
        """Put text where the cursor is (the card never took the focus, so the selection is still there)."""
        self._thread(lambda: insert.insert(text, self.cfg['dictation']['restore_clipboard_ms']))

    def _copy(self, text):
        winapi.clipboard_set(text, private=True)

    # ---- write or answer (§9.7) ------------------------------------------------------------------------------

    def decide(self, text, app, text_box):
        """('answer', question) or ('write', text) for what you just said."""
        mode = self.a['talk_mode']
        if mode == 'always-write':
            return 'write', text
        m = WAKE.match(text)
        if m:
            question = text[m.end():].strip()
            return ('answer', question[:1].upper() + question[1:]) if question else ('write', text)
        if mode == 'always-answer':
            return 'answer', text
        if time.monotonic() - self.last_answer_at < FOLLOW_UP_S and self.cards.card_open:
            return 'answer', text                       # a follow-up while the answer is still on screen
        if app.lower() in {a.lower() for a in self.a['always_write_in']}:
            return 'write', text
        return ('answer', text) if text_box is False else ('write', text)

    def answer(self, question):
        self._thread(self._answer, question)

    def _answer(self, question):
        follow = time.monotonic() - self.last_answer_at < FOLLOW_UP_S and self.conversation
        if not follow:
            self.cards.close_cards()
            self.conversation = []
        card = self.cards.result('MWB', question[:90])
        facts, tags = answer.gather(question, self.store, self.cfg['meetings']['outlook'], self.calendar)
        now = datetime.datetime.now()
        prompt = prompts.ANSWER.format(today=f'{now:%A %d %B %Y}', now=f'{now:%H:%M}',
                                       facts_rule=prompts.FACTS_RULE if facts else '',
                                       question=question, facts=('Facts:\n' + facts) if facts else '')
        messages = [prompts.system()] + self.conversation + [prompts.user(prompt)]
        r = self.router.chat('answer', messages, 600, temperature=0.3, on_text=card.append)
        if not r.ok:
            card.set_text(f"Couldn't answer: {r.error}")
            return
        text, removed = answer.check_citations(r.text, tags)
        if removed:
            text += f'\n\n({removed} citation{"s" if removed > 1 else ""} removed: not found in your data.)'
        card.set_text(text)
        card.set_note(f'{question[:80]}  ·  {r.route}, {r.seconds:.1f} s')
        clean = re.sub(r'\s*\[[^\]]+\]', '', text)
        card.set_buttons([('Copy', lambda: self._copy(clean)), ('Insert', lambda: self._restore(clean))])
        self.conversation += [prompts.user(question), {'role': 'assistant', 'content': r.text}]
        self.conversation = self.conversation[-6:]
        self.last_answer_at = time.monotonic()

    # ---- email (§9.4) ----------------------------------------------------------------------------------------

    def _email_text(self):
        text = copy_selection().strip()
        if text:
            return text, False
        if winapi.foreground_app()[1].lower() == 'outlook.exe':
            mail = outlook.current_mail()
            if mail:
                subject, sender, body = mail
                return f'From: {sender}\nSubject: {subject}\n\n{body}', True
        return '', False

    def email_explain(self):
        self._thread(self._email_explain)

    def _email_explain(self):
        text, _ = self._email_text()
        card = self.cards.result('Email', 'Reading the email…')
        if not text:
            card.set_text('Select the email\'s text first (or open it in classic Outlook), then press the keys again.')
            return
        today = datetime.date.today()
        r = self.router.chat('email', [prompts.system(), prompts.user(prompts.EMAIL_EXPLAIN.format(
            today=f'{today:%A %d %B %Y}', email=text[:8000]))], 700, temperature=0.2, json_mode=True)
        d = r.json() if r.ok else None
        if not isinstance(d, dict):
            card.set_text(f"Couldn't explain it: {r.error or 'the answer was not in the expected form'}")
            return
        out = [str(d.get('summary', '')).strip(), '']
        if d.get('they_want'):
            out += ['They want:'] + [f'• {w}' for w in d['they_want']] + ['']
        if d.get('deadlines'):
            out.append('Deadlines:')
            for x in d['deadlines']:
                if isinstance(x, dict):
                    when = dates.resolve(str(x.get('when', '')), today)          # worked out by code
                    out.append(f'• {x.get("what", "")}: {x.get("when", "")}'
                               + (f' → {dates.pretty(when)}' if when else ''))
            out.append('')
        if d.get('people'):
            out += ['People: ' + ', '.join(map(str, d['people'])), '']
        options = [str(o) for o in d.get('reply_options') or []][:3]
        if options:
            out += ['Reply ideas:'] + [f'{i}. {o}' for i, o in enumerate(options, 1)]
        card.set_text('\n'.join(out).strip())
        card.set_note(f'{r.route}, {r.seconds:.1f} s. Hold the same keys and speak to draft a reply.')
        card.set_buttons([('Copy', lambda: self._copy('\n'.join(out).strip()))])

    def email_draft(self, gist):
        self._thread(self._email_draft, gist)

    def _email_draft(self, gist):
        text, from_outlook = self._email_text()
        card = self.cards.result('Reply draft', f'"{gist[:80]}"')
        if not gist.strip():
            card.set_text('I didn\'t hear what the reply should say. Hold the keys and speak while holding.')
            return
        r = self.router.chat('email', [prompts.system(), prompts.user(prompts.EMAIL_DRAFT.format(
            gist=gist, style=self.a['style'], words=150, email=text[:6000] or '(no email selected)'))], 500,
            temperature=0.4, on_text=card.append)
        if not r.ok:
            card.set_text(f"Couldn't write the draft: {r.error}")
            return
        draft = r.text.strip()
        card.set_text(draft)
        buttons = [('Copy', lambda: self._copy(draft))]
        if from_outlook:
            buttons.append(('Open as Outlook draft', lambda: self._thread(outlook.open_reply_draft, draft)))
        buttons.append(('Insert', lambda: self._restore(draft)))
        card.set_buttons(buttons)
        card.set_note(f'{r.route}, {r.seconds:.1f} s. MWB never sends: you check it and send it yourself.')

    # ---- code (§9.5) -----------------------------------------------------------------------------------------

    def code_explain(self):
        self._thread(self._code_explain)

    def _code_explain(self):
        lang = language_of(_title_of_foreground())
        code = copy_selection()
        card = self.cards.result('Code', 'Reading the code…')
        if not code.strip():
            card.set_text('Select some code first, then press the keys again.')
            return
        r = self.router.chat('code', [prompts.system(), prompts.user(prompts.CODE_EXPLAIN.format(
            language=lang if lang != 'the' else '', code=code[:12000]))], 1800, temperature=0.2, on_text=card.append)
        if not r.ok:
            card.set_text(f"Couldn't explain it: {r.error}")
            return
        card.set_text(r.text)
        better = FENCE.search(r.text.split('## Better version')[-1])
        buttons = [('Copy', lambda: self._copy(r.text))]
        if better:
            new = better.group(1).rstrip('\n') + ('\n' if code.endswith('\n') else '')
            buttons += [('Open diff in VS Code', lambda: self._thread(self._diff, code, new)),
                        ('Replace selection', lambda: self._restore(new))]
        card.set_buttons(buttons)
        card.set_note(f'{r.route}, {r.seconds:.1f} s. Check it before you use it.')

    def _diff(self, old, new):
        folder = tempfile.mkdtemp(prefix='mwb-diff-')
        a, b = os.path.join(folder, 'selected'), os.path.join(folder, 'suggested')
        for path, text in ((a, old), (b, new)):
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
        try:
            subprocess.Popen(['code', '--diff', a, b], shell=True, creationflags=0x08000000)
        except OSError:
            log.info('VS Code not found for the diff')

    def code_write(self, request):
        self._thread(self._code_write, request)

    def _code_write(self, request):
        lang = language_of(_title_of_foreground())
        if not request.strip():
            return
        self.ui.set_state('working')
        r = self.router.chat('code', [prompts.system(), prompts.user(prompts.CODE_WRITE.format(
            language=lang if lang != 'the' else 'the right', request=request))], 1500, temperature=0.2)
        block = FENCE.search(r.text) if r.ok else None
        if not block:
            self.ui.set_state('idle')
            card = self.cards.result('Code', request[:80])
            card.set_text(f"Couldn't write it: {r.error or 'no code in the answer'}")
            return
        insert.insert(block.group(1).rstrip('\n'), self.cfg['dictation']['restore_clipboard_ms'])
        self.ui.set_state('done')

    # ---- rewrite by voice (§9.2) -----------------------------------------------------------------------------

    def rewrite(self, instruction):
        self._thread(self._rewrite, instruction)

    def _rewrite(self, instruction):
        text = copy_selection()
        card = self.cards.result('Rewrite', f'"{instruction[:80]}"')
        if not text.strip():
            card.set_text('Select the text to change first, then hold the keys and say how.')
            return
        if not instruction.strip():
            card.set_text("I didn't hear how to change it. Hold the keys and speak while holding.")
            return
        r = self.router.chat('rewrite', [prompts.system(), prompts.user(prompts.REWRITE.format(
            instruction=instruction, text=text[:8000]))], 1200, temperature=0.4, on_text=card.append)
        if not r.ok:
            card.set_text(f"Couldn't rewrite it: {r.error}")
            return
        new = r.text.strip()
        card.set_text(new)
        card.set_buttons([('Copy', lambda: self._copy(new)), ('Replace', lambda: self._restore(new))])
        card.set_note(f'{r.route}, {r.seconds:.1f} s')
