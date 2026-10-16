"""The Today page (design §8.3): a local page that the core serves on 127.0.0.1 to your own browser. Phase 2 shows
the meetings, their transcripts and a search; notes, labels and the journal join it in Phases 3 and 4.

The server starts when you open the page (Ctrl+Alt+J or the tray) and stops after 30 idle minutes. Only this laptop
can reach it, and only with this session's token, which the first link sets as a cookie."""
import datetime, html, http.server, logging, os, secrets, threading, time, urllib.parse

log = logging.getLogger('mwb.today')
IDLE_S = 30 * 60

CSS = """
:root{--paper:#F3F5F8;--sheet:#FFFFFF;--ink:#0E1726;--ink-2:#465267;--ink-3:#66738A;--rule:#D3D9E3;--cobalt:#2148C9;
--you:#2148C9;--them:#946000;--ok:#21734B;--ok-wash:#DDF2E6;--amber:#946000;--amber-wash:#F7ECD3;--wash:#EDF1F7}
@media (prefers-color-scheme:dark){:root{--paper:#06122A;--sheet:#0A1A36;--ink:#E4EBF6;--ink-2:#A9B7CF;--ink-3:#8494B2;
--rule:#22416F;--cobalt:#7FA6FF;--you:#7FA6FF;--them:#F1B65C;--ok:#70D49C;--ok-wash:#123526;--amber:#F1B65C;
--amber-wash:#3A301C;--wash:#0F264C}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,sans-serif}
main{max-width:920px;margin:0 auto;padding:24px 16px 64px}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;justify-content:space-between;margin-bottom:16px}
h1{font-size:22px;margin:0}h2{font-size:16px;margin:28px 0 8px}a{color:var(--cobalt);text-decoration:none}
a:hover{text-decoration:underline}.muted{color:var(--ink-3)}
form{display:flex;gap:8px}input[type=search]{font:inherit;padding:6px 10px;border:1px solid var(--rule);border-radius:8px;
background:var(--sheet);color:var(--ink);min-width:220px}button{font:inherit;padding:6px 12px;border-radius:8px;
border:1px solid var(--rule);background:var(--sheet);color:var(--ink);cursor:pointer}
.card{background:var(--sheet);border:1px solid var(--rule);border-radius:12px;overflow:hidden}
table{width:100%;border-collapse:collapse}td,th{padding:10px 12px;text-align:left;border-bottom:1px solid var(--rule);
vertical-align:top}th{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
tr:last-child td{border-bottom:0}.chip{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;
background:var(--wash);color:var(--ink-2)}.chip.ready{background:var(--ok-wash);color:var(--ok)}
.chip.recording,.chip.transcribing{background:var(--amber-wash);color:var(--amber)}
.line{display:grid;grid-template-columns:64px 56px 1fr;gap:10px;padding:8px 14px;border-bottom:1px solid var(--rule)}
.line:last-child{border-bottom:0}.t{color:var(--ink-3);font:13px/1.6 Consolas,monospace}
.who{font-weight:600;font-size:13px}.who.You{color:var(--you)}.who.Them{color:var(--them)}
mark{background:var(--amber-wash);color:inherit}
.notes{padding:12px 16px}.notes ul{margin:4px 0 10px;padding-left:20px}.notes h3{font-size:13px;margin:10px 0 2px;
color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em}.lbl{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.lbl form{display:inline}.lbl button.on{background:var(--cobalt);color:#fff;border-color:transparent}
.chip.work{background:var(--wash);color:var(--cobalt)}.chip.timepass{background:var(--amber-wash);color:var(--amber)}
.due{color:var(--ink-3);font-size:13px;white-space:nowrap}
@media (max-width:600px){.line{grid-template-columns:52px 1fr}.line .t{grid-row:span 2}td:nth-child(4),th:nth-child(4){display:none}}
"""


def _clock(seconds):
    s = int(seconds or 0)
    return f'{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}' if s >= 3600 else f'{s // 60}:{s % 60:02d}'


def _minutes(m):
    if not m.get('ended'):
        return '…'
    d = datetime.datetime.fromisoformat(m['ended']) - datetime.datetime.fromisoformat(m['started'])
    return f'{max(1, round(d.total_seconds() / 60))} min'


def _due(a):
    if a.get('due_date'):
        d = datetime.date.fromisoformat(a['due_date'])
        return f'{d:%a} {d.day} {d:%b}'
    return html.escape(a.get('due_text') or 'no date')


def _page(title, body, refresh=False):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            + ('<meta http-equiv="refresh" content="10">' if refresh else '') +
            f'<style>{CSS}</style></head><body><main>{body}</main></body></html>')


class TodayPage:
    def __init__(self, store):
        self.store = store
        self.server = None
        self.token = secrets.token_urlsafe(18)
        self.last_hit = 0.0
        self.understanding = None           # from Phase 3: label corrections

    def url(self):
        if not self.server:
            self._start()
        return f'http://127.0.0.1:{self.server.server_address[1]}/?t={self.token}'

    def open(self):
        os.startfile(self.url())

    def _start(self):
        page = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                page.last_hit = time.monotonic()
                u = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(u.query)
                cookie = self.headers.get('Cookie', '')
                if q.get('t', [''])[0] != page.token and f'mwb={page.token}' not in cookie:
                    return self.send(403, _page('MWB', '<p>Open this page from MWB (Ctrl+Alt+J).</p>'))
                try:
                    if u.path == '/':
                        body, refresh = page.home(q.get('q', [''])[0].strip())
                    elif u.path.startswith('/meeting/') and u.path[9:].isdigit():
                        body, refresh = page.meeting(int(u.path[9:]))
                    else:
                        return self.send(404, _page('MWB', '<p>Not found.</p>'))
                except Exception:
                    log.exception('page failed')
                    return self.send(500, _page('MWB', '<p>Something went wrong; see the log.</p>'))
                self.send(200, body, refresh)

            def do_POST(self):
                """One-click label correction (§10.3). Only from this page: the cookie is SameSite=Strict."""
                page.last_hit = time.monotonic()
                u = urllib.parse.urlparse(self.path)
                if f'mwb={page.token}' not in self.headers.get('Cookie', ''):
                    return self.send(403, _page('MWB', '<p>Open this page from MWB (Ctrl+Alt+J).</p>'))
                self.rfile.read(int(self.headers.get('Content-Length') or 0))
                parts = u.path.strip('/').split('/')
                ok = len(parts) == 3 and parts[0] == 'label' and parts[1].isdigit() and parts[2] in ('work', 'timepass')
                if ok and page.understanding:
                    page.understanding.correct(int(parts[1]), parts[2])
                    self.send_response(303)
                    self.send_header('Location', f'/meeting/{parts[1]}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                self.send(404, _page('MWB', '<p>Not found.</p>'))

            def send(self, code, text, refresh=False):
                data = text.encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Set-Cookie', f'mwb={page.token}; HttpOnly; SameSite=Strict; Path=/')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(data)

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.last_hit = time.monotonic()
        threading.Thread(target=self.server.serve_forever, daemon=True, name='today-page').start()
        threading.Thread(target=self._idle_stop, daemon=True, name='today-idle').start()
        log.info('Today page on port %d', self.server.server_address[1])

    def _idle_stop(self):
        while self.server:
            time.sleep(60)
            if time.monotonic() - self.last_hit > IDLE_S:
                self.close()

    def close(self):
        s, self.server = self.server, None
        if s:
            s.shutdown()
            s.server_close()
            log.info('Today page stopped')

    # ---- pages -----------------------------------------------------------------------------------------------

    def home(self, query):
        e = html.escape
        meetings = self.store.meetings(60)
        busy = any(m['status'] in ('recording', 'transcribing') for m in meetings)
        today = datetime.date.today().isoformat()
        rows = []
        for m in meetings:
            when = datetime.datetime.fromisoformat(m['started'])
            day = 'Today' if m['started'][:10] == today else when.strftime('%a %d %b')
            progress = f' {m["pieces_done"]}/{m["pieces"]}' if m['status'] == 'transcribing' else ''
            rows.append(f'<tr><td>{day}<br><span class="muted">{when:%H:%M}</span></td>'
                        f'<td><a href="/meeting/{m["id"]}">{e(m["title"] or "Untitled call")}</a><br>'
                        f'<span class="muted">{e(m["app_name"] or "")}</span></td>'
                        f'<td><span class="chip {e(m["status"])}">{e(m["status"])}{progress}</span></td>'
                        f'<td class="muted">{_minutes(m)}</td></tr>')
        table = ('<div class="card"><table><tr><th>When</th><th>Meeting</th><th>Transcript</th><th>Length</th></tr>'
                 + ''.join(rows) + '</table></div>') if rows else \
            '<p class="muted">No meetings yet. When a call starts, MWB asks whether to record it.</p>'
        found = ''
        if query:
            hits = self.search(query)
            found = '<h2>Search</h2>' + ('<div class="card">' + ''.join(
                f'<div class="line"><span class="t"><a href="/meeting/{mid}#s{sid}">{_clock(st)}</a></span>'
                f'<span class="who {e(sp) if sp in ("You", "Them") else ""}">{e(sp)}</span>'
                f'<span>{snip}<br><span class="muted">{e(title or "Untitled call")}</span></span></div>'
                for mid, sid, sp, st, snip, title in hits) + '</div>' if hits else
                f'<p class="muted">Nothing found for “{e(query)}”.</p>')
        todo = self.store.actions(open_only=True)[:12]
        todo_html = ''
        if todo:
            todo_html = '<h2>Open action items</h2><div class="card">' + ''.join(
                f'<div class="line"><span class="due">{_due(a)}</span><span class="who">{e(a["owner"])}</span>'
                f'<span>{e(a["what"])}<br><a class="muted" href="/meeting/{a["meeting_id"]}">'
                f'{e(a["title"] or "Untitled call")}</a></span></div>' for a in todo) + '</div>'
        sent = self.store.rows("SELECT route, COUNT(*) n, SUM(chars_in) c FROM api_log WHERE substr(ts, 1, 10) = ? "
                               "GROUP BY route", (today,))
        usage = ', '.join(f'{r["n"]} request{"s" if r["n"] != 1 else ""} to the '
                          f'{"API" if r["route"] == "api" else "local model"} ({(r["c"] or 0) // 1000} k characters)'
                          for r in sent if r['route'])
        agreed, judged = self.understanding.agreement() if self.understanding else (0, 0)
        agree = f' Labels: {agreed} of {judged} matched yours.' if judged else ''
        body = (f'<header><h1>MWB · Today</h1><form method="get" action="/"><input type="search" name="q" '
                f'value="{e(query)}" placeholder="Search transcripts" aria-label="Search transcripts">'
                f'<button>Search</button></form></header>{found}{todo_html}<h2>Meetings</h2>{table}'
                f'<p class="muted">Audio and transcripts stay on this laptop; notes and answers send text to the API. '
                f'Today: {usage or "nothing sent"}.{agree}</p>')
        return _page('MWB · Today', body, refresh=busy), busy

    def search(self, query):
        terms = ' '.join('"' + w.replace('"', '') + '"' for w in query.split()[:8])
        with self.store.lock:
            return self.store.db.execute(
                "SELECT s.meeting_id, s.id, s.speaker, s.start_s, snippet(segments_fts, 0, '<mark>', '</mark>', '…', "
                '12), m.title FROM segments_fts JOIN segments s ON s.id = segments_fts.rowid JOIN meetings m '
                'ON m.id = s.meeting_id WHERE segments_fts MATCH ? ORDER BY rank LIMIT 40', (terms,)).fetchall()

    def meeting(self, mid):
        e = html.escape
        m = self.store.meeting(mid)
        if not m:
            return _page('MWB', '<p>No such meeting.</p>'), False
        lines = self.store.segments(mid)
        busy = m['status'] in ('recording', 'transcribing')
        body = ''.join(f'<div class="line" id="s{i}"><span class="t">{_clock(st)}</span>'
                       f'<span class="who {e(sp) if sp in ("You", "Them") else ""}">{e(sp)}</span>'
                       f'<span>{e(t)}</span></div>' for i, sp, st, _, t in lines)
        when = datetime.datetime.fromisoformat(m['started'])
        state = {'recording': 'Recording now; lines appear as they are transcribed.',
                 'transcribing': f'Transcribing: {m["pieces_done"]} of {m["pieces"]} pieces done.',
                 'failed': 'This recording failed.'}.get(m['status'], '')
        text = '\n'.join(f'[{_clock(st)}] {sp}: {t}' for _, sp, st, _, t in lines)
        copy = (f'<button onclick="navigator.clipboard.writeText(document.getElementById(\'all\').value)">Copy all'
                f'</button><textarea id="all" hidden>{e(text)}</textarea>') if lines else ''
        notes, label, acts = self.store.notes(mid), self.store.label(mid), self.store.actions(mid)
        extra = ''
        if label:
            buttons = ''.join(
                f'<form method="post" action="/label/{mid}/{v}"><button class="{"on" if label["label"] == v else ""}"'
                f' title="{"Confirm" if label["label"] == v else "Change to"} {v}">{v.capitalize()}</button></form>'
                for v in ('work', 'timepass'))
            why = '; '.join(e(str(r)) for r in label['reasons'][:4])
            how = {'A': 'from the details', 'B': 'from the transcript', 'C': 'your choice'}[label['stage']]
            sub = ' · ' + e(label['subtype']) if label['subtype'] else ''
            extra += (f'<div class="lbl"><span class="chip {e(label["label"])}">{e(label["label"].capitalize())}{sub}'
                      f'</span><span class="muted">{how}{": " + why if why else ""}</span>{buttons}</div>')
        if notes and notes['status'] == 'ready':
            def ul(xs):
                return '<ul>' + ''.join(f'<li>{e(str(x))}</li>' for x in xs) + '</ul>' if xs else '<p class="muted">None</p>'
            act = ('<ul>' + ''.join(f'<li><b>{e(a["owner"])}</b>: {e(a["what"])} <span class="due">{_due(a)}</span>'
                                    f'</li>' for a in acts) + '</ul>') if acts else '<p class="muted">None</p>'
            extra += (f'<h2>Notes</h2><div class="card notes"><h3>Summary</h3>{ul(notes["summary"])}'
                      f'<h3>Decisions</h3>{ul(notes["decisions"])}<h3>Action items</h3>{act}'
                      f'<p class="muted">Written by {e(notes["model"] or "")} ({e(notes["route"] or "")}). '
                      f'Dates are worked out from the meeting day.</p></div>')
        elif notes and notes['status'] == 'waiting':
            extra += ('<p class="muted">Notes are waiting: the API could not be reached, and the local model waits '
                      'for mains power and a calm CPU.</p>')
        page = (f'<header><h1>{e(m["title"] or "Untitled call")}</h1><a href="/">← All meetings</a></header>'
                f'<p class="muted">{e(m["app_name"] or "")} · {when:%a %d %b %Y, %H:%M} · {_minutes(m)}'
                f'{" · " + e(m["language"]) if m["language"] else ""}</p>'
                + (f'<p><span class="chip {e(m["status"])}">{e(state)}</span></p>' if state else '')
                + extra + f'<h2>Transcript</h2><p>{copy}</p>'
                + (f'<div class="card">{body}</div>' if lines else '<p class="muted">No lines yet.</p>'))
        return _page(m['title'] or 'Meeting', page, refresh=busy), busy
