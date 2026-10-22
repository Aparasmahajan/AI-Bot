"""Transcripts (design §9.3): tidy whisper's lines, merge the two lanes into one timeline marked You and Them, and
import transcripts that Teams, Zoom, Google Meet or Webex already made, which costs no CPU and records nothing.

Import reads WebVTT (.vtt: Teams, Zoom, Webex), Word (.docx: Teams' "Download as .docx", Google Docs from Meet)
and plain text. Only the standard library is used: a .docx is a zip of XML."""
import difflib, re, zipfile
from pathlib import Path
from xml.etree import ElementTree

NON_SPEECH = re.compile(r'^\s*[\[(][^\])]*[\])]\s*$')         # [BLANK_AUDIO], (music), [Laughter]
HAS_WORD = re.compile(r'[A-Za-z0-9ऀ-ॿ]')               # Latin or Devanagari


def tidy(rows):
    """Drop non-speech markers and whisper's repeats; normalise hyphens. rows: (speaker, start, end, text)."""
    out, last = [], {}
    for speaker, start, end, text in rows:
        text = text.replace('‑', '-').strip()
        if not text or NON_SPEECH.match(text) or not HAS_WORD.search(text):
            continue
        if last.get(speaker) == text.lower():          # whisper can loop on steady noise
            continue
        last[speaker] = text.lower()
        out.append((speaker, start, end, text))
    return out


def drop_echo(rows, similar=0.7):
    """Without a headset the mic also hears the other side. A You line that overlaps a Them line in time and says
    nearly the same thing is that echo, so it goes."""
    them = [r for r in rows if r[0] == 'Them']
    keep = []
    for r in rows:
        if r[0] == 'You':
            for t in them:
                if r[1] < (t[2] or t[1]) + 1.5 and (r[2] or r[1]) + 1.5 > t[1] and \
                        difflib.SequenceMatcher(None, r[3].lower(), t[3].lower()).ratio() >= similar:
                    break
            else:
                keep.append(r)
        else:
            keep.append(r)
    return keep


def merge(rows):
    return sorted(drop_echo(tidy(rows)), key=lambda r: (r[1], r[0]))


# ---- import ------------------------------------------------------------------------------------------------------

_TS = r'(\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?'


def _secs(ts):
    parts = ts.replace(',', '.').split(':')
    return sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))


def parse_vtt(text):
    rows = []
    blocks = re.split(r'\n\s*\n', text.replace('\r\n', '\n'))
    for b in blocks:
        m = re.search(rf'({_TS})\s*-->\s*({_TS})', b)
        if not m:
            continue
        body = b[m.end():].split('\n', 1)[1] if '\n' in b[m.end():] else ''
        body = body.strip()
        if not body:
            continue
        speaker = 'Them'
        v = re.match(r'<v\s+([^>]+)>(.*?)(?:</v>)?$', body, re.S)
        if v:
            speaker, body = v.group(1).strip(), v.group(2)
        else:
            s = re.match(r'([^:\n]{2,40}):\s+(.*)', body, re.S)          # Zoom: "Name: text"
            if s:
                speaker, body = s.group(1).strip(), s.group(2)
        body = re.sub(r'<[^>]+>', '', body).replace('\n', ' ').strip()
        if body:
            rows.append((speaker, _secs(m.group(1)), _secs(m.group(3)), body))
    # Teams splits one person's turn into many cues: join neighbours from the same speaker
    joined = []
    for r in rows:
        if joined and joined[-1][0] == r[0] and r[1] - (joined[-1][2] or joined[-1][1]) < 2.0:
            p = joined[-1]
            joined[-1] = (p[0], p[1], r[2], f'{p[3]} {r[3]}')
        else:
            joined.append(r)
    return joined


def _paragraphs_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read('word/document.xml'))
    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    return [''.join(t.text or '' for t in p.iter(w + 't')).strip() for p in root.iter(w + 'p')]


def parse_paragraphs(paras):
    """Teams' .docx and similar text: a header line "Name   0:03" (or "0:03 Name"), then what they said."""
    head = re.compile(rf'^(?:(.+?)\s+({_TS})|({_TS})\s+(.+?))$')
    rows, cur = [], None
    for p in (x for x in paras if x):
        m = head.match(p)
        if m and len(p) < 80:
            name = (m.group(1) or m.group(5) or '').strip(' -:')
            ts = m.group(2) or m.group(4)
            cur = [name or 'Them', _secs(ts), None, []]
            rows.append(cur)
        elif cur is not None:
            cur[3].append(p)
        else:
            s = re.match(r'([^:]{2,40}):\s+(.*)', p)
            rows.append([s.group(1), float(len(rows)), None, [s.group(2)]] if s else ['Them', float(len(rows)), None, [p]])
    return [(r[0], r[1], r[2], ' '.join(r[3]).strip()) for r in rows if ' '.join(r[3]).strip()]


def parse_file(path):
    """[(speaker, start s, end s, text)] from a transcript file."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == '.docx':
        return parse_paragraphs(_paragraphs_docx(path))
    text = path.read_text(encoding='utf-8-sig', errors='replace')
    if ext == '.vtt' or text.lstrip().startswith('WEBVTT') or '-->' in text:
        return parse_vtt(text)
    return parse_paragraphs(text.splitlines())
