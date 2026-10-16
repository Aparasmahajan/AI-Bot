"""Settings (design §16.3): the built-in default.toml here, overridden by %APPDATA%\\MWB\\config.toml.
Also the folders MWB keeps its data in (§14)."""
import os, re, tomllib
from pathlib import Path

HERE = Path(__file__).parent
APPDATA = Path(os.environ.get('APPDATA', Path.home())) / 'MWB'
LOCAL = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'MWB'
USER_FILE = APPDATA / 'config.toml'


def _merge(base, over):
    for k, v in over.items():
        base[k] = _merge(base.get(k, {}), v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return base


def load():
    """The settings as nested dicts. A broken user file is reported, not fatal: the defaults still run."""
    with open(HERE / 'default.toml', 'rb') as f:
        cfg = tomllib.load(f)
    problem, yours = None, {}
    if USER_FILE.exists():
        try:
            with open(USER_FILE, 'rb') as f:
                yours = tomllib.load(f)
            _merge(cfg, yours)
        except (OSError, tomllib.TOMLDecodeError) as e:
            problem = f'{USER_FILE.name}: {e}'
    cfg['_problem'] = problem
    # the (section, key) pairs you set yourself: effort levels never change those (§12.5)
    cfg['_user'] = {(s, k) for s, v in yours.items() if isinstance(v, dict) for k in v}
    return cfg


def toml_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(toml_value(x) for x in v) + ']'
    s = str(v)
    return f"'{s}'" if "'" not in s and '\n' not in s else '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def save_user(changes, path=None):
    """Write {section: {key: value}} into your settings file, changing only those lines: your comments, order and
    other settings stay as they are. A key you haven't set yet goes at the end of its section."""
    path = Path(path or USER_FILE)
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    for section, keys in changes.items():
        start = next((i for i, l in enumerate(lines) if l.strip() == f'[{section}]'), None)
        if start is None:
            lines += ([''] if lines and lines[-1].strip() else []) + [f'[{section}]']
            start = len(lines) - 1
        end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
        for key, value in keys.items():
            text = f'{key} = {toml_value(value)}'
            hit = next((i for i in range(start + 1, end) if lines[i].split('=')[0].strip() == key
                        and not lines[i].lstrip().startswith('#')), None)
            if hit is None:
                last = max([i for i in range(start, end) if lines[i].strip()] or [start])
                lines.insert(last + 1, text)
                end += 1
            else:
                m = _COMMENT.match(lines[hit])
                lines[hit] = text + (f'   {m.group(1)}' if m else '')
    text = '\n'.join(lines) + '\n'
    tomllib.loads(text)                             # it must read back before it replaces your file
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


# key = value  # comment, where the value may itself hold a # inside quotes
_COMMENT = re.compile(r'''^\s*[\w-]+\s*=\s*(?:'[^']*'|"(?:[^"\\]|\\.)*"|\[[^\]#]*\]|[^#'"\[]*?)\s*(#.*)$''')


def path(text):
    return Path(os.path.expandvars(text))


def dictionary_files():
    """The built-in dictionary, then yours (%APPDATA%\\MWB\\dictionary.txt), which wins on a clash."""
    return [p for p in (HERE / 'dictionary.txt', APPDATA / 'dictionary.txt') if p.exists()]
