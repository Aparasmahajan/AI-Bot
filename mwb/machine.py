"""This machine (design §12.1, §12.6): the hardware probe, the fingerprint, the suggested profile and effort level,
calibration numbers and your effort choice, kept in %LOCALAPPDATA%\\MWB\\machine\\<fingerprint>.toml. These are the
machine's own settings: they never travel with you, unlike %APPDATA%\\MWB\\config.toml.

The probe is the one P0-6 proved on this laptop: one PowerShell CIM query, about 2 s, run off the core's loop. The
fingerprint is built from the CPU, RAM size, memory sticks, GPUs and NPU, so adding a memory stick counts as a new
machine and brings the setup screen back."""
import ctypes, datetime, hashlib, json, logging, os, shutil, subprocess, tomllib

from mwb import config, winapi

log = logging.getLogger('mwb.machine')
FOLDER = config.LOCAL / 'machine'
LEVELS = ('E1', 'E2', 'E3', 'E4')
NAMES = {'E1': 'Battery saver', 'E2': 'Balanced', 'E3': 'High', 'E4': 'Max'}
FEATURES = {'journal': 'Journal', 'meetings': 'Meetings', 'dictation': 'Dictation', 'email_code': 'Email and code'}
PROBE = r"""$c = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors
$m = @(Get-CimInstance Win32_PhysicalMemory | Select-Object ConfiguredClockSpeed,Speed)
$g = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM)
$n = @(Get-PnpDevice -Class ComputeAccelerator -PresentOnly -ErrorAction SilentlyContinue | Select-Object FriendlyName)
ConvertTo-Json -Compress -Depth 3 @{cpu = $c; mem = $m; gpu = $g; npu = $n}"""


def _list(v):
    return [] if v is None else v if isinstance(v, list) else [v]


def probe():
    """The hardware, as P0-6 records it. Raises RuntimeError if Windows won't say."""
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', PROBE], capture_output=True,
                             text=True, timeout=60, creationflags=0x08000000).stdout.strip()
        d = json.loads(out)
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        raise RuntimeError(f'the hardware could not be read ({type(e).__name__})')
    has = ctypes.windll.kernel32.IsProcessorFeaturePresent
    m = winapi.MEMORYSTATUSEX(dwLength=ctypes.sizeof(winapi.MEMORYSTATUSEX))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    sticks = _list(d.get('mem'))
    mts = min([int(s.get('ConfiguredClockSpeed') or s.get('Speed') or 0) for s in sticks] or [0])
    cpu = d.get('cpu') or {}
    return {'cpu': ' '.join(str(cpu.get('Name', '')).split()), 'cores': cpu.get('NumberOfCores') or 0,
            'threads': cpu.get('NumberOfLogicalProcessors') or 0, 'avx2': bool(has(40)), 'avx512': bool(has(41)),
            'ram_gb': round(m.ullTotalPhys / 2 ** 30), 'memory_sticks': len(sticks), 'memory_mts': mts,
            'bandwidth_peak_gbs': round(len(sticks) * mts * 8 / 1000, 1),
            'gpu': [g.get('Name', '') for g in _list(d.get('gpu'))], 'npu': bool(_list(d.get('npu')))}


def fingerprint(hw):
    key = '|'.join([hw['cpu'], str(hw['ram_gb']), str(hw['memory_sticks']), ';'.join(hw['gpu']), str(hw['npu'])])
    return hashlib.sha256(key.encode()).hexdigest()[:10]


def discrete_gpu(hw):
    return any(any(v in n for v in ('NVIDIA', 'Radeon RX', 'Arc A', 'Arc B')) for n in hw['gpu'])


def profile_of(hw):
    """§12.2: no discrete GPU and 16 GB on one stick is Lean."""
    if hw['ram_gb'] >= 64 and discrete_gpu(hw):
        return 'workstation'
    if discrete_gpu(hw):
        return 'performance'
    if hw['ram_gb'] >= 32 and hw['memory_sticks'] >= 2:
        return 'balanced'
    return 'lean'


def suggested(profile, preference='suggested'):
    """The level the setup screen pre-selects (§12.5); effort_preference in your settings can change it."""
    top = available(profile)[-1]
    if preference == 'max-available':
        return top
    if preference == 'battery-saver':
        return 'E1'
    return {'lean': 'E2', 'balanced': 'E3'}.get(profile, 'E4')


def available(profile):
    """The levels this machine can run at all: Max needs a GPU, or 32 GB in two sticks."""
    return LEVELS if profile != 'lean' else LEVELS[:3]


def why_not(level, profile):
    """A reason a level is greyed out or slow on this machine, or ''."""
    if level not in available(profile):
        return 'Not available on this laptop: needs a GPU, or 32 GB in two sticks.'
    if level == 'E3' and profile == 'lean':
        return 'Slower on this laptop.'
    return ''


def path_of(fp):
    return FOLDER / f'{fp}.toml'


def load(fp):
    p = path_of(fp)
    if not p.exists():
        return None
    try:
        with open(p, 'rb') as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        log.warning('machine file not read: %s', e)
        return None


def new(hw, fp, preference='suggested'):
    """A first machine file: what was found, and the suggested level, not yet confirmed by you."""
    profile = profile_of(hw)
    level = suggested(profile, preference)
    return {'fingerprint': fp, 'profile': profile, 'hardware': hw, 'calibration': {},
            'effort': {'mode': 'auto', 'lowest': 'E1', 'highest': level, 'on_battery': 'lower', 'chosen': False,
                       'by_feature': {}}}


def effort_of(data):
    """The effort choice from a machine file, with defaults filled in."""
    e = dict((data or {}).get('effort') or {})
    profile = (data or {}).get('profile', 'lean')
    top = available(profile)[-1]
    clamp = lambda v, d: v if v in LEVELS and LEVELS.index(v) <= LEVELS.index(top) else d
    e['highest'] = clamp(e.get('highest'), suggested(profile))
    e['lowest'] = clamp(e.get('lowest'), 'E1')
    if LEVELS.index(e['lowest']) > LEVELS.index(e['highest']):
        e['lowest'] = e['highest']
    e['mode'] = e.get('mode') if e.get('mode') in ('auto', 'fixed') else 'auto'
    e['on_battery'] = e.get('on_battery') if e.get('on_battery') in ('lower', 'keep') else 'lower'
    e['by_feature'] = {k: clamp(v, e['highest']) for k, v in (e.get('by_feature') or {}).items() if k in FEATURES}
    e['chosen'] = bool(e.get('chosen'))
    return e


def save(fp, data):
    """Write the machine file, keeping the previous one as .bak."""
    FOLDER.mkdir(parents=True, exist_ok=True)
    p = path_of(fp)
    if p.exists():
        shutil.copyfile(p, p.with_suffix('.toml.bak'))
    v = config.toml_value
    out = [f'# MWB machine file: this laptop only, never copied with your settings (design §12.6). '
           f'Written {datetime.datetime.now():%Y-%m-%d %H:%M}.']
    out += [f'{k} = {v(data[k])}' for k in ('fingerprint', 'profile') if k in data]
    for table in ('hardware', 'calibration', 'local_llm', 'effort'):
        t = data.get(table)
        if not isinstance(t, dict):
            continue
        out += ['', f'[{table}]'] + [f'{k} = {v(x)}' for k, x in t.items() if not isinstance(x, dict)]
        for sub, inner in t.items():
            if isinstance(inner, dict):
                out += ['', f'[{table}.{sub}]'] + [f'{k} = {v(x)}' for k, x in inner.items()]
    text = '\n'.join(out) + '\n'
    tomllib.loads(text)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(p)
    return p


def models_needed(cfg, levels):
    """[(what, path, found?)] for the models and programs the chosen levels use on this machine."""
    llm, m, sp = cfg['llm'], cfg['meetings'], cfg['speech']
    llama = config.path(llm['llamacpp'])
    rows = [('Speech (Parakeet, in AI-App)', config.path(os.environ.get('MWB_ASR_PYTHON') or sp['python'])),
            ('Meetings (whisper-cli)', config.path(m['whisper_cli'])),
            ('Meetings (whisper small)', config.path(m['whisper_model'])),
            ('Local fallback (llama-server)', llama / 'cpu' / 'llama-server.exe'),
            ('Local fallback (Qwen3.5 2B)', llama / 'models' / llm['local_model'])]
    if any(LEVELS.index(l) >= 1 for l in levels):
        rows.append(('Code and journal fallback (Qwen3.5 4B)', llama / 'models' / llm['local_model_big']))
    return [(what, str(p), p.exists()) for what, p in rows]
