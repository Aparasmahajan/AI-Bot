"""Facts for answer mode (design §9.7). Questions about your day are answered from your own data, found by code:
meetings and their notes, action items, transcript search, the Outlook calendar and your dictations. Each fact
carries a tag such as [M3 10:04] or [A2]; the model must cite those tags, and any tag it invents is removed."""
import datetime, re

from mwb.skills import dates

STOP = set('''a an the and or but if of to in on at for from by with about into over after before what whats when where
who whom whose which why how is are was were be been am do does did doing done have has had i me my mine we us our
you your it its this that these those there here can could would should will shall may might must tell show give
say said says mention mentioned talk talked discuss discussed today yesterday week any all some more most mwb please
let know get got any anything something did my'''.split())


def _clock(s):
    s = int(s or 0)
    return f'{s // 60:02d}:{s % 60:02d}' if s < 3600 else f'{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}'


def gather(question, store, outlook_mode='if-running', calendar=None):
    """(facts text, set of tags). calendar() returns upcoming items; given for tests."""
    q = question.lower()
    facts, tags = [], set()
    today = datetime.date.today()

    def add(tag, text):
        tags.add(tag)
        facts.append(f'[{tag}] {text}')

    # meetings on the day asked about, with their notes and labels
    if re.search(r'meeting|call|today|yesterday|this week|my day|stand-?up|sync|discuss|decid|label|timepass', q):
        start = today - datetime.timedelta(days=1 if 'yesterday' in q else (6 if 'week' in q else 0))
        end = today - datetime.timedelta(days=1) if 'yesterday' in q else today
        for m in store.rows('SELECT * FROM meetings WHERE substr(started, 1, 10) BETWEEN ? AND ? ORDER BY started',
                            (start.isoformat(), end.isoformat())):
            when = datetime.datetime.fromisoformat(m['started'])
            mins = ''
            if m['ended']:
                mins = f', {round((datetime.datetime.fromisoformat(m["ended"]) - when).total_seconds() / 60)} min'
            label = store.label(m['id'])
            add(f'M{m["id"]} {when:%H:%M}', f'meeting "{m["title"] or "untitled"}" on {when:%a %d %b} '
                f'({m["app_name"]}{mins}{", " + label["label"] if label else ""}, transcript {m["status"]})')
            notes = store.notes(m['id'])
            if notes and notes['status'] == 'ready':
                for b in notes['summary'][:4]:
                    facts.append(f'    [M{m["id"]}] summary: {b}')
                for d in notes['decisions'][:4]:
                    facts.append(f'    [M{m["id"]}] decision: {d}')
                tags.add(f'M{m["id"]}')
    # the calendar, for what comes next
    if re.search(r'next meeting|calendar|schedule|who is in|who\'s in|attend|agenda|upcoming|free|busy|later today', q):
        items = calendar() if calendar else None
        if items is None:
            from mwb.collectors import outlook
            items = outlook.upcoming(12, outlook_mode)
        for i, c in enumerate(items, 1):
            add(f'C{i}', f'calendar: "{c["subject"]}" {c["start"]:%a %d %b %H:%M}-{c["end"]:%H:%M}'
                f'{", organiser " + c["organizer"] if c.get("organizer") else ""}'
                f'{", invited: " + c["attendees"] if c.get("attendees") else ""}')
        if not items:
            facts.append('(calendar: nothing found in the next 12 hours, or classic Outlook is not running)')
    # action items
    if re.search(r'action item|to-?do|pending|open item|follow.?up|owe|promis|deadline|due|tasks?\b|what do i have', q):
        for a in store.actions(open_only=True)[:15]:
            due = dates.pretty(datetime.date.fromisoformat(a['due_date'])) if a['due_date'] else (a['due_text'] or
                                                                                                   'no date')
            add(f'A{a["id"]}', f'action item for {a["owner"]}: {a["what"]} (due {due}; from "{a["title"] or ""}")')
    # what was said: search the transcripts
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9'-]{2,}", q) if w not in STOP]
    if words and re.search(r'say|said|mention|talk|discuss|about|what did|anyone|who', q):
        query = ' OR '.join(f'"{w}"' for w in words[:6])
        try:
            hits = store.rows('SELECT s.meeting_id, s.speaker, s.start_s, s.text, m.title FROM segments_fts f JOIN '
                              'segments s ON s.id = f.rowid JOIN meetings m ON m.id = s.meeting_id WHERE segments_fts '
                              'MATCH ? ORDER BY rank LIMIT 8', (query,))
        except Exception:
            hits = []
        for h in hits:
            add(f'M{h["meeting_id"]} {_clock(h["start_s"])}', f'in "{h["title"] or "untitled"}", {h["speaker"]} '
                f'said: "{h["text"][:300]}"')
    # dictations
    if re.search(r'dictat|did i (write|type)|what i wrote', q):
        for d in store.rows('SELECT id, ts, app, final_text FROM dictations ORDER BY id DESC LIMIT 5'):
            add(f'D{d["id"]}', f'dictated at {d["ts"][11:16]} into {d["app"]}: "{(d["final_text"] or "")[:200]}"')
    return '\n'.join(facts), tags


def check_citations(text, tags):
    """Remove citations that don't match a fact; returns (text, how many were removed)."""
    known = {t.split()[0] for t in tags} | tags
    text = re.sub(r'【([^】†]*)(?:†[^】]*)?】', r'[\1]', text)           # gpt-oss sometimes cites 【M1†…】
    removed = 0

    def keep(m):
        nonlocal removed
        tag = m.group(1).strip()
        if tag in tags or tag.split()[0] in known:
            return m.group(0)
        removed += 1
        return ''
    text = re.sub(r'\[\s*((?:M|A|C|D)\d+(?: \d{1,2}:\d{2}(?::\d{2})?)?)\s*\]', lambda m: f'[{m.group(1)}]', text)     # the model sometimes writes [ M1 ]
    return re.sub(r'\[((?:M|A|C|D)\d+(?: \d{1,2}:\d{2}(?::\d{2})?)?)\]', keep, text), removed
