"""SQLite storage (design §14): one database in %LOCALAPPDATA%\\MWB, WAL mode, FTS5 search, standard library only."""
import datetime, json, sqlite3, threading
from pathlib import Path

from mwb import config

SCHEMA = Path(__file__).with_name('schema.sql')


class Store:
    def __init__(self, path=None):
        path = Path(path or config.LOCAL / 'mwb.db')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute('PRAGMA journal_mode = WAL')
            self.db.execute('PRAGMA synchronous = NORMAL')
            self.db.execute('PRAGMA foreign_keys = ON')
            self.db.executescript(SCHEMA.read_text(encoding='utf-8'))

    def add_dictation(self, started, app, raw_text, final_text, latency_ms, audio_s, pieces, trigger, inserted_by):
        with self.lock:
            cur = self.db.execute(
                'INSERT INTO dictations (ts, app, raw_text, final_text, latency_ms, audio_s, pieces, trigger, '
                'inserted_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (started.isoformat(timespec='seconds'), app, raw_text, final_text, latency_ms, round(audio_s, 2),
                 pieces, trigger, inserted_by))
            return cur.lastrowid

    def last_dictation(self):
        with self.lock:
            row = self.db.execute("SELECT final_text FROM dictations WHERE final_text != '' "
                                  'ORDER BY id DESC LIMIT 1').fetchone()
        return row[0] if row else None

    def latencies(self, since=None):
        since = since or (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat(timespec='seconds')
        with self.lock:
            return [r[0] for r in self.db.execute(
                'SELECT latency_ms FROM dictations WHERE ts >= ? AND latency_ms IS NOT NULL', (since,))]

    # ---- meetings (Phase 2) ----------------------------------------------------------------------------------

    MEETING_FIELDS = ('app_id', 'app_name', 'title', 'started', 'ended', 'status', 'source', 'language', 'pieces',
                      'pieces_done', 'camera')

    def new_meeting(self, **f):
        cols = [k for k in self.MEETING_FIELDS if k in f]
        with self.lock:
            return self.db.execute(f'INSERT INTO meetings ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})',
                                   [f[k] for k in cols]).lastrowid

    def update_meeting(self, meeting_id, **f):
        cols = [k for k in self.MEETING_FIELDS if k in f]
        with self.lock:
            self.db.execute(f'UPDATE meetings SET {", ".join(k + " = ?" for k in cols)} WHERE id = ?',
                            [f[k] for k in cols] + [meeting_id])

    def bump_meeting(self, meeting_id, field, by=1):
        assert field in ('pieces', 'pieces_done')
        with self.lock:
            self.db.execute(f'UPDATE meetings SET {field} = {field} + ? WHERE id = ?', (by, meeting_id))

    def add_segments(self, meeting_id, rows):
        """rows: (speaker, start_s, end_s, text)."""
        with self.lock:
            self.db.execute('BEGIN')
            self.db.executemany('INSERT INTO segments (meeting_id, speaker, start_s, end_s, text) '
                                'VALUES (?, ?, ?, ?, ?)', [(meeting_id, *r) for r in rows])
            self.db.execute('COMMIT')

    def delete_segments(self, ids):
        with self.lock:
            self.db.executemany('DELETE FROM segments WHERE id = ?', [(i,) for i in ids])

    def meeting(self, meeting_id):
        with self.lock:
            cur = self.db.execute('SELECT * FROM meetings WHERE id = ?', (meeting_id,))
            row = cur.fetchone()
            return dict(zip([c[0] for c in cur.description], row)) if row else None

    def meetings(self, limit=50, status=None):
        q = 'SELECT * FROM meetings' + (' WHERE status = ?' if status else '') + ' ORDER BY started DESC LIMIT ?'
        with self.lock:
            cur = self.db.execute(q, (status, limit) if status else (limit,))
            names = [c[0] for c in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

    def segments(self, meeting_id):
        with self.lock:
            return self.db.execute('SELECT id, speaker, start_s, end_s, text FROM segments WHERE meeting_id = ? '
                                   'ORDER BY start_s, id', (meeting_id,)).fetchall()

    def app_choices(self):
        with self.lock:
            return dict(self.db.execute('SELECT app_id, policy FROM app_policy').fetchall())

    def set_choice(self, app_id, policy):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO app_policy (app_id, policy, decided) VALUES (?, ?, ?)',
                            (app_id, policy, datetime.datetime.now().isoformat(timespec='seconds')))

    def get_meta(self, key, default=None):
        with self.lock:
            row = self.db.execute('SELECT value FROM meta WHERE key = ?', (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key, value):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', (key, str(value)))

    # ---- understanding (Phase 3) -----------------------------------------------------------------------------

    def rows(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            names = [c[0] for c in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

    def run(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).lastrowid

    def save_notes(self, meeting_id, status, summary=None, decisions=None, chunks=None, route=None, model=None,
                   error=None):
        dump = lambda v: None if v is None else json.dumps(v, ensure_ascii=False)
        self.run('INSERT OR REPLACE INTO meeting_notes (meeting_id, status, summary, decisions, chunks, route, model, '
                 'made, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (meeting_id, status, dump(summary), dump(decisions), dump(chunks), route, model,
                  datetime.datetime.now().isoformat(timespec='seconds'), error))

    def notes(self, meeting_id):
        r = self.rows('SELECT * FROM meeting_notes WHERE meeting_id = ?', (meeting_id,))
        if not r:
            return None
        r = r[0]
        for k in ('summary', 'decisions', 'chunks'):
            r[k] = json.loads(r[k]) if r[k] else []
        return r

    def replace_actions(self, meeting_id, items):
        """items: (owner, what, due_text, due_date or None)."""
        now = datetime.datetime.now().isoformat(timespec='seconds')
        with self.lock:
            self.db.execute('BEGIN')
            self.db.execute('DELETE FROM action_items WHERE meeting_id = ?', (meeting_id,))
            self.db.executemany('INSERT INTO action_items (meeting_id, owner, what, due_text, due_date, created) '
                                'VALUES (?, ?, ?, ?, ?, ?)', [(meeting_id, *i, now) for i in items])
            self.db.execute('COMMIT')

    def actions(self, meeting_id=None, open_only=False):
        q = 'SELECT a.*, m.title, m.started FROM action_items a LEFT JOIN meetings m ON m.id = a.meeting_id'
        where, args = [], []
        if meeting_id is not None:
            where.append('a.meeting_id = ?')
            args.append(meeting_id)
        if open_only:
            where.append('a.done = 0')
        return self.rows(q + (' WHERE ' + ' AND '.join(where) if where else '') +
                         ' ORDER BY a.due_date IS NULL, a.due_date, a.id', args)

    def save_label(self, meeting_id, label, subtype, confidence, work_min, timepass_min, reasons, stage, series,
                   model_label=None):
        self.run('INSERT OR REPLACE INTO meeting_labels (meeting_id, label, subtype, confidence, work_min, '
                 'timepass_min, reasons, stage, model_label, series) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                 (meeting_id, label, subtype, confidence, work_min, timepass_min,
                  json.dumps(reasons, ensure_ascii=False), stage, model_label, series))

    def label(self, meeting_id):
        r = self.rows('SELECT * FROM meeting_labels WHERE meeting_id = ?', (meeting_id,))
        if r:
            r[0]['reasons'] = json.loads(r[0]['reasons'] or '[]')
        return r[0] if r else None

    def log_usage(self, skill, route, model, chars_in, chars_out, seconds, ok):
        self.run('INSERT INTO api_log (ts, skill, route, model, chars_in, chars_out, seconds, ok) '
                 'VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (datetime.datetime.now().isoformat(timespec='seconds'), skill,
                                                     route, model, chars_in, chars_out, round(seconds, 2), int(ok)))

    def close(self):
        with self.lock:
            self.db.close()
