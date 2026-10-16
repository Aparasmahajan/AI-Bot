"""Dates are worked out by code, never by the model (P0-4, 13 Oct 2026: a model turned "by Friday" into the wrong
date). The model quotes what was said, "by Friday" or "end of next week", and resolve() turns it into a date counted
from the day of the meeting or the email. Anything it can't read stays as words, with no date."""
import datetime, re

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
SHORT_DAYS = {d[:3]: i for i, d in enumerate(DAYS)}
MONTHS = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct',
                                          'nov', 'dec'])}
NUMBERS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'ten': 10, 'a': 1}


def _upcoming(ref, weekday, include_today=False):
    ahead = (weekday - ref.weekday()) % 7
    if ahead == 0 and not include_today:
        ahead = 7
    return ref + datetime.timedelta(days=ahead)


def resolve(text, ref):
    """A datetime.date for phrases like "by Friday", "tomorrow", "next Monday", "16 Oct", "EOD", or None."""
    if not text:
        return None
    t = text.lower().strip()
    t = re.sub(r'[,.;]', ' ', t)
    if isinstance(ref, datetime.datetime):
        ref = ref.date()
    m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', t)
    if m:
        return datetime.date(*map(int, m.groups()))
    if re.search(r'\b(today|tonight|eod|end of (the )?day|this evening|by evening|aaj)\b', t):
        return ref
    if re.search(r'\bday after tomorrow\b', t):
        return ref + datetime.timedelta(days=2)
    if re.search(r'\btomorrow\b', t):
        return ref + datetime.timedelta(days=1)
    m = re.search(r'\bin (\d+|' + '|'.join(NUMBERS) + r') (day|days|week|weeks)\b', t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS[m.group(1)]
        return ref + datetime.timedelta(days=n * (7 if m.group(2).startswith('week') else 1))
    if re.search(r'\b(eow|end of (the )?week)\b', t):
        friday = _upcoming(ref, 4, include_today=True)
        return friday + datetime.timedelta(days=7) if 'next' in t else friday
    if re.search(r'\bnext week\b', t):
        return ref + datetime.timedelta(days=7 - ref.weekday())            # Monday of next week
    if re.search(r'\b(end of (the )?month|eom)\b', t):
        nxt = (ref.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        return nxt - datetime.timedelta(days=1)
    # "16 Oct", "October 16", "16th October 2026", "16/10" (day first, as in India)
    m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3})[a-z]*(?:\s+(\d{4}))?\b', t) or \
        re.search(r'\b([a-z]{3})[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?\b', t)
    if m:
        a, b, year = m.groups()
        day, mon = (a, b) if a.isdigit() else (b, a)
        if mon in MONTHS:
            y = int(year) if year else ref.year
            try:
                d = datetime.date(y, MONTHS[mon], int(day))
            except ValueError:
                return None
            return d if year or d >= ref - datetime.timedelta(days=60) else d.replace(year=y + 1)
    m = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b', t)
    if m:
        day, mon, year = m.groups()
        y = int(year) + (2000 if year and len(year) == 2 else 0) if year else ref.year
        try:
            return datetime.date(y, int(mon), int(day))
        except ValueError:
            return None
    m = re.search(r'\b(?:(this|next|coming|by|on|before|till|until)\s+)?'
                  r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
                  r'mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b', t)
    if m:
        day = _upcoming(ref, SHORT_DAYS[m.group(2)[:3]], include_today=m.group(1) == 'this')
        if m.group(1) == 'next' and day.isocalendar()[1] == ref.isocalendar()[1]:
            day += datetime.timedelta(days=7)               # "next Friday" said on Monday: the Friday after
        return day
    return None


def pretty(d):
    return f'{d:%a} {d.day} {d:%b}' if d else ''
