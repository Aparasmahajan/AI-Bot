"""Settings (design §16.3): the built-in default.toml here, overridden by %APPDATA%\\MWB\\config.toml.
Also the folders MWB keeps its data in (§14)."""
import os, tomllib
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
    problem = None
    if USER_FILE.exists():
        try:
            with open(USER_FILE, 'rb') as f:
                _merge(cfg, tomllib.load(f))
        except (OSError, tomllib.TOMLDecodeError) as e:
            problem = f'{USER_FILE.name}: {e}'
    cfg['_problem'] = problem
    return cfg


def path(text):
    return Path(os.path.expandvars(text))


def dictionary_files():
    """The built-in dictionary, then yours (%APPDATA%\\MWB\\dictionary.txt), which wins on a clash."""
    return [p for p in (HERE / 'dictionary.txt', APPDATA / 'dictionary.txt') if p.exists()]
