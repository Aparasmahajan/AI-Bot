"""P0-4, the first sync check (design §12.7, §17). Ten saved MWB tasks go through the API and through the local
fallback with the same prompts. For each answer it records the time to the first word and in total, the tokens, and
automatic checks: the format, the facts that must appear, nothing invented. It also writes a blind review page
(design §12: you score the answers without knowing which route wrote which).

  .venv\\Scripts\\python.exe -I docs\\bench\\p0_4_sync_check.py                   the Groq routes (needs the saved key)
  .venv\\Scripts\\python.exe -I docs\\bench\\p0_4_sync_check.py --routes local    Qwen3.5 2B and 4B (needs ~3 GB free)
  options: --routes groq-120b,local-2b,...   --tasks answer,journal,...   --backend cpu|vulkan

Every prompt is made up for this test; no real work text is sent anywhere. The Groq key comes from Windows
Credential Manager and is never printed or saved. Answers are merged into docs\\bench\\p0_4\\answers.json, and
docs\\bench\\p0_4\\review.html is rebuilt from all of them."""
import argparse, ctypes, ctypes.wintypes as wt, datetime, html, json, os, random, re, statistics, subprocess, sys, \
    time, urllib.request
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, HERE]
from mwb import credentials                     # noqa: E402
from mwb.llm.client import Connection           # noqa: E402
from mwb.llm.providers import GROQ              # noqa: E402
import code_test                                # noqa: E402  (the 5 coding tasks of 12 Oct)

OUT = os.path.join(HERE, 'p0_4')
LLAMA = os.path.join(os.environ['USERPROFILE'], 'Tools', 'llamacpp')
SYSTEM = ("You are MWB, a work assistant on a software engineer's Windows laptop in India. Follow the requested "
          "format exactly. Use only facts from the input: never invent names, numbers, dates, ticket IDs or commit "
          "IDs. Write in clear, plain English.")

ROUTES = {      # API routes send reasoning_effort; local routes run Qwen3.5 with thinking off
    'groq-120b': dict(kind='api', model='openai/gpt-oss-120b', extra={'reasoning_effort': 'low'}),
    'groq-120b-medium': dict(kind='api', model='openai/gpt-oss-120b', extra={'reasoning_effort': 'medium'}),
    'groq-20b': dict(kind='api', model='openai/gpt-oss-20b', extra={'reasoning_effort': 'low'}),
    'local-2b': dict(kind='local', model='Qwen3.5-2B-Q4_K_M.gguf', need_gb=1.25 + 0.75),
    'local-4b': dict(kind='local', model='Qwen3.5-4B-Q4_K_M.gguf', need_gb=2.42 + 0.75),
}
GROUPS = {'groq': ['groq-120b', 'groq-20b', 'groq-120b-medium'], 'local': ['local-2b', 'local-4b']}
REVIEWED = ['groq-120b', 'groq-20b', 'local-2b', 'local-4b']     # the blind review compares these


# ---------- checks: each returns True or False for one answer ----------

def has(*patterns):
    """Every pattern (a regex, case-insensitive) appears in the answer."""
    return lambda t: all(re.search(p, t, re.I) for p in patterns)


def lacks(*patterns):
    return lambda t: not any(re.search(p, t, re.I) for p in patterns)


def headings(*names):
    return lambda t: all(re.search(rf'^\s*#+\s*{re.escape(n)}\s*$', t, re.I | re.M) for n in names)


def section(text, name):
    """The text under a '## name' heading, up to the next heading."""
    m = re.search(rf'^\s*#+\s*{re.escape(name)}\s*$(.*?)(?=^\s*#+\s|\Z)', text, re.I | re.M | re.S)
    return m.group(1) if m else ''


def json_of(text):
    """The JSON object in an answer, allowing for a ```json fence around it; None if there isn't a valid one."""
    m = re.search(r'\{.*\}', text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None


def words(text):
    return len(re.findall(r"[\w'’-]+", text))


def english(text):
    """Less than 2 % of the letters are Devanagari."""
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum('ऀ' <= c <= 'ॿ' for c in letters) / len(letters) < 0.02


def sentences(text):
    return [s for s in re.split(r'(?<=[.!?\]])\s+(?=[A-Z])', text.strip()) if s.strip()]


def runs_with(tests):
    """The answer's code block, run with these tests in a separate process, passes."""
    return lambda t: '```' in t and code_test.passes(code_test.extract_code(t), tests)


def label_ok(expected):
    def check(t):
        j = json_of(t)
        return (isinstance(j, dict) and j.get('label') == expected and isinstance(j.get('confidence'), (int, float))
                and 0 <= j['confidence'] <= 1 and isinstance(j.get('reasons'), list) and 1 <= len(j['reasons']) <= 3)
    return check


@dataclass
class Task:
    id: str
    title: str
    prompt: str
    max_tokens: int
    checks: list = field(default_factory=list)      # (what is checked, function)


NOTES_FORMAT = ('Format, exactly:\n## Summary\n- 2 to 4 bullets\n## Decisions\n- one bullet per decision, or "- None"\n'
                '## Action items\n- [Owner] what (due: when, or "no date")')

TASKS = [
    Task('meeting_en', 'Meeting notes, English call', f"""Write notes for this meeting.

{NOTES_FORMAT}

Transcript (Teams, Tue 13 Oct 2026, 10:00-10:15):
Priya: Morning all. Quick one today. Arjun, where are we on the login timeout bug?
Arjun: PAY-412. I found it: the session refresh runs after the token has already expired. The fix is ready locally; I'll raise the PR today and it should be merged by Wednesday.
Priya: Good. Me, can you review Arjun's PR?
Me: Yes, I'll review it as soon as it's up. I'm also preparing the UAT build; I'll share it with Sanjay's team by Wednesday.
Priya: Meera, the Kafka consumer?
Meera: Still blocked. I don't have access to the staging Kafka cluster. I raised a ticket with DevOps, but nobody has picked it up.
Priya: I'll escalate that with DevOps today. Without Kafka we can't test the order events.
Meera: Thanks. Once I have access it's about two days of work.
Priya: One more thing: dark mode. We won't make it this sprint, so let's move it to the next sprint. Everyone okay?
Arjun: Fine by me.
Me: Agreed.
Priya: Okay. The release candidate is still planned for Thursday. Next sync is Friday at 11. Thanks, everyone.""", 700, [
        ('three headings', headings('Summary', 'Decisions', 'Action items')),
        ('ticket PAY-412 kept', has(r'PAY-412')),
        ('dark mode moved to next sprint, under Decisions', lambda t: re.search(r'dark mode', section(t, 'Decisions'), re.I)),
        ('owners Arjun, Priya and Me in action items',
         lambda t: all(re.search(n, section(t, 'Action items')) for n in (r'Arjun', r'Priya', r'\bMe\b|\bYou\b'))),
        ('dates Wednesday, Thursday, Friday', has(r'Wednesday', r'Thursday', r'Friday')),
        ('Kafka access blocker', has(r'Kafka', r'access')),
    ]),
    Task('meeting_hinglish', 'Meeting notes, Hindi and English call', f"""Write notes for this meeting, in English.

{NOTES_FORMAT}

The transcript mixes Hindi and English; the speech-to-text wrote Hindi in Devanagari.
Transcript (Teams, Tue 13 Oct 2026, 16:00-16:20):
Rohit: Hi everyone. आज का agenda छोटा है: staging deployment और payment gateway वाला issue.
Neha: Payment gateway में timeout आ रहा है। मैंने logs देखे, problem retry logic में है, हर retry पे नया token बन रहा है। मैं Thursday तक fix कर दूंगी।
Rohit: ठीक है। Deployment का क्या status है?
Me: Staging पे deployment Friday को करेंगे। उससे पहले मुझे database migration script review करनी है, वो मैं कल तक कर दूंगा।
Rohit: Perfect. Client demo Monday को है, इसलिए Friday की deadline miss नहीं होनी चाहिए।
Neha: एक और बात, QA team को नए test cases चाहिए। मैं आज शाम तक भेज दूंगी।
Rohit: और हाँ, logging library का upgrade अभी नहीं करेंगे, demo के बाद देखेंगे।
Me: Agreed.
Rohit: Okay, next sync Wednesday को चार बजे। Thanks.""", 700, [
        ('three headings', headings('Summary', 'Decisions', 'Action items')),
        ('written in English', english),
        ('Neha owns the timeout fix by Thursday', lambda t: re.search(r'Neha.*(timeout|retry|payment).*Thursday|Neha.*Thursday',
                                                                      section(t, 'Action items'), re.I)),
        ('Me reviews the migration script', lambda t: re.search(r'(\bMe\b|\bYou\b).*migration', section(t, 'Action items'), re.I)),
        ('Friday deployment and Monday demo', has(r'Friday', r'Monday')),
        ('test cases to QA', has(r'test cases?', r'QA')),
        ('logging upgrade postponed', has(r'logging')),
    ]),
    Task('label_work', 'Work or Timepass: a planning call', """Label this call Work or Timepass. Reply with JSON only:
{"label": "work" or "timepass", "confidence": a number from 0 to 1, "reasons": [one to three short strings]}

Call: app Microsoft Teams; calendar entry "Sprint 43 planning" (organiser Priya, 7 invitees); Tue 13 Oct 2026, 11:00-11:45; 6 people spoke.
First minute of the transcript: "Okay, let's go through the backlog. We have 34 story points of carry-over from last sprint. The rate limiter for the public API is the top item, then the invoice export bug..." """, 200, [
        ('valid JSON, label work, confidence 0-1, 1-3 reasons', label_ok('work')),
    ]),
    Task('label_timepass', 'Work or Timepass: a chat with friends', """Label this call Work or Timepass. Reply with JSON only:
{"label": "work" or "timepass", "confidence": a number from 0 to 1, "reasons": [one to three short strings]}

Call: app WhatsApp; no calendar entry; Tue 13 Oct 2026, 13:10-13:35; 3 people spoke.
First minute of the transcript: "bhai kal ka match dekha? last over mein kya six maara yaar... haan haan, aur weekend pe movie ka plan hai kya? Saturday ko chalte hain na..." """, 200, [
        ('valid JSON, label timepass, confidence 0-1, 1-3 reasons', label_ok('timepass')),
    ]),
    Task('email_explain', 'Explain an email', """Explain this email. Today is Tuesday 13 October 2026. Reply with JSON only:
{"summary": "two short lines", "they_want": ["..."], "deadlines": [{"what": "...", "date": "YYYY-MM-DD"}], "people": ["..."], "reply_options": ["...", "..."]}

From: Vikram Rao (client PM)
To: Me; Cc: Priya
Subject: Review next week: docs and load test

Hi,
Ahead of our review next Tuesday, could you send the API documentation and the latest load test report? Please also confirm whether the rate limit is applied per user or per tenant; our security team is asking. If the report isn't final, a draft is fine, but we need it by Friday so we can go through it before the review.
Thanks,
Vikram""", 400, [
        ('valid JSON with the five fields',
         lambda t: isinstance(json_of(t), dict) and {'summary', 'they_want', 'deadlines', 'people', 'reply_options'} <= set(json_of(t))),
        ('Friday is 2026-10-16', has(r'2026-10-16')),
        ('asks: docs, load test report, rate limit', has(r'doc', r'load test', r'rate limit')),
        ('Vikram among the people', has(r'Vikram')),
    ]),
    Task('email_draft', 'Draft a reply in my style', """Draft my reply to this email. My point, as I said it: "tell him I'll share the build by Wednesday, and I still need Kafka access from DevOps; without it the integration is blocked". My style: greeting "Hi <first name>,", short paragraphs, sign-off "Thanks,". Write only the email body, under 120 words. Promise nothing I didn't say.

From: Sanjay Mehta
Subject: UAT build and Kafka integration
Hi,
When can we expect the UAT build? And is the Kafka integration done on your side?
Regards,
Sanjay""", 300, [
        ('greets Sanjay', has(r'^\s*Hi Sanjay,')),
        ('build by Wednesday', has(r'Wednesday')),
        ('Kafka access from DevOps, integration blocked', has(r'Kafka', r'access', r'DevOps', r'block')),
        ('signs off "Thanks,"', has(r'Thanks,\s*$|Thanks,\s*\n')),
        ('under 120 words', lambda t: words(t) < 120),
        ("doesn't claim the integration is done", lacks(r'integration (is|has been) (done|complete)')),
    ]),
    Task('code_explain', 'Explain code and fix it', """Explain this Python code. Format exactly:
## What it does
(2 sentences)
## Problems
- bullets
## Better version
(one ```python code block)

```python
def add_tag(tag, tags=[]):
    tags.append(tag)
    return tags

def average(nums):
    total = 0
    for i in range(1, len(nums)):
        total += nums[i]
    return total / len(nums)
```""", 900, [
        ('three headings', headings('What it does', 'Problems', 'Better version')),
        ('finds the shared mutable default', has(r'mutable|default (list|argument|value)|shared')),
        ('finds that the first number is skipped', has(r'first (element|item|number|value)|index 0|range\(1|off.by.one|skip')),
        ('finds the empty-list division', has(r'empty|zero')),
        ('its better version passes tests', lambda t: runs_with(
            "assert add_tag('a') == ['a']\nassert add_tag('b') == ['b']\n"
            "assert average([2, 4]) == 3\nassert average([5]) == 5\n")(section(t, 'Better version'))),
    ]),
    Task('dictation_cleanup', 'Clean up dictation', """Clean up this dictated text: remove filler words, repeated words and false starts, and fix punctuation and capitalisation. Keep my words and meaning; add nothing. Reply with the cleaned text only.

um so basically i wanted to uh tell you that the the deployment is moved to friday because uh the qa team found two issues in the payment flow and uh we need to fix them first so yeah um please don't don't share the build with the client before that okay""", 200, [
        ('fillers and repeats gone', lacks(r'\bum\b', r'\buh\b', r'\bthe the\b', r"don't don't")),
        ('facts kept', has(r'Friday', r'QA', r'payment', r'two issues', r'client')),
        ('no preamble', lacks(r'^\s*(here|sure|cleaned)')),
        ('25 to 50 words', lambda t: 25 <= words(t) <= 50),
    ]),
    Task('journal', 'End-of-day journal with citations', """Write my end-of-day journal from these events: 3 to 6 sentences of plain prose, in the first person. End every sentence with the IDs of the events it uses, in square brackets, like [E1] or [E2, E3]. Mention each commit by its exact ID. Mention timepass calls only as a count: no app, time or length. Add nothing that isn't in the events: no reasons, attachments, results or plans.

Events, Tue 13 Oct 2026:
E1 10:42 commit 3f9c2a1 in AI-Bot (dev): "Add API key window and Credential Manager storage"
E2 10:58 commit b7d41e0 in AI-Bot (dev): "P0-1 two-lane capture check"
E3 10:30-10:47 call, Teams, label Work, 16 min; notes: decided to move dark mode to the next sprint
E4 12:15 email sent to Vikram Rao, subject "API docs and load test report"
E5 13:10-13:35 call, WhatsApp, label Timepass
E6 dictation: 6 times, 412 words in total""", 400, [
        ('every sentence cites events', lambda t: bool(sentences(t)) and all(re.search(r'\[E\d+(,\s*E\d+)*\]\W*$', s) for s in sentences(t))),
        ('3 to 6 sentences', lambda t: 3 <= len(sentences(t)) <= 6),
        ('both commit IDs exact', has(r'\b3f9c2a1\b', r'\bb7d41e0\b')),
        ('no invented commit IDs', lambda t: set(re.findall(r'\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b', t)) <= {'3f9c2a1', 'b7d41e0'}),
        ('no timepass details', lacks(r'WhatsApp', r'13:10', r'13:35', r'25\s*min')),
    ]),
    Task('answer', 'Quick answer', "In two sentences: what is the difference between a process and a thread?", 150, [
        ('at most 3 sentences', lambda t: len(sentences(t)) <= 3),
        ('mentions memory', has(r'memory|address space')),
        ('under 80 words', lambda t: words(t) < 80),
    ]),
]
TASK_BY_ID = {t.id: t for t in TASKS}


# ---------- running ----------

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [('dwLength', wt.DWORD), ('dwMemoryLoad', wt.DWORD)] + [
        (n, ctypes.c_ulonglong) for n in ('ullTotalPhys', 'ullAvailPhys', 'ullTotalPageFile', 'ullAvailPageFile',
                                          'ullTotalVirtual', 'ullAvailVirtual', 'ullAvailExtendedVirtual')]


def available_gb():
    m = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2**30


def seconds(text):
    """'1m2.5s', '7.66s' or '120ms' (Groq's rate-limit reset headers) -> seconds."""
    total = 0.0
    for num, unit in re.findall(r'([\d.]+)(ms|h|m|s)', text or ''):
        total += float(num) * {'ms': 0.001, 'h': 3600, 'm': 60, 's': 1}[unit]
    return total


def ask(conn, model, prompt, max_tokens, temperature=0.3, system=SYSTEM, **extra):
    """One answer, waiting out rate limits: Groq's free tier allows a few thousand tokens a minute."""
    messages = ([{'role': 'system', 'content': system}] if system else []) + [{'role': 'user', 'content': prompt}]
    for attempt in range(6):
        r = conn.chat(model, messages, max_tokens=max_tokens, temperature=temperature, **extra)
        if r.ok or r.status not in (429, 500, 502, 503):
            break
        wait = r.retry_after or seconds(r.rate.get('x-ratelimit-reset-tokens')) or 5 * (attempt + 1)
        print(f'      {r.status}, waiting {wait:.0f} s', flush=True)
        time.sleep(wait + 0.5)
    left = r.rate.get('x-ratelimit-remaining-tokens')
    if left and left.isdigit() and int(left) < 3000:                    # pace before the next request
        time.sleep(seconds(r.rate.get('x-ratelimit-reset-tokens')) + 0.5)
    return r


TYPOGRAPHY = {0x2010: '-', 0x2011: '-', 0x00A0: ' ', 0x202F: ' '}


def normalize(text):
    """MWB's clean-up of model output before use: gpt-oss writes IDs such as PAY-412 with a non-breaking hyphen
    (U+2011), which breaks search and links, and puts narrow no-break spaces in times."""
    return text.translate(TYPOGRAPHY)


def check(fn, text):
    try:
        return bool(fn(text))
    except Exception:                   # a malformed answer fails the check; it must not stop the run
        return False


def score(task, text, ok=True):
    checks = [(name, ok and check(fn, normalize(text))) for name, fn in task.checks]
    return dict(checks=checks, passed=sum(c for _, c in checks), of=len(checks),
                needed_cleanup=normalize(text) != text)


def record(task, route, r):
    return dict(task=task.id, route=route, ok=r.ok, error=r.error, text=r.text, first_word_s=r.first_word_s,
                total_s=round(r.total_s, 2), prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
                reasoning_tokens=r.reasoning_tokens, finish=r.finish, server=r.server, **score(task, r.text, r.ok))


def run_tasks(conn, route, model, tasks, extra, code_tasks):
    rows = []
    reasoning = {'low': 1000, 'medium': 2000}.get(extra.get('reasoning_effort'), 0)   # gpt-oss reasons inside max_tokens
    for task in tasks:
        r = ask(conn, model, task.prompt, task.max_tokens + reasoning, **extra)
        row = record(task, route, r)
        rows.append(row)
        fw = f'{r.first_word_s:.2f}' if r.first_word_s else '-'
        print(f'  {route:17} {task.id:18} {"ok " if r.ok else "ERR"} first word {fw:>6} s  total {r.total_s:6.2f} s  '
              f'checks {row["passed"]}/{row["of"]}  {r.completion_tokens} tokens'
              + (f' ({r.reasoning_tokens} reasoning)' if r.reasoning_tokens else '')
              + (f'  {r.error}' if r.error else ''), flush=True)
    for name, prompt, tests in (code_test.TASKS if code_tasks else []):
        r = ask(conn, model, prompt + code_test.PROMPT_TAIL, 600 + reasoning, temperature=0, system=None, **extra)
        ok = r.ok and code_test.passes(code_test.extract_code(r.text), tests)
        rows.append(dict(task='code:' + name, route=route, ok=r.ok, error=r.error, text=r.text,
                         first_word_s=r.first_word_s, total_s=round(r.total_s, 2), completion_tokens=r.completion_tokens,
                         reasoning_tokens=r.reasoning_tokens, checks=[('hidden tests pass', ok)], passed=int(ok), of=1))
        print(f'  {route:17} code:{name:13} {"PASS" if ok else "FAIL"}  total {r.total_s:6.2f} s', flush=True)
    return rows


def run_api(routes, tasks, code_tasks):
    stored = credentials.read(credentials.api_key_target('groq'))
    if not stored:
        sys.exit('No Groq key in Credential Manager: double-click "Set API key.cmd" first.')
    conn = Connection(GROQ.base, stored.secret)
    t = time.perf_counter()
    status, _ = conn.get('/models')
    cold = time.perf_counter() - t
    warm = []
    for _ in range(5):
        t = time.perf_counter()
        conn.get('/models')
        warm.append(time.perf_counter() - t)
    net = dict(first_request_s=round(cold, 3), kept_alive_median_s=round(statistics.median(warm), 3), status=status)
    print(f'network: first request {cold:.2f} s (connect, TLS, answer); then {statistics.median(warm):.2f} s each '
          f'on the kept-alive connection', flush=True)
    rows = []
    for route in routes:
        spec = ROUTES[route]
        rows += run_tasks(conn, route, spec['model'], tasks, spec['extra'], code_tasks and route != 'groq-120b-medium')
    conn.close()
    return rows, net


def run_local(routes, tasks, backend):
    rows = []
    for route in routes:
        spec = ROUTES[route]
        free = available_gb()
        if free < spec['need_gb']:
            print(f'  {route}: skipped, {free:.1f} GB free and it needs {spec["need_gb"]:.1f} GB. '
                  'Close some windows and run it again.', flush=True)
            continue
        exe = os.path.join(LLAMA, backend, 'llama-server.exe')
        port = 8093
        proc = subprocess.Popen([exe, '-m', os.path.join(LLAMA, 'models', spec['model']), '-t', '4', '-c', '4096',
                                 '--host', '127.0.0.1', '--port', str(port),
                                 '--chat-template-kwargs', '{"enable_thinking":false}'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        try:
            t0 = time.time()
            while time.time() - t0 < 180:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as r:
                        if json.load(r).get('status') == 'ok':
                            break
                except OSError:
                    time.sleep(0.5)
            print(f'  {route}: {backend} server ready in {time.time() - t0:.1f} s, {free:.1f} GB was free', flush=True)
            conn = Connection(f'http://127.0.0.1:{port}/v1')
            rows += run_tasks(conn, route if backend == 'cpu' else f'{route}-{backend}', 'local', tasks,
                              {'top_p': 0.8, 'top_k': 20, 'presence_penalty': 0}, False)
            conn.close()
        finally:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
    return rows


# ---------- results and the review page ----------

def save(rows, net):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, 'answers.json')
    data = {'runs': [], 'answers': []}
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    done = {(r['task'], r['route']) for r in rows}
    data['answers'] = [a for a in data['answers'] if (a['task'], a['route']) not in done] + rows
    data['runs'].append(dict(at=datetime.datetime.now().isoformat(timespec='seconds'), network=net,
                             routes=sorted({r['route'] for r in rows}), free_gb=round(available_gb(), 2)))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data


def summary(data):
    by_route = {}
    for a in data['answers']:
        by_route.setdefault(a['route'], []).append(a)
    print('\nroute              tasks  checks  first word (median)  total (median)  coding')
    for route, rows in by_route.items():
        tasks = [r for r in rows if not r['task'].startswith('code:')]
        code = [r for r in rows if r['task'].startswith('code:')]
        fw = [r['first_word_s'] for r in tasks if r['first_word_s']]
        tot = [r['total_s'] for r in tasks if r['ok']]
        print(f'{route:18} {len(tasks):5}  {sum(r["passed"] for r in tasks):3}/{sum(r["of"] for r in tasks):<3} '
              f'{statistics.median(fw) if fw else 0:12.2f} s {statistics.median(tot) if tot else 0:13.2f} s   '
              + (f'{sum(r["passed"] for r in code)}/{len(code)}' if code else '-'))


def write_machine_file(data):
    """P0-6 left api_first_words_s empty: fill it with the median first word of the quick tasks on gpt-oss-120b."""
    quick = [a['first_word_s'] for a in data['answers'] if a['route'] == 'groq-120b' and a['first_word_s']
             and a['task'] in ('answer', 'dictation_cleanup', 'label_work', 'label_timepass')]
    path = os.path.join(os.environ['LOCALAPPDATA'], 'MWB', 'machine', '530285546f.toml')
    if not quick or not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        text = f.read()
    line = (f'api_first_words_s = {statistics.median(quick):.2f}   # Groq gpt-oss-120b, reasoning low, median of '
            f'{len(quick)} quick tasks, {datetime.date.today():%d %b} (P0-4)')
    text = re.sub(r'^# api_first_words_s:.*$|^api_first_words_s = .*$', line.replace('\\', r'\\'), text, flags=re.M)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'machine file: {line}')


def write_review(data):
    """A blind review page: per task, the reviewed routes' answers in a shuffled order, labelled A, B, C..."""
    answers = {(a['task'], a['route']): a for a in data['answers']}
    letters, sections = {}, []
    for n, task in enumerate(TASKS, 1):
        present = [r for r in REVIEWED if (task.id, r) in answers]
        if len(present) < 2:
            continue
        order = present[:]
        random.Random(f'{task.id}:{",".join(present)}').shuffle(order)
        cards = []
        for letter, route in zip('ABCD', order):
            a = answers[(task.id, route)]
            letters[f'{task.id}:{letter}'] = route
            fw = f'{a["first_word_s"]:.1f} s to first word, ' if a['first_word_s'] else ''
            cards.append(f'''<article class="ans" data-key="{task.id}:{letter}">
  <header><span class="letter">{letter}</span><span class="who">{html.escape(route)} · {fw}{a["total_s"]:.1f} s in all · checks {a["passed"]}/{a["of"]}</span></header>
  <pre>{html.escape(a["text"] or a["error"])}</pre>
  <div class="stars" role="group" aria-label="Score answer {letter}">{''.join(f'<button data-v="{v}" aria-label="{v} of 5">{v}</button>' for v in range(1, 6))}</div>
</article>''')
        sections.append(f'''<section class="task" data-task="{task.id}">
  <h2><span class="n">{n}</span>{html.escape(task.title)}</h2>
  <details><summary>Show the prompt</summary><pre class="prompt">{html.escape(task.prompt)}</pre></details>
  <div class="answers">{''.join(cards)}</div>
</section>''')
    data['review_letters'] = letters
    with open(os.path.join(OUT, 'answers.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    page = REVIEW_PAGE.replace('{{sections}}', '\n'.join(sections)).replace(
        '{{date}}', f'{datetime.date.today():%d %B %Y}')
    with open(os.path.join(OUT, 'review.html'), 'w', encoding='utf-8') as f:
        f.write(page)


REVIEW_PAGE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blind Review</title>
<style>
:root{--paper:#F3F5F8;--sheet:#FFFFFF;--ink:#0E1726;--ink-2:#465267;--ink-3:#66738A;--rule:#D3D9E3;--wash:#EDF1F7;
 --cobalt:#2148C9;--cobalt-wash:#E3E9FB;--ok:#21734B;--ok-wash:#DDF2E6}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#06122A;--sheet:#0A1A36;--ink:#E4EBF6;
 --ink-2:#A9B7CF;--ink-3:#8494B2;--rule:#22416F;--wash:#0F264C;--cobalt:#8FB2FF;--cobalt-wash:#14306A;--ok:#70D49C;--ok-wash:#123526}}
:root[data-theme="dark"]{--paper:#06122A;--sheet:#0A1A36;--ink:#E4EBF6;--ink-2:#A9B7CF;--ink-3:#8494B2;--rule:#22416F;
 --wash:#0F264C;--cobalt:#8FB2FF;--cobalt-wash:#14306A;--ok:#70D49C;--ok-wash:#123526}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 16px 80px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.01em}
.lede{color:var(--ink-2);margin:0 0 18px;max-width:760px}
.bar{position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:10px 0;
 background:var(--paper);border-bottom:1px solid var(--rule);margin-bottom:22px}
.bar button{font:inherit;padding:7px 14px;border-radius:8px;border:1px solid var(--rule);background:var(--sheet);color:var(--ink);cursor:pointer}
.bar button.primary{background:var(--cobalt);border-color:var(--cobalt);color:#fff}
.bar .progress{color:var(--ink-3);font-size:13px;margin-left:auto}
.task{margin:0 0 34px}
.task h2{font-size:18px;margin:0 0 8px;display:flex;align-items:center;gap:10px}
.task h2 .n{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:7px;background:var(--cobalt-wash);color:var(--cobalt);font-size:13px}
details{margin:0 0 12px;color:var(--ink-2)}
summary{cursor:pointer;font-size:13px}
pre{white-space:pre-wrap;word-wrap:break-word;margin:0;font:13px/1.5 Consolas,"Cascadia Mono",monospace}
pre.prompt{background:var(--wash);border-radius:8px;padding:12px;margin-top:8px;color:var(--ink)}
.answers{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.ans{background:var(--sheet);border:1px solid var(--rule);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:10px;min-width:0}
.ans header{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.letter{font-weight:700;color:var(--cobalt)}
.who{display:none;font-size:12px;color:var(--ok);background:var(--ok-wash);padding:1px 8px;border-radius:99px}
.revealed .who{display:inline}
.ans pre{flex:1}
.stars{display:flex;gap:6px}
.stars button{width:34px;height:30px;border-radius:7px;border:1px solid var(--rule);background:var(--sheet);color:var(--ink-2);cursor:pointer;font:inherit}
.stars button.on{background:var(--cobalt);border-color:var(--cobalt);color:#fff}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--ink);color:var(--paper);padding:8px 14px;border-radius:8px;opacity:0;transition:opacity .2s}
.toast.show{opacity:1}
</style></head>
<body><main>
<h1>Blind review: API against the local model</h1>
<p class="lede">Each task was given to Groq and to the local Qwen3.5 models with the same prompt. The answers are shuffled and labelled A to D. Score each one from 1 (unusable) to 5 (I'd use it as is). When you're done, press <b>Reveal</b> to see who wrote what, then <b>Copy my scores</b> and paste them to Claude. Made {{date}}; every prompt is invented.</p>
<div class="bar"><button class="primary" id="copy">Copy my scores</button><button id="reveal">Reveal who wrote what</button><span class="progress" id="progress"></span></div>
{{sections}}
<div class="toast" id="toast"></div>
</main>
<script>
const KEY = 'mwb-p0-4-scores';
let scores = {};
try { scores = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
const all = [...document.querySelectorAll('.ans')];
function paint() {
  all.forEach(a => a.querySelectorAll('.stars button').forEach(b => b.classList.toggle('on', +b.dataset.v <= (scores[a.dataset.key] || 0))));
  document.getElementById('progress').textContent = `${Object.keys(scores).length} of ${all.length} answers scored`;
}
all.forEach(a => a.querySelectorAll('.stars button').forEach(b => b.addEventListener('click', () => {
  scores[a.dataset.key] = +b.dataset.v;
  try { localStorage.setItem(KEY, JSON.stringify(scores)); } catch (e) {}
  paint();
})));
document.getElementById('reveal').addEventListener('click', e => {
  const on = document.body.classList.toggle('revealed');
  e.target.textContent = on ? 'Hide who wrote what' : 'Reveal who wrote what';
});
document.getElementById('copy').addEventListener('click', async () => {
  const text = 'P0-4 scores: ' + Object.entries(scores).map(([k, v]) => `${k}=${v}`).join(' ');
  try { await navigator.clipboard.writeText(text); toast('Copied. Paste it to Claude.'); }
  catch (e) { prompt('Copy this:', text); }
});
function toast(t) { const el = document.getElementById('toast'); el.textContent = t; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 1800); }
paint();
</script>
</body></html>
'''


def main():
    ap = argparse.ArgumentParser(description='P0-4 sync check')
    ap.add_argument('--routes', default='groq', help='groq, local, all, or a comma list of route names')
    ap.add_argument('--tasks', default='', help='comma list of task ids (default: all ten)')
    ap.add_argument('--backend', default='cpu', choices=['cpu', 'vulkan'])
    ap.add_argument('--no-code', action='store_true', help='skip the five coding tasks on the API routes')
    ap.add_argument('--rescore', action='store_true', help='re-run the checks on the saved answers; no model calls')
    args = ap.parse_args()
    if args.rescore:
        path = os.path.join(OUT, 'answers.json')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for a in data['answers']:
            if a['task'] in TASK_BY_ID:
                a.update(score(TASK_BY_ID[a['task']], a['text'], a['ok']))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        summary(data)
        write_review(data)
        return
    names = []
    for part in args.routes.split(','):
        names += GROUPS['groq'] + GROUPS['local'] if part == 'all' else GROUPS.get(part, [part])
    unknown = [n for n in names if n not in ROUTES]
    if unknown:
        sys.exit(f'unknown route(s): {", ".join(unknown)}')
    tasks = [TASK_BY_ID[t] for t in args.tasks.split(',')] if args.tasks else TASKS
    api = [n for n in names if ROUTES[n]['kind'] == 'api']
    local = [n for n in names if ROUTES[n]['kind'] == 'local']
    rows, net = [], None
    if api:
        r, net = run_api(api, tasks, not args.no_code)
        rows += r
    if local:
        rows += run_local(local, tasks, args.backend)
    if not rows:
        return
    data = save(rows, net)
    summary(data)
    write_machine_file(data)
    write_review(data)
    print(f'\nanswers: {os.path.join(OUT, "answers.json")}\nreview page: {os.path.join(OUT, "review.html")}')


if __name__ == '__main__':
    main()
