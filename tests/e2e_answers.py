"""Design P3 exit: "10 questions about your day answered with correct facts". A scratch database is seeded with a made
-up day (two meetings with notes, action items and labels, a dictation, and a calendar), then ten questions go
through the real answer path, via the API. Each answer must contain the right facts and cite only real tags.
Nothing touches your own history.

  .venv\\Scripts\\python.exe -I tests\\e2e_answers.py"""
import datetime, logging, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mwb import config                                          # noqa: E402
from mwb.llm.router import Router                               # noqa: E402
from mwb.skills.assist import Assist                            # noqa: E402
from mwb.store.db import Store                                  # noqa: E402


class Card:
    def __init__(self):
        self.text, self.note = '', ''

    def append(self, piece):
        self.text = '' if piece == '\x00restart' else self.text + piece

    def set_text(self, t):
        self.text = t

    def set_note(self, n):
        self.note = n

    def set_buttons(self, b):
        pass


class Cards:
    card_open = False

    def __init__(self):
        self.last = None

    def result(self, title, note=''):
        self.last = Card()
        return self.last

    def close_cards(self):
        pass


def seed(store):
    today = datetime.date.today()
    at = lambda h, m: datetime.datetime.combine(today, datetime.time(h, m)).isoformat()
    m1 = store.new_meeting(app_id='teams', app_name='Teams', title='Payments team sync', started=at(10, 0),
                           ended=at(10, 15), status='ready', source='recorded', language='en')
    store.add_segments(m1, [
        ('Them', 30, 40, 'Meera here. The Kafka consumer is still blocked; I have no access to the staging Kafka '
                         'cluster. I raised a ticket with DevOps.'),
        ('You', 50, 60, "I'll share the UAT build with Sanjay's team by Wednesday."),
        ('Them', 300, 310, "Dark mode won't make this sprint, so it moves to the next sprint.")])
    store.save_notes(m1, 'ready', ['Kafka access for staging is still blocked; DevOps ticket raised.',
                                   'UAT build goes to Sanjay\'s team this week.'],
                     ['Dark mode moves to the next sprint.'], [], 'api', 'test')
    due = today + datetime.timedelta(days=2)
    store.replace_actions(m1, [('You', "Share the UAT build with Sanjay's team", 'in two days', due.isoformat()),
                               ('Them', 'Escalate Kafka access with DevOps', 'today', today.isoformat())])
    store.save_label(m1, 'work', 'delivery', 0.95, None, None, ['title sounds like work'], 'A', 'payments team sync')
    m2 = store.new_meeting(app_id='teams', app_name='Teams', title='Friday fun quiz', started=at(16, 0),
                           ended=at(16, 30), status='ready', source='recorded', language='en')
    store.add_segments(m2, [('Them', 10, 20, 'Welcome to the quiz! First round is Bollywood songs.')])
    store.save_notes(m2, 'ready', ['A team quiz with music rounds.'], [], [], 'api', 'test')
    store.save_label(m2, 'timepass', 'games', 0.9, None, None, ['title sounds like timepass'], 'A', 'friday fun quiz')
    store.add_dictation(datetime.datetime.now(), 'Teams.exe', 'ask priya about the mtms release',
                        'Ask Priya about the MTMS release.', 800, 3.0, 1, 'caps', 'paste')
    return due


def main():
    logging.basicConfig(level=logging.WARNING)
    store = Store(os.path.join(tempfile.mkdtemp(), 'mwb.db'))
    due = seed(store)
    today = datetime.date.today()
    cfg = config.load()
    router = Router(cfg)
    cards = Cards()
    a = Assist(cfg, router, cards, None, store)
    soon = (datetime.datetime.now() + datetime.timedelta(hours=1)).replace(second=0, microsecond=0)
    a.calendar = lambda: [{'subject': 'Design review', 'organizer': 'Asha Rao', 'attendees': 'Dev Kumar; You',
                           'start': soon, 'end': soon + datetime.timedelta(minutes=30)}]
    questions = [
        ('What meetings did I have today?', ['payments', 'quiz']),
        ("What's my next meeting and who is in it?", ['design review', 'asha']),
        ('What are my open action items?', ['uat build']),
        ('What did they say about the Kafka access?', ['kafka', 'devops']),
        ('What was decided in the payments sync today?', ['dark mode']),
        ('Was the quiz today work or timepass?', ['timepass']),
        ('When is my UAT build action item due?', [f'{due:%A}'.lower()[:3]]),
        ('What did I dictate last?', ['mtms']),
        ('How long was the payments sync today?', ['15']),
        ("What's the difference between a process and a thread?", ['memory']),
    ]
    passed = 0
    for q, want in questions:
        a.last_answer_at, a.conversation = 0.0, []
        a._answer(q)
        text = cards.last.text
        flat = text.lower()
        ok = all(w in flat.replace('-', ' ') or w in flat.replace('-', '') for w in want) and 'removed: not found' not in flat
        passed += ok
        print(f'{"PASS" if ok else "FAIL"}  {q}\n      {" ".join(text.split())[:260]}\n      ({cards.last.note})')
    print(f'\n{passed} of {len(questions)} answered with the right facts (design: 10 of 10).')
    router.close()


if __name__ == '__main__':
    main()
