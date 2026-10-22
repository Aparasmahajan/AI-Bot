"""Clean-up rules for dictation (design §9.1): plain code, under 5 ms, no model. Parakeet already writes punctuation
and capitals; these rules drop fillers, collapse stutters, apply "scratch that", turn spoken commands into layout,
and apply the personal dictionary. Each rule is small on purpose, so a surprise is easy to trace."""
import re
from pathlib import Path

FILLERS = r'(?:u+m+|u+h+m*|e+r+m+|a+h+|h+m+|m+h*m+)'
# A piece that starts with one of these words continues the previous piece's sentence: the pause was mid-sentence.
CONTINUES = {'and', 'or', 'because', 'which', 'that', 'to', 'of', 'with', 'for', 'than', 'in', 'on', 'at', 'from',
             'into', 'about', 'as', 'if', 'when', 'while', 'where', 'who', 'whose', 'is', 'are', 'was', 'were'}
STUTTER_KEEP = {'that', 'had', 'is', 'very', 'no', 'bye', 'ha'}     # doubled on purpose often enough
PUNCT_WORDS = [(r'question mark', '?'), (r'exclamation (?:mark|point)', '!'), (r'full stop', '.'), (r'comma', ',')]


def load_dictionary(files):
    """[(compiled pattern, replacement)] from "heard -> wanted" lines; later files win."""
    rules = {}
    for f in files:
        for line in Path(f).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '->' not in line:
                continue
            heard, wanted = (s.strip() for s in line.split('->', 1))
            if heard and wanted:
                rules[heard.lower()] = wanted
    out = []
    for heard, wanted in sorted(rules.items(), key=lambda kv: -len(kv[0])):    # longest first: "v s code" before "vs"
        words = [re.escape(w) for w in re.split(r'[\s.]+', heard) if w]
        out.append((re.compile(r'(?<![\w-])' + r'[\s.,]*'.join(words) + r'(?![\w-])', re.I), wanted))
    return out


def join_pieces(pieces):
    """Join the texts of the audio pieces. A piece cut at a mid-sentence pause gets a period it shouldn't have."""
    text = ''
    for p in (p.strip() for p in pieces):
        if not p:
            continue
        first = re.match(r"[A-Za-z']+", p)
        if text.endswith('.') and first and first.group().lower() in CONTINUES and not text.endswith('..'):
            text = text[:-1] + ' ' + p[0].lower() + p[1:]
        else:
            text = f'{text} {p}' if text else p
    return text


def _drop_fillers(t):
    t = re.sub(rf'(^|[.?!]\s+){FILLERS}\b[,.]?\s*', r'\1', t, flags=re.I)        # at a sentence start
    t = re.sub(rf',?\s*\b{FILLERS}\b(\s*[.?!])', r'\1', t, flags=re.I)           # before a sentence end
    return re.sub(rf',?\s*\b{FILLERS}\b,?', '', t, flags=re.I)                   # mid-sentence, with its commas


def _collapse_stutters(t):
    def one(m):
        return m.group(1) if m.group(1).lower() not in STUTTER_KEEP else m.group(0)
    return re.sub(r"\b([A-Za-z']+)(?:,?\s+\1\b)+", one, t, flags=re.I)


def _scratch_that(t):
    """"Send it Friday, scratch that, Thursday" -> "Send it Thursday": the words after replace as many words before.
    Said at the end, it removes the sentence before it."""
    while True:
        m = re.search(r'[,.]?\s*\bscratch that\b[,.]?\s*', t, flags=re.I)
        if not m:
            return t
        before, after = t[:m.start()], t[m.end():]
        sentence_start = max(before.rfind('. '), before.rfind('? '), before.rfind('! '), before.rfind('\n'))
        head, last = before[:sentence_start + 1], before[sentence_start + 1:]
        clause = re.match(r'[^.?!\n]*', after).group()
        n = len(clause.split())
        if not n:
            t = (head.rstrip() + ' ' + after.lstrip(' ,.')).strip()
            continue
        words = last.split()
        kept = ' '.join(words[:max(0, len(words) - n)]).rstrip(',')
        t = (head + (' ' if head and not head.endswith('\n') else '') + (kept + ' ' if kept else '') + after).strip()


def _spoken_commands(t):
    t = re.sub(r'[,.]?\s*\bnew paragraph\b[,.:]?\s*', '\n\n', t, flags=re.I)
    t = re.sub(r'[,.]?\s*\b(?:new|next) line\b[,.:]?\s*', '\n', t, flags=re.I)
    t = re.sub(r'(^|,?\s*)\bbullet(?: point)?\b[,.:]?\s*',     # keeps the period of the line before
               lambda m: '- ' if not m.group(1).strip(' ,.') and m.start() == 0 else '\n- ', t, flags=re.I)
    for words, mark in PUNCT_WORDS:
        t = re.sub(rf'[,.]?\s*\b{words}\b[,.]?', mark, t, flags=re.I)
    return t


def _tidy(t):
    t = t.replace('‑', '-').replace(' ', ' ')
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r' *\n *', '\n', t)
    t = re.sub(r' +([,.?!:;])', r'\1', t)
    t = re.sub(r',+([.?!])', r'\1', t)
    t = re.sub(r'([,.?!])\1+', r'\1', t)
    t = re.sub(r'(?m)^[,.;:] *', '', t)
    t = re.sub(r'(?m)^(- .*?)\.$', r'\1', t)            # a bullet is not a sentence
    t = re.sub(r'(^(?:- )?|[.?!]\s+|\n(?:- )?)([a-z])', lambda m: m.group(1) + m.group(2).upper(), t)
    return t.strip(' ,')


def clean(pieces, dictionary=()):
    """The finished text for a list of piece texts."""
    t = join_pieces(pieces)
    if not t:
        return ''
    t = _drop_fillers(t)
    t = _collapse_stutters(t)
    t = _scratch_that(t)
    t = _spoken_commands(t)
    for pattern, wanted in dictionary:
        t = pattern.sub(wanted, t)
    t = _tidy(t)
    return '' if not re.search(r'\w', t) else t
