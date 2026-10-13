"""Small coding check for local models: 5 Python tasks, each graded by running hidden tests.
Starts llama-server with the given model, asks each task once (temperature 0), extracts the code,
runs it with the tests in a separate Python process (10 s limit), then stops the server.
Usage: py -3.14 -I code_test.py LABEL MODEL.gguf [extra llama-server args...]
p0_4_sync_check.py imports TASKS, extract_code and passes to put the same tasks to the API."""
import json, os, re, subprocess, sys, tempfile, time, urllib.request

SERVER = os.path.join(os.environ['USERPROFILE'], 'Tools', 'llamacpp', 'cpu', 'llama-server.exe')
PORT = 8091
BASE = f'http://127.0.0.1:{PORT}'
PROMPT_TAIL = ' Reply with only the code, in one ```python block, no explanation.'

TASKS = [
    ('merge_intervals', 'Write a Python function merge_intervals(intervals) that takes a list of [start, end] pairs and returns a new list where overlapping or touching intervals are merged, sorted by start.',
     'assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]\n'
     'assert merge_intervals([[1,4],[4,5]]) == [[1,5]]\n'
     'assert merge_intervals([]) == []\n'
     'assert merge_intervals([[5,7],[1,2]]) == [[1,2],[5,7]]\n'),
    ('is_balanced', 'Write a Python function is_balanced(s) that returns True if every bracket in the string s, of the kinds (), [] and {}, is correctly matched and nested, ignoring all other characters, and False otherwise.',
     'assert is_balanced("a(b[c]{d})e") is True\n'
     'assert is_balanced("([)]") is False\n'
     'assert is_balanced("") is True\n'
     'assert is_balanced("((") is False\n'
     'assert is_balanced("}{") is False\n'),
    ('top_k_words', 'Write a Python function top_k_words(words, k) that returns the k most frequent strings in the list words, ordered by frequency from high to low, with ties broken alphabetically.',
     'assert top_k_words(["b","a","c","a","b","a"], 2) == ["a","b"]\n'
     'assert top_k_words(["x","y","z"], 2) == ["x","y"]\n'
     'assert top_k_words(["k","k","j","j","i"], 3) == ["j","k","i"]\n'),
    ('parse_duration', 'Write a Python function parse_duration(text) that converts strings like "1h30m", "45s", "2h5s" or "10m20s" into a total number of seconds as an int. Hours (h), minutes (m) and seconds (s) are optional but appear in that order.',
     'assert parse_duration("1h30m") == 5400\n'
     'assert parse_duration("45s") == 45\n'
     'assert parse_duration("2h5s") == 7205\n'
     'assert parse_duration("10m20s") == 620\n'),
    ('chunk_by_size', 'Write a Python function chunk_by_size(items, max_total) that splits a list of positive ints into consecutive chunks (lists), keeping the original order, where each chunk sum is at most max_total. A single item larger than max_total goes into its own chunk. Start a new chunk only when adding the next item would exceed max_total.',
     'assert chunk_by_size([3,4,2,6,1], 7) == [[3,4],[2],[6,1]]\n'
     'assert chunk_by_size([10,1,1], 5) == [[10],[1,1]]\n'
     'assert chunk_by_size([], 5) == []\n'),
]


def extract_code(text):
    """The first fenced code block, or the whole text if there is none."""
    m = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.S)
    return m.group(1) if m else text


def passes(code, tests):
    """Run the code and its hidden tests in a separate, isolated Python process with a 10 s limit."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 't.py')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code + '\n\n' + tests)
        try:
            return subprocess.run([sys.executable, '-I', path], capture_output=True, timeout=10, cwd=d).returncode == 0
        except subprocess.TimeoutExpired:
            return False


def post(path, body, timeout=900):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main():
    label, model, extra = sys.argv[1], sys.argv[2], sys.argv[3:]
    proc = subprocess.Popen([SERVER, '-m', model, '-t', '4', '-c', '4096', '--host', '127.0.0.1', '--port', str(PORT)] + extra,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    try:
        t0 = time.time()
        while time.time() - t0 < 180:
            try:
                with urllib.request.urlopen(BASE + '/health', timeout=2) as r:
                    if json.load(r).get('status') == 'ok':
                        break
            except Exception:
                time.sleep(0.5)
        passed, gen_tokens, gen_ms, wall = 0, 0, 0.0, time.time()
        for name, task, tests in TASKS:
            r = post('/v1/chat/completions', {'messages': [{'role': 'user', 'content': task + PROMPT_TAIL}], 'temperature': 0, 'max_tokens': 600})
            text = r['choices'][0]['message'].get('content') or ''
            gen_tokens += r['usage']['completion_tokens']; gen_ms += r['timings']['predicted_ms']
            ok = passes(extract_code(text), tests)
            passed += ok
            print(f'[{label}] {name:15} {"PASS" if ok else "FAIL"}  ({r["usage"]["completion_tokens"]} tokens)', flush=True)
        print(f'[{label}] passed {passed}/{len(TASKS)} | writing {gen_tokens / (gen_ms / 1000):.1f} tokens/s | all 5 tasks took {time.time() - wall:.0f} s', flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()


if __name__ == '__main__':
    main()
