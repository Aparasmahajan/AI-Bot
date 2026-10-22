"""Meeting notes, action items and the Work or Timepass label (design §9.3, §10), run as background jobs once a
transcript is ready or imported.

Notes come in two passes: each 10-minute part first, then one combined set, so a long meeting never overflows the
model and the label check can quote each part. Owners and deadlines are quoted from the meeting; the dates are
worked out by code from the meeting's day. The label uses cheap rules first (stage A) and asks the model only when
they are unsure (stage B); your corrections (stage C) carry over to the whole series. Batch work goes through the
API at any time, and to the local model only on mains power with a calm CPU."""
import datetime, json, logging, queue, re, threading, time

from mwb.llm import prompts
from mwb.sensors import system
from mwb.skills import dates

log = logging.getLogger('mwb.notes')
CHUNK_S = 600
WORK_WORDS = r'stand-?up|sprint|review|rca|design|sync|planning|demo|client|kt\b|interview|retro|scrum|1:1|one on one|' \
             r'release|deploy|incident|triage|grooming|backlog|status|handover|onboarding|training|all hands|town ?hall'
FUN_WORDS = r'fun|celebrat|birthday|farewell|games?\b|quiz|party|lunch|festival|diwali|holi|treat|movie|cricket|' \
            r'match\b|bday|anniversary|chai|coffee break'
WORK_APPS = {'teams', 'webex', 'zoom', 'slack', 'goto', 'ringcentral'}


def series_of(title):
    """The same meeting each week: the title without dates, numbers and brackets."""
    t = re.sub(r'\(.*?\)|\[.*?\]|\d+', ' ', (title or '').lower())
    return re.sub(r'[^a-z]+', ' ', t).strip()


def clock(s):
    s = int(s)
    return f'{s // 60:02d}:{s % 60:02d}' if s < 3600 else f'{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}'


class Understanding:
    def __init__(self, cfg, store, router, ui):
        self.cfg, self.store, self.router, self.ui = cfg, store, router, ui
        self.me = cfg['assist'].get('my_name') or 'You'
        self.jobs = queue.Queue()
        self.cpu = system.CpuWatch(limit=60, for_s=1)
        self.running = True
        threading.Thread(target=self._loop, daemon=True, name='understanding').start()
        for m in store.rows("SELECT m.id FROM meetings m LEFT JOIN meeting_notes n ON n.meeting_id = m.id "
                            "WHERE m.status = 'ready' AND (n.status IS NULL OR n.status = 'waiting')"):
            self.enqueue(m['id'])

    def enqueue(self, mid):
        self.jobs.put(mid)

    def _batch_ok(self):
        """Local model for batch work: only on mains power with the CPU under 60 % (§8.5)."""
        self.cpu.sample()
        time.sleep(1)
        return system.on_mains() and self.cpu.sample() < 60

    def _loop(self):
        retry = {}
        while self.running:
            try:
                mid = self.jobs.get(timeout=60)
            except queue.Empty:
                now = time.monotonic()
                for m, when in list(retry.items()):
                    if now >= when:
                        del retry[m]
                        self.jobs.put(m)
                continue
            try:
                if not self.notes(mid):
                    retry[mid] = time.monotonic() + 600         # try again in 10 minutes
            except Exception:
                log.exception('notes for meeting %d failed', mid)

    # ---- notes -----------------------------------------------------------------------------------------------

    def _ask_json(self, skill, prompt, max_tokens, allow_local, check):
        for attempt in (1, 2):
            r = self.router.chat(skill, [prompts.system(), prompts.user(prompt)], max_tokens, temperature=0.2,
                                 json_mode=True, allow_local=allow_local)
            if not r.ok:
                return None, r
            data = r.json()
            if isinstance(data, dict) and check(data):
                return data, r
            log.info('%s: answer not in the asked format (try %d)', skill, attempt)
        return None, r

    def notes(self, mid):
        """True when done (or nothing to do); False to try again later."""
        m = self.store.meeting(mid)
        segs = self.store.segments(mid)
        if not m or not segs:
            self.store.save_notes(mid, 'failed', error='no transcript')
            return True
        t0 = time.monotonic()
        allow_local = self._batch_ok()
        when = datetime.datetime.fromisoformat(m['started'])
        title, app = m['title'] or 'Untitled call', m['app_name'] or m['app_id'] or ''
        length_s = max(s[3] or s[2] for s in segs)
        length = f'{max(1, round(length_s / 60))} min'
        parts = {}
        for _, speaker, start, _, text in segs:
            parts.setdefault(int(start // CHUNK_S), []).append(f'[{clock(start)}] {speaker}: {text}')
        chunks = []
        for i in sorted(parts):
            lines = '\n'.join(parts[i])[:14000]
            span = f'{clock(i * CHUNK_S)}-{clock(min(length_s, (i + 1) * CHUNK_S))}'
            data, r = self._ask_json('notes', prompts.CHUNK_NOTES.format(
                span=span, length=length, title=title, app=app, date=f'{when:%a %d %b %Y, %H:%M}', lines=lines),
                900, allow_local, lambda d: isinstance(d.get('notes'), list))
            if data is None:
                self.store.save_notes(mid, 'waiting', error=r.error[:300])
                log.info('notes for meeting %d wait: %s', mid, r.error[:120])
                return False
            data['t'] = span
            chunks.append(data)
        if len(chunks) == 1:
            final = {'summary': chunks[0].get('notes', [])[:4], 'decisions': chunks[0].get('decisions', []),
                     'actions': chunks[0].get('actions', [])}
            route, model = r.route, r.model
        else:
            text = '\n\n'.join(f'Part {c["t"]}:\n' + json.dumps({k: c.get(k) for k in ('notes', 'decisions', 'actions')},
                                                                  ensure_ascii=False) for c in chunks)
            final, r = self._ask_json('notes', prompts.COMBINE.format(title=title, app=app, length=length,
                                                                      date=f'{when:%a %d %b %Y}', parts=text),
                                      1200, allow_local, lambda d: isinstance(d.get('summary'), list))
            if final is None:
                self.store.save_notes(mid, 'waiting', error=r.error[:300])
                return False
            route, model = r.route, r.model
        actions = []
        for a in final.get('actions') or []:
            if not isinstance(a, dict) or not str(a.get('what', '')).strip():
                continue
            owner = str(a.get('owner') or '').strip() or 'Unassigned'
            if owner.lower() in ('you', 'me', 'myself', 'i', self.me.lower()):
                owner = 'You'
            due_text = str(a.get('due') or '').strip()
            due = dates.resolve(due_text, when.date())
            actions.append((owner, str(a['what']).strip(), due_text, due.isoformat() if due else None))
        self.store.replace_actions(mid, actions)
        self.store.save_notes(mid, 'ready', [str(x) for x in final.get('summary') or []],
                              [str(x) for x in final.get('decisions') or [] if str(x).strip().lower() != 'none'],
                              [{k: c.get(k) for k in ('t', 'notes', 'quotes', 'work_talk')} for c in chunks],
                              route, model)
        label = self.classify(mid, allow_local)
        mine = sum(1 for a in actions if a[0] == 'You')
        log.info('meeting %d: notes in %.1f s via %s, %d action items (%d yours), label %s', mid,
                 time.monotonic() - t0, route, len(actions), mine, label)
        self.ui.notify(f'Notes ready: {title} · {(label or "").capitalize() or "unlabelled"} · {length} · '
                       f'{mine} action item{"s" if mine != 1 else ""} for you')
        return True

    # ---- Work or Timepass ------------------------------------------------------------------------------------

    def stage_a(self, m, actions):
        """(score from -1 Timepass to +1 Work, reasons) from the meeting's details (§10.1)."""
        score, reasons = 0.0, []
        title = (m['title'] or '').lower()
        if re.search(WORK_WORDS, title):
            score += 0.6
            reasons.append(f'the title "{m["title"]}" sounds like work')
        if re.search(FUN_WORDS, title):
            score -= 0.6
            reasons.append(f'the title "{m["title"]}" sounds like timepass')
        app = (m['app_id'] or '').split(':')[0]
        if app in ('whatsapp', 'discord', 'telegram', 'phonelink'):
            score -= 0.3
            reasons.append(f'{m["app_name"]} is a personal app')
        elif app in WORK_APPS:
            score += 0.15
            reasons.append(f'{m["app_name"]} is a work tool')
        if len(actions) >= 2:
            score += 0.2
            reasons.append(f'{len(actions)} action items')
        elif not actions:
            score -= 0.1
        return max(-1.0, min(1.0, score)), reasons

    def classify(self, mid, allow_local=True):
        m = self.store.meeting(mid)
        series = series_of(m['title'])
        if series:
            mine = self.store.rows("SELECT label FROM meeting_labels WHERE series = ? AND stage = 'C' "
                                   "ORDER BY meeting_id DESC LIMIT 1", (series,))
            if mine:
                self.store.save_label(mid, mine[0]['label'], None, 1.0, None, None,
                                      ['you labelled this meeting series before'], 'C', series)
                return mine[0]['label']
        actions = self.store.actions(mid)
        score, reasons = self.stage_a(m, actions)
        if abs(score) >= 0.6:
            label = 'work' if score > 0 else 'timepass'
            self.store.save_label(mid, label, None, round(abs(score), 2), None, None, reasons, 'A', series)
            return label
        notes = self.store.notes(mid) or {}
        parts = '\n'.join(f'{c.get("t")}: {json.dumps({"notes": c.get("notes"), "quotes": c.get("quotes"), "work_talk": c.get("work_talk")}, ensure_ascii=False)}'
                          for c in notes.get('chunks') or [])
        speakers = len({s[1] for s in self.store.segments(mid)})
        corrections = self.store.rows("SELECT m.title, l.label FROM meeting_labels l JOIN meetings m ON m.id = "
                                      "l.meeting_id WHERE l.stage = 'C' AND l.model_label IS NOT NULL "
                                      "ORDER BY l.meeting_id DESC LIMIT 5")
        examples = ('\nYour earlier corrections, as examples:\n' + '\n'.join(
            f'- "{c["title"]}" is {c["label"]}' for c in corrections) + '\n') if corrections else ''
        length = (datetime.datetime.fromisoformat(m['ended']) - datetime.datetime.fromisoformat(m['started'])
                  ) if m['ended'] else None
        data, r = self._ask_json('label', prompts.LABEL.format(
            title=m['title'] or 'none', app=m['app_name'] or '', parts=parts or '(no notes)', examples=examples,
            length=f'{round(length.total_seconds() / 60)} min' if length else 'length unknown',
            speakers=f'{speakers} voice lanes'), 500, allow_local,
            lambda d: d.get('label') in ('work', 'timepass'))
        if data is None:
            label = 'work' if score >= 0 else 'timepass'
            self.store.save_label(mid, label, None, round(abs(score), 2), None, None,
                                  reasons + ['the transcript check could not run'], 'A', series)
            return label
        quotes = {q.get('quote', '').strip() for c in notes.get('chunks') or [] for q in (c.get('quotes') or [])
                  if isinstance(q, dict)}
        evidence = [f'{e.get("t", "")} "{e.get("quote", "")}"' for e in data.get('evidence') or []
                    if isinstance(e, dict) and e.get('quote', '').strip() in quotes]       # only quotes that exist
        try:
            conf = max(0.0, min(1.0, float(data.get('confidence', 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        num = lambda v: float(v) if isinstance(v, (int, float)) else None
        self.store.save_label(mid, data['label'], str(data.get('subtype') or '')[:30] or None, round(conf, 2),
                              num(data.get('work_minutes')), num(data.get('timepass_minutes')),
                              [str(x) for x in (data.get('reasons') or [])][:3] + evidence[:2], 'B', series)
        return data['label']

    def correct(self, mid, label):
        """Stage C: your one-click correction, applied to the whole series."""
        old = self.store.label(mid)
        model_label = old['model_label'] if old and old['stage'] == 'C' else (old['label'] if old else None)
        series = series_of((self.store.meeting(mid) or {}).get('title'))
        self.store.save_label(mid, label, None, 1.0, None, None, ['your correction'], 'C', series, model_label)
        if series:
            for row in self.store.rows("SELECT meeting_id, label, stage FROM meeting_labels WHERE series = ? AND "
                                       "meeting_id != ? AND stage != 'C'", (series, mid)):
                self.store.save_label(row['meeting_id'], label, None, 1.0, None, None,
                                      ['you labelled this meeting series'], 'C', series, row['label'])
        log.info('label of meeting %d set to %s by you', mid, label)

    def agreement(self):
        """(agreed, judged): how often MWB's label matched yours, over meetings you have confirmed or corrected."""
        rows = self.store.rows("SELECT label, model_label FROM meeting_labels WHERE stage = 'C' AND model_label "
                               "IS NOT NULL")
        return sum(r['label'] == r['model_label'] for r in rows), len(rows)

    def close(self):
        self.running = False
