"""Forgetting (design §14, Phase 5): "Forget this meeting" and "Forget today" on the Today page remove the rows, any
audio and the journal entries together.

A forgotten meeting goes with its transcript, notes, action items and label (the database deletes those with it),
and any audio pieces still waiting. If that day already has a journal, it is written again without the meeting.
Forgetting a day removes its meetings, dictations, activity, voice notes and journal; the journal's Markdown file
goes to the Recycle Bin, since it is your file. The day is MWB's working day, 06:00 to 06:00."""
import datetime, logging, shutil
from pathlib import Path

from mwb import config, winapi
from mwb.skills.journal import bounds, day_of

log = logging.getLogger('mwb.forget')
AUDIO = config.LOCAL / 'audio'
BUSY = ('recording', 'transcribing')


def meeting(store, mid, journal=None):
    """True if there was such a meeting. journal: rewrites that day's journal, if it has one."""
    m = store.meeting(mid)
    if not m or m['status'] in BUSY:                # still recording or transcribing: it can go once it's ready
        return False
    store.run('DELETE FROM meetings WHERE id = ?', (mid,))
    shutil.rmtree(AUDIO / f'm{mid}', ignore_errors=True)
    log.info('meeting %d forgotten', mid)
    if journal is not None:
        day = day_of(datetime.datetime.fromisoformat(m['started']))
        if journal.made(day):
            journal.write(day, manual=True, from_page=True)
    return True


def day(store, day):
    """Forget everything MWB kept for one working day. Returns how many of each were removed. A call still being
    recorded or transcribed is kept; forget it once its transcript is ready."""
    s, e = (t.isoformat(timespec='seconds') for t in bounds(day))
    ids = [r['id'] for r in store.rows('SELECT id FROM meetings WHERE started >= ? AND started < ? AND status NOT IN '
                                       "('recording', 'transcribing')", (s, e))]
    for mid in ids:
        store.run('DELETE FROM meetings WHERE id = ?', (mid,))
        shutil.rmtree(AUDIO / f'm{mid}', ignore_errors=True)
    counts = {'meetings': len(ids)}
    for table, col in (('dictations', 'ts'), ('activity', 'started'), ('journal_notes', 'ts')):
        counts[table] = store.rows(f'SELECT COUNT(*) n FROM {table} WHERE {col} >= ? AND {col} < ?', (s, e))[0]['n']
        store.run(f'DELETE FROM {table} WHERE {col} >= ? AND {col} < ?', (s, e))
    j = store.rows('SELECT path FROM journals WHERE day = ?', (day.isoformat(),))
    if j:
        if j[0]['path'] and Path(j[0]['path']).exists():
            winapi.recycle(j[0]['path'])
        store.run('DELETE FROM journals WHERE day = ?', (day.isoformat(),))
    counts['journal'] = len(j)
    log.info('day %s forgotten: %s', day, counts)            # counts only, never what was said
    return counts
