-- MWB's database (design §14): %LOCALAPPDATA%\MWB\mwb.db, WAL mode. The core is the only writer.
-- Phase 1 has the dictation history; meetings, events and the journal tables arrive with Phases 2 to 4.

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS dictations (
    id          INTEGER PRIMARY KEY,
    ts          TEXT NOT NULL,          -- local time the dictation started, ISO 8601
    app         TEXT,                   -- program it went into, e.g. Code.exe (never the window title)
    raw_text    TEXT,                   -- the speech engine's words, pieces joined
    final_text  TEXT,                   -- after the clean-up rules: what was inserted
    latency_ms  INTEGER,                -- from finishing to the text being in place
    audio_s     REAL,
    pieces      INTEGER,
    trigger     TEXT,                   -- caps | hold
    inserted_by TEXT                    -- paste | type | none
);

CREATE INDEX IF NOT EXISTS dictations_ts ON dictations (ts);

-- Search over what you dictated
CREATE VIRTUAL TABLE IF NOT EXISTS dictations_fts USING fts5 (final_text, content = 'dictations', content_rowid = 'id');
CREATE TRIGGER IF NOT EXISTS dictations_ai AFTER INSERT ON dictations BEGIN
    INSERT INTO dictations_fts (rowid, final_text) VALUES (new.id, new.final_text);
END;
CREATE TRIGGER IF NOT EXISTS dictations_ad AFTER DELETE ON dictations BEGIN
    INSERT INTO dictations_fts (dictations_fts, rowid, final_text) VALUES ('delete', old.id, old.final_text);
END;

-- Phase 2: meetings (design §9.3, §14)
CREATE TABLE IF NOT EXISTS meetings (
    id          INTEGER PRIMARY KEY,
    app_id      TEXT,                   -- teams, zoom, meet, browser:brave.exe, manual, imported ...
    app_name    TEXT,
    title       TEXT,                   -- from the calendar, the meeting tab, or the imported file
    started     TEXT NOT NULL,          -- local time, ISO 8601
    ended       TEXT,
    status      TEXT NOT NULL,          -- recording | transcribing | ready | failed
    source      TEXT NOT NULL,          -- recorded | imported
    language    TEXT,                   -- what whisper heard most: en, hi ...
    pieces      INTEGER DEFAULT 0,      -- audio pieces made
    pieces_done INTEGER DEFAULT 0,      -- ... and transcribed
    camera      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS meetings_started ON meetings (started);

CREATE TABLE IF NOT EXISTS segments (
    id          INTEGER PRIMARY KEY,
    meeting_id  INTEGER NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
    speaker     TEXT NOT NULL,          -- You | Them, or a name from an imported transcript
    start_s     REAL NOT NULL,          -- from the start of the meeting
    end_s       REAL,
    text        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS segments_meeting ON segments (meeting_id, start_s);

CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5 (text, content = 'segments', content_rowid = 'id');
CREATE TRIGGER IF NOT EXISTS segments_ai AFTER INSERT ON segments BEGIN
    INSERT INTO segments_fts (rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS segments_ad AFTER DELETE ON segments BEGIN
    INSERT INTO segments_fts (segments_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

-- Your answers to "Record this call?": "never" for an app, or a remembered choice for an unknown one
CREATE TABLE IF NOT EXISTS app_policy (
    app_id      TEXT PRIMARY KEY,
    policy      TEXT NOT NULL,          -- record | ask | never
    decided     TEXT
);

INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', '2');
UPDATE meta SET value = '2' WHERE key = 'schema' AND value < '2';

-- Phase 3: understanding (design §9.3, §10, §12.7)
CREATE TABLE IF NOT EXISTS meeting_notes (
    meeting_id  INTEGER PRIMARY KEY REFERENCES meetings (id) ON DELETE CASCADE,
    status      TEXT NOT NULL,          -- waiting | ready | failed
    summary     TEXT,                   -- JSON list of bullets
    decisions   TEXT,                   -- JSON list
    chunks      TEXT,                   -- JSON: per 10-minute chunk notes and quotes, for the label check
    route       TEXT,                   -- api | local
    model       TEXT,
    made        TEXT,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS action_items (
    id          INTEGER PRIMARY KEY,
    meeting_id  INTEGER REFERENCES meetings (id) ON DELETE CASCADE,
    owner       TEXT,                   -- You, or the name said in the meeting
    what        TEXT NOT NULL,
    due_text    TEXT,                   -- as said: "by Friday"
    due_date    TEXT,                   -- worked out by code from due_text and the meeting's date
    done        INTEGER DEFAULT 0,
    created     TEXT
);
CREATE INDEX IF NOT EXISTS action_items_open ON action_items (done, due_date);

CREATE TABLE IF NOT EXISTS meeting_labels (
    meeting_id  INTEGER PRIMARY KEY REFERENCES meetings (id) ON DELETE CASCADE,
    label       TEXT NOT NULL,          -- work | timepass
    subtype     TEXT,
    confidence  REAL,
    work_min    REAL,
    timepass_min REAL,
    reasons     TEXT,                   -- JSON list of plain-language reasons, with quotes where there are any
    stage       TEXT NOT NULL,          -- A (rules) | B (transcript check) | C (your correction)
    model_label TEXT,                   -- what MWB said before you corrected it, for the agreement count
    series      TEXT                    -- the normalised title, so a correction carries over to the series
);

CREATE TABLE IF NOT EXISTS api_log (
    id          INTEGER PRIMARY KEY,
    ts          TEXT NOT NULL,
    skill       TEXT,
    route       TEXT,                   -- api | local
    model       TEXT,
    chars_in    INTEGER,                -- what was sent, as a size only: the text itself is never kept here
    chars_out   INTEGER,
    seconds     REAL,
    ok          INTEGER
);

UPDATE meta SET value = '3' WHERE key = 'schema' AND value < '3';
