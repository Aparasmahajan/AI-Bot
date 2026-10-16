"""The end-of-day journal (design §9.6, JNL-1 to JNL-4 and JNL-6), written at 18:30 or when you ask.

Facts come from code: commits from git, meetings with their notes and labels, time per project from the active
window, dictation counts, voice notes, sent mail (subjects and people only) and tomorrow's calendar. Code renders
them as tables and lists. The model writes only the prose: a summary, a few sentences per project, blockers and
tomorrow's plan. Every sentence must cite the facts it uses; a checker drops sentences without a valid tag, with a
commit ID that git doesn't know, or with a number that isn't in the facts. If no model can answer, the journal is
still written, with the facts alone.

The working day runs from 06:00 to 06:00, so late-night commits land on the right day. The journal is a Markdown
file you own, in Documents\\MWB\\journal; if you edit it, a later run writes beside it instead of over it."""
import ctypes, ctypes.wintypes as wt, datetime, hashlib, logging, re, threading, time
from pathlib import Path

from mwb import config
from mwb.collectors import git, outlook
from mwb.llm import prompts
from mwb.sensors import system
from mwb.skills import dates

log = logging.getLogger('mwb.journal')
DAY_START_H = 6
RETRY_S = 15 * 60
TRIES = 3                       # scheduled runs: after this many failed tries, write the facts alone
SHA = re.compile(r'\b[0-9a-f]{7,40}\b')
TAG_BOX = re.compile(r'\[([^\[\]]+)\]')
TAG = re.compile(r'^[cmaendit]:\S+$')
NUMBER = re.compile(r'(?<![\w.:])\d+(?:[.:]\d+)?')
NUMBER_WORDS = {w: str(i) for i, w in enumerate('two three four five six seven eight nine ten eleven twelve thirteen '
                                                'fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(), 2)}


def day_of(t):
    return (t - datetime.timedelta(hours=DAY_START_H)).date()


def bounds(day):
    start = datetime.datetime.combine(day, datetime.time(DAY_START_H))
    return start, start + datetime.timedelta(days=1)


def hm(seconds):
    m = round(seconds / 60)
    return f'{m // 60} h {m % 60:02d} m' if m >= 60 else f'{m} m'


def project_tag(name):
    return 'a:' + re.sub(r'\s+', '_', name)


class GUID(ctypes.Structure):
    _fields_ = [('Data1', wt.DWORD), ('Data2', wt.WORD), ('Data3', wt.WORD), ('Data4', ctypes.c_ubyte * 8)]


def documents():
    """The Documents folder where Windows really keeps it: it may have been moved, to OneDrive for example."""
    guid = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
    p = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(p)) == 0:
            path = p.value
            ctypes.windll.ole32.CoTaskMemFree(p)
            return Path(path)
    except (AttributeError, OSError):
        pass
    return Path.home() / 'Documents'


def _dt(s):
    return datetime.datetime.fromisoformat(s)


def _overlap(s, e, spans):
    return sum(max(0.0, (min(e, b) - max(s, a)).total_seconds()) for a, b in spans)


def time_by_project(acts, meetings, start, end):
    """({project: seconds}, working-day start, end, seconds away) from activity rows and meetings. Meeting time
    counts as "Meetings", not as the call app; away is the rest of the working day, so the rows add up to it."""
    spans = [(m['start'], m['end']) for m in meetings]
    totals, first, last = {}, None, None
    for a in acts:
        s, e = max(_dt(a['started']), start), min(_dt(a['ended']), end)
        if e <= s or a['idle']:
            continue
        secs = (e - s).total_seconds() - _overlap(s, e, spans)
        if secs > 0:
            totals[a['project'] or 'Other'] = totals.get(a['project'] or 'Other', 0) + secs
        first, last = min(first or s, s), max(last or e, e)
    if spans:
        totals['Meetings'] = sum((b - a).total_seconds() for a, b in spans)
        first = min(t for t in [first, *(a for a, _ in spans)] if t)
        last = max(t for t in [last, *(b for _, b in spans)] if t)
    small = [p for p, v in totals.items() if v < 300 and p not in ('Meetings', 'Other')]
    for p in small:                                     # under 5 minutes: into "Other"
        totals['Other'] = totals.get('Other', 0) + totals.pop(p)
    work = (last - first).total_seconds() if first else 0
    return dict(sorted(totals.items(), key=lambda kv: -kv[1])), first, last, max(0.0, work - sum(totals.values()))


STOP = set("""you your with from that this have were been today work worked working spent time more most also into
over after before about still their there then they them what when which while will would some made make much very
just only other than each across both during""".split())


def _words(text):
    """Numbers and the first five letters of longer words: enough to see whether a fact and a sentence share a topic."""
    return {w if w[0].isdigit() else w[:5] for w in re.findall(r"[a-z0-9][a-z0-9'-]*", text.lower())
            if w[0].isdigit() or (len(w) >= 4 and w not in STOP)}


def check_sentence(s, known, shas, facts):
    """The sentence with only valid tags, or None if it must go. known is {tag: its fact line}. A tag counts only
    if its fact shares a word or a number with the sentence; then the sentence goes if no tag is left, if it names
    a commit ID git doesn't know, or if it has a number the facts don't contain."""
    s = re.sub(r'【([^】†]*)(?:†[^】]*)?】', r'[\1]', str(s)).strip()
    found = []
    words = _words(TAG_BOX.sub(' ', s))

    def keep(m):
        parts = [p.strip() for p in re.split(r'[,;]|\s+(?=[cmaendit]:)', m.group(1)) if p.strip()]
        if not parts or not all(TAG.match(p) for p in parts):
            return m.group(0)
        good = [p for p in parts if p in known and _words(f'{known[p]} {p[2:]}') & words]
        found.extend(good)
        return ' ' + ' '.join(f'[{p}]' for p in good) if good else ''
    s = TAG_BOX.sub(keep, s)
    if not found:
        return None
    body = TAG_BOX.sub('', s)
    for h in SHA.findall(body):
        if re.search(r'\d', h) and not any(sha.startswith(h) for sha in shas):
            return None
    known_numbers = set(NUMBER.findall(facts))
    spelled = re.sub(r'\b(' + '|'.join(NUMBER_WORDS) + r')\b', lambda m: NUMBER_WORDS[m.group(1).lower()],
                     SHA.sub('', body), flags=re.I)
    if any(n not in known_numbers for n in NUMBER.findall(spelled)):
        return None
    return re.sub(r'\s+([.,;:])', r'\1', re.sub(r'\s{2,}', ' ', s)).strip()


class Journal:
    def __init__(self, cfg, store, router, ui):
        self.cfg, self.store, self.router, self.ui = cfg, store, router, ui
        self.j = cfg['journal']
        self.me = cfg['assist'].get('my_name') or 'You'
        self.lock = threading.Lock()
        self.tries = {}                     # day -> (failed tries, monotonic time of the last)
        self.on_ready = None                # on_ready(day, manual): the core opens the page after a manual run
        self.calendar = None                # tests: calendar(start, end) -> items
        self.mail = None                    # tests: mail(start, end) -> {'sent', 'received'}

    # ---- where and when ----------------------------------------------------------------------------------------

    def folder(self):
        return config.path(self.j['folder']) if self.j.get('folder') else documents() / 'MWB' / 'journal'

    def due_time(self):
        h, m = (int(x) for x in self.j['time'].split(':'))
        return datetime.time(h, m)

    def repo_names(self):
        return [r.name for r in git.find_repos(self.j['repo_roots'])]

    def maybe_run(self, now=None):
        """Called about once a minute by the core: today's journal after the set time, and yesterday's if it was
        missed (the laptop was off at 18:30) and the day had anything in it."""
        now = now or datetime.datetime.now()
        today = day_of(now)
        for day in (today - datetime.timedelta(days=1), today):
            if now < datetime.datetime.combine(day, self.due_time()) or self.made(day):
                continue
            tries, last = self.tries.get(day, (0, 0.0))
            if tries and time.monotonic() - last < RETRY_S:
                continue
            if day != today and not self._had_anything(day):
                continue
            threading.Thread(target=self.write, args=(day,), daemon=True, name='journal').start()
            return day
        return None

    def made(self, day):
        return bool(self.store.rows('SELECT 1 FROM journals WHERE day = ?', (day.isoformat(),)))

    def _had_anything(self, day):
        s, e = (t.isoformat(timespec='seconds') for t in bounds(day))
        return bool(self.store.rows('SELECT 1 FROM activity WHERE started >= ? AND started < ? AND idle = 0 LIMIT 1',
                                    (s, e)) or
                    self.store.rows('SELECT 1 FROM meetings WHERE started >= ? AND started < ? LIMIT 1', (s, e)))

    def add_note(self, text):
        """A voice note for today's journal (JNL-6). Returns its id, or None for nothing said."""
        text = (text or '').strip()
        if not text:
            return None
        return self.store.run('INSERT INTO journal_notes (ts, text) VALUES (?, ?)',
                              (datetime.datetime.now().isoformat(timespec='seconds'), text))

    # ---- facts -------------------------------------------------------------------------------------------------

    def collect(self, day, now=None):
        now = now or datetime.datetime.now()
        start, end = bounds(day)
        until = min(end, now)
        s_iso, e_iso = start.isoformat(timespec='seconds'), end.isoformat(timespec='seconds')
        email = git.author(self.j['git_author'])
        commits, dirty = git.day(self.j['repo_roots'], start, until, email) if email else ([], {})
        meetings = []
        for m in self.store.rows('SELECT * FROM meetings WHERE started >= ? AND started < ? ORDER BY started',
                                 (s_iso, e_iso)):
            ms = _dt(m['started'])
            me = _dt(m['ended']) if m['ended'] else (until if m['status'] == 'recording' else ms)
            notes = self.store.notes(m['id'])
            meetings.append({'id': m['id'], 'title': m['title'] or 'Untitled call', 'start': ms, 'end': max(ms, me),
                             'app': m['app_name'] or '', 'label': self.store.label(m['id']),
                             'notes': notes if notes and notes['status'] == 'ready' else None,
                             'actions': self.store.actions(m['id'])})
        acts = self.store.rows('SELECT * FROM activity WHERE ended > ? AND started < ? ORDER BY started', (s_iso, e_iso))
        projects, first, last, away = time_by_project(acts, meetings, start, until)
        dictation = self.store.rows("SELECT COUNT(*) n, SUM(LENGTH(final_text) - LENGTH(REPLACE(final_text, ' ', '')) "
                                    "+ 1) words FROM dictations WHERE ts >= ? AND ts < ? AND final_text != ''",
                                    (s_iso, e_iso))[0]
        notes = self.store.rows('SELECT * FROM journal_notes WHERE ts >= ? AND ts < ? ORDER BY ts', (s_iso, e_iso))
        mode = self.cfg['meetings'].get('outlook', 'if-running')
        mail = None
        if self.j['email'] == 'classic-outlook':
            mail = self.mail(start, until) if self.mail else outlook.mail_day(start, until, mode)
        t_start, t_end = bounds(day + datetime.timedelta(days=1))
        tomorrow = self.calendar(t_start, t_end) if self.calendar else outlook.calendar_between(t_start, t_end, mode)
        open_items = [a for a in self.store.actions(open_only=True) if a['owner'] in ('You', self.me)][:12]
        return {'day': day, 'start': start, 'end': end, 'commits': commits, 'dirty': dirty, 'meetings': meetings,
                'projects': projects, 'first': first, 'last': last, 'away': away, 'dictation': dictation,
                'notes': notes, 'mail': mail, 'tomorrow': tomorrow, 'open': open_items}

    def facts_text(self, f):
        """The facts for the model, each line with its tag; and {tag: fact line} for the checker."""
        out, tags = [f'Day: {f["day"]:%A %d %B %Y} (06:00 to 06:00).'], {}

        def add(tag, text, indent=''):
            tags[tag] = text
            out.append(f'{indent}[{tag}] {text}')
        c = f['commits']
        out.append(f'Commits ({len(c)}, +{sum(x["added"] for x in c)} -{sum(x["removed"] for x in c)}):' if c
                   else 'Commits: none.')
        for x in c[:60]:
            add(f'c:{x["short"]}', f'{x["time"]:%H:%M} {x["repo"]} (branch {x["branch"]}): "{x["message"]}" '
                f'+{x["added"]} -{x["removed"]}, {x["files"]} files')
        if f['dirty']:
            add('c:uncommitted', 'Not committed yet: ' + ', '.join(f'{r} {n} files' for r, n in f['dirty'].items()))
        out.append('Meetings:' if f['meetings'] else 'Meetings: none.')
        for m in f['meetings']:
            lab = m['label']
            bits = [f'{m["start"]:%H:%M} "{m["title"]}", {hm((m["end"] - m["start"]).total_seconds())}']
            if lab:
                bits.append(f'{lab["label"].capitalize()}' + (f' ({lab["subtype"]})' if lab['subtype'] else ''))
            if m['notes']:
                bits.append('Summary: ' + ' '.join(m['notes']['summary'][:4]))
                if m['notes']['decisions']:
                    bits.append('Decisions: ' + '; '.join(m['notes']['decisions'][:4]))
            if m['actions']:
                bits.append('Action items: ' + '; '.join(f'{a["owner"]}: {a["what"]}' for a in m['actions'][:6]))
            add(f'm:{m["id"]}', '. '.join(bits))
        if f['projects']:
            out.append('Time by project (from the window in front):')
            for p, secs in f['projects'].items():
                add(project_tag(p), f'{p} {hm(secs)}')
            out.append(f'Working day {f["first"]:%H:%M} to {f["last"]:%H:%M}; away from the laptop {hm(f["away"])}.')
        d = f['dictation']
        if d['n']:
            add('d:day', f'Dictation: {d["n"]} times, {d["words"] or 0} words.')
        if f['notes']:
            out.append('Voice notes:')
            for n in f['notes']:
                add(f'n:{n["id"]}', f'{n["ts"][11:16]} "{n["text"][:400]}"')
        if f['mail']:
            add('e:sent', f'Email: {len(f["mail"]["sent"])} sent, {f["mail"]["received"]} received.')
            for i, s in enumerate(f['mail']['sent'][:25], 1):
                add(f'e:{i}', f'sent {s["time"]:%H:%M} "{s["subject"]}" to {s["to"]}', '  ')
        if f['open']:
            out.append('Your open action items:')
            for a in f['open']:
                due = dates.pretty(datetime.date.fromisoformat(a['due_date'])) if a['due_date'] else \
                    (a['due_text'] or 'no date')
                add(f'i:{a["id"]}', f'{a["what"]} (due {due}; from "{a["title"] or "a meeting"}")')
        if f['tomorrow']:
            out.append("Tomorrow's calendar:")
            for i, t in enumerate(f['tomorrow'], 1):
                add(f't:{i}', f'{t["start"]:%H:%M}-{t["end"]:%H:%M} "{t["subject"]}"')
        return '\n'.join(out), tags

    # ---- writing -----------------------------------------------------------------------------------------------

    def write(self, day=None, manual=False, from_page=False):
        """Write the journal for a day (default: today). Returns the file's path, or None if it must wait.
        manual: you asked, so the local model may be used and the facts-only version is written at once."""
        day = day or day_of(datetime.datetime.now())
        if not self.lock.acquire(blocking=False):
            return None
        try:
            return self._write(day, manual, from_page)
        except Exception:
            log.exception('journal for %s failed', day)
            self.tries[day] = (self.tries.get(day, (0, 0))[0] + 1, time.monotonic())
            return None
        finally:
            self.lock.release()

    def _write(self, day, manual, from_page=False):
        t0 = time.monotonic()
        if manual:
            self.ui.set_state('working')
        f = self.collect(day)
        facts, tags = self.facts_text(f)
        allow_local = manual or self._calm()
        r = self.router.chat('journal', [prompts.system(), prompts.user(prompts.JOURNAL.format(
            day=f'{day:%A %d %B %Y}', facts=facts))], 1400, temperature=0.3, json_mode=True, allow_local=allow_local)
        data = r.json() if r.ok else None
        if not isinstance(data, dict):
            tries = self.tries.get(day, (0, 0))[0] + 1
            self.tries[day] = (tries, time.monotonic())
            why = r.error or 'the answer was not in the expected form'
            log.info('journal prose for %s failed (try %d): %s', day, tries, why[:120])
            if not manual and tries < TRIES:
                if tries == 1:
                    self.ui.notify('The journal is waiting: the API did not answer and the local model needs mains '
                                   'power and a calm CPU. Press Ctrl+Alt+Shift+J to write it now.')
                return None
            data, route, model = {}, 'none', ''
        else:
            route, model = r.route, r.model
        prose, dropped = self.check(data, tags, f, facts)
        md = self.render(f, prose, route, model, dropped)
        path = self.save(day, md, route, model, time.monotonic() - t0, dropped)
        log.info('journal for %s written via %s: %d sentences dropped, %.1f s', day, route, dropped,
                 time.monotonic() - t0)
        if manual:
            self.ui.set_state('done')
        else:
            self.ui.notify(f'Your journal for {day:%A} is ready. Press Ctrl+Alt+J to open it.')
        if self.on_ready and not from_page:
            self.on_ready(day, manual)
        return path

    def _calm(self):
        """Batch work may use the local model only on mains power with the CPU under 60 % (§8.5)."""
        if not system.on_mains():
            return False
        cpu = system.CpuWatch()
        cpu.sample()
        time.sleep(1)
        return cpu.sample() < 60

    def check(self, data, tags, f, facts):
        """Keep only sentences that pass check_sentence. Returns (prose, how many were dropped)."""
        shas = {c['sha'] for c in f['commits']}
        dropped = 0

        def clean(items):
            nonlocal dropped
            out = []
            for s in items if isinstance(items, list) else []:
                ok = check_sentence(s, tags, shas, facts)
                if ok:
                    out.append(ok)
                elif str(s).strip():
                    dropped += 1
            return out
        projects = []
        names = set(f['projects']) | {c['repo'] for c in f['commits']}
        for p in data.get('projects') or []:
            if isinstance(p, dict) and str(p.get('project', '')).strip() in names:
                sentences = clean(p.get('sentences'))
                if sentences:
                    projects.append((str(p['project']).strip(), sentences))
            elif isinstance(p, dict):
                dropped += len(p.get('sentences') or [])
        return {'summary': clean(data.get('summary')), 'projects': projects, 'blockers': clean(data.get('blockers')),
                'tomorrow': clean(data.get('tomorrow'))}, dropped

    def render(self, f, prose, route, model, dropped):
        esc = lambda s: str(s).replace('|', '\\|').replace('\n', ' ')
        day = f['day']
        L = [f'# {day:%A}, {day.day} {day:%B %Y}', '']
        if prose['summary']:
            L += [' '.join(prose['summary']), '']
        c = f['commits']
        L.append(f'## Code · {len(c)} commit{"s" if len(c) != 1 else ""} · +{sum(x["added"] for x in c)} '
                 f'−{sum(x["removed"] for x in c)}' if c else '## Code')
        L.append('')
        if c:
            L += ['| SHA | Time | Repo | Branch | Message | Lines |', '|---|---|---|---|---|---|']
            L += [f'| `{x["short"]}` | {x["time"]:%H:%M} | {esc(x["repo"])} | {esc(x["branch"])} | {esc(x["message"])} '
                  f'| +{x["added"]} −{x["removed"]} |' for x in c]
        else:
            L.append('No commits today.')
        if f['dirty']:
            L += ['', 'Not committed yet: ' + ', '.join(f'{r} ({n} file{"s" if n != 1 else ""})'
                                                        for r, n in f['dirty'].items()) + '.']
        L.append('')
        if prose['projects']:
            L += ['## Projects', '']
            L += [f'**{p}.** ' + ' '.join(s) for p, s in prose['projects']]
            L.append('')
        ms = f['meetings']
        if ms:
            total = sum((m['end'] - m['start']).total_seconds() for m in ms)
            by = {}
            for m in ms:
                if m['label']:
                    by[m['label']['label']] = by.get(m['label']['label'], 0) + (m['end'] - m['start']).total_seconds()
            head = f'## Meetings · {hm(total)}' + ''.join(f' · {k.capitalize()} {hm(v)}' for k, v in sorted(by.items(),
                                                                                                         key=lambda kv: kv[0] != 'work'))
            L += [head, '']
            for m in ms:
                line = f'- {m["start"]:%H:%M} **{esc(m["title"])}** · {hm((m["end"] - m["start"]).total_seconds())}'
                if m['label']:
                    line += f' · {m["label"]["label"].capitalize()}'
                if m['notes'] and m['notes']['summary']:
                    line += f'. {m["notes"]["summary"][0]}'
                if m['notes'] and m['notes']['decisions']:
                    line += ' Decided: ' + '; '.join(d.rstrip('.') for d in m['notes']['decisions'][:3]) + '.'
                mine = [a for a in m['actions'] if a['owner'] in ('You', self.me)]
                if mine:
                    line += (' Your action' + ('s' if len(mine) > 1 else '') + ': ' +
                             '; '.join(a['what'].rstrip('.') for a in mine) + '.')
                L.append(line)
            L.append('')
        if f['projects']:
            L += ['## Time by project', '', '| Project | Time |', '|---|---|']
            L += [f'| {esc(p)} | {hm(s)} |' for p, s in f['projects'].items()]
            L += ['', f'Working day {f["first"]:%H:%M}–{f["last"]:%H:%M} · away from the laptop {hm(f["away"])}.']
            d = f['dictation']
            if d['n']:
                L.append(f'Dictation: {d["n"]} time{"s" if d["n"] != 1 else ""}, {d["words"] or 0} words.')
            L.append('')
        if f['mail']:
            sent = f['mail']['sent']
            L += [f'## Email · {len(sent)} sent · {f["mail"]["received"]} received', '']
            if sent:
                names = ' · '.join(esc(s['subject']) for s in sent[:5])
                L += ['Sent: ' + names + (f', and {len(sent) - 5} more.' if len(sent) > 5 else '.'), '']
        if f['notes']:
            L += ['## Notes', ''] + [f'- {n["ts"][11:16]} {esc(n["text"])}' for n in f['notes']] + ['']
        if prose['blockers'] or f['open']:
            L += ['## Open items', '']
            L += [' '.join(prose['blockers']), ''] if prose['blockers'] else []
            for a in f['open']:
                due = dates.pretty(datetime.date.fromisoformat(a['due_date'])) if a['due_date'] else \
                    (a['due_text'] or 'no date')
                L.append(f'- {esc(a["what"])} · due {esc(due)} · from {esc(a["title"] or "a meeting")}')
            L.append('')
        if f['tomorrow'] or prose['tomorrow']:
            L += ['## Tomorrow', '']
            L += [f'- {t["start"]:%H:%M} {esc(t["subject"])}' for t in f['tomorrow']]
            if prose['tomorrow']:
                L += ([''] if f['tomorrow'] else []) + [' '.join(prose['tomorrow'])]
            L.append('')
        made = datetime.datetime.now()
        if route == 'none':
            how = 'The summary could not be written (no model answered), so this journal has the facts only.'
        else:
            how = (f'Prose by {model} ({"API" if route == "api" else "on this laptop"}); every sentence cites the '
                   f'facts it uses' + (f'; {dropped} sentence{"s" if dropped != 1 else ""} that did not '
                                       f'{"were" if dropped != 1 else "was"} removed.' if dropped else '.'))
        L += ['---', '', f'*Written {made:%H:%M} by MWB. Commits, meetings, times and counts come from git, MWB and '
                         f'the window in front. {how}*', '']
        return '\n'.join(L)

    def save(self, day, md, route, model, seconds, dropped):
        folder = self.folder()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'{day.isoformat()}.md'
        old = self.store.rows('SELECT file_hash FROM journals WHERE day = ?', (day.isoformat(),))
        if path.exists():
            current = hashlib.sha256(path.read_bytes()).hexdigest()
            if not old or old[0]['file_hash'] != current:           # you edited it (or MWB didn't write it)
                path = folder / f'{day.isoformat()} (new {datetime.datetime.now():%H%M}).md'
        data = md.encode('utf-8')
        path.write_bytes(data)
        self.store.run('INSERT OR REPLACE INTO journals (day, made, path, markdown, route, model, seconds, dropped, '
                       'file_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (day.isoformat(), datetime.datetime.now().isoformat(timespec='seconds'), str(path), md, route,
                        model, round(seconds, 1), dropped, hashlib.sha256(data).hexdigest()))
        return path

    def journals(self, limit=14):
        return self.store.rows('SELECT day, made, path, route, dropped FROM journals ORDER BY day DESC LIMIT ?',
                               (limit,))

    def get(self, day):
        r = self.store.rows('SELECT * FROM journals WHERE day = ?', (day,))
        return r[0] if r else None

    def draft(self, day):
        """Open the journal as an Outlook draft to your manager (JNL-4). MWB never sends it."""
        j = self.get(day)
        if not j:
            return False
        d = datetime.date.fromisoformat(day)
        body = re.sub(r'\s*\[[cmaendit]:[^\]]+\]', '', j['markdown'])         # tags help on the page, not in mail
        return outlook.journal_draft(f'Work update, {d:%A} {d.day} {d:%B}', body, self.j.get('manager_email', ''))
