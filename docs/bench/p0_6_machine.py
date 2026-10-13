"""P0-6: hardware fingerprint and first calibration record, saved as this machine's baseline.
Probes CPU, RAM sticks and speed, free memory, GPU, NPU, CPU features and the power source,
builds the short fingerprint from CPU, RAM, GPU and NPU (design §12.1), suggests a profile, and
writes %LOCALAPPDATA%\\MWB\\machine\\<fingerprint>.toml. An existing file is kept as .bak first.
Calibration numbers that were measured earlier are copied in with their dates; the API time
stays empty until P0-4 runs. Standard library only.
Usage: py -3.14 -I p0_6_machine.py [--print]   (--print shows the TOML without writing it)"""
import ctypes, ctypes.wintypes as wt, datetime, hashlib, json, os, subprocess, sys, time

LOCAL = os.environ['LOCALAPPDATA']
LLAMA = os.path.join(os.environ['USERPROFILE'], 'Tools', 'llamacpp')

# Measured on this laptop before P0-6 (docs/bench/RESULTS-2026-10-11.md).
MEASURED = {
    'speech_5s_phrase_s': (0.91, 'Parakeet int8, 4 threads, 11 Oct'),
    'local_tokens_per_s': (10.3, 'Qwen3.5 2B, CPU, 12 Oct'),
    'local_tokens_per_s_large': (3.6, 'Qwen3.5 4B, CPU, 12 Oct'),
}


def cim(query):
    """Run one CIM query through PowerShell and return a list of dicts."""
    ps = f'@({query}) | ConvertTo-Json -Compress -Depth 2'
    out = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    if not out:
        return []
    data = json.loads(out)
    return data if isinstance(data, list) else [data]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [('dwLength', wt.DWORD), ('dwMemoryLoad', wt.DWORD),
                ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [('ACLineStatus', ctypes.c_byte), ('BatteryFlag', ctypes.c_byte),
                ('BatteryLifePercent', ctypes.c_byte), ('SystemStatusFlag', ctypes.c_byte),
                ('BatteryLifeTime', wt.DWORD), ('BatteryFullLifeTime', wt.DWORD)]


def free_gb():
    m = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullTotalPhys / 2**30, m.ullAvailPhys / 2**30


def power():
    s = SYSTEM_POWER_STATUS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
    source = {0: 'battery', 1: 'ac'}.get(s.ACLineStatus, 'unknown')
    return source, (s.BatteryLifePercent & 0xFF)


def probe():
    has = ctypes.windll.kernel32.IsProcessorFeaturePresent
    cpu = cim('Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors')[0]
    sticks = cim('Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,ConfiguredClockSpeed,Speed')
    gpus = cim('Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM')
    npus = cim("Get-PnpDevice -Class ComputeAccelerator -PresentOnly -ErrorAction SilentlyContinue | Select-Object FriendlyName")
    total, _ = free_gb()
    samples = []
    for _ in range(5):                     # free memory moves a lot; take the median of 5 over ~4 s
        samples.append(free_gb()[1])
        time.sleep(1)
    mts = min(int(s.get('ConfiguredClockSpeed') or s.get('Speed') or 0) for s in sticks)
    source, battery = power()
    return {
        'cpu': ' '.join(cpu['Name'].split()),
        'cores': cpu['NumberOfCores'], 'threads': cpu['NumberOfLogicalProcessors'],
        'avx2': bool(has(40)), 'avx512': bool(has(41)),
        'ram_gb': round(total),
        'memory_sticks': len(sticks),
        'memory_mts': mts,
        # one DDR4 channel moves 8 bytes per transfer; a laptop with one stick runs one channel
        'bandwidth_peak_gbs': round(len(sticks) * mts * 8 / 1000, 1),
        'gpu': [g['Name'] for g in gpus],
        'npu': bool(npus),
        'power': source, 'battery_percent': battery,
        'free_ram_gb': round(sorted(samples)[2], 2),
    }


def fingerprint(hw):
    key = '|'.join([hw['cpu'], str(hw['ram_gb']), str(hw['memory_sticks']), ';'.join(hw['gpu']), str(hw['npu'])])
    return hashlib.sha256(key.encode()).hexdigest()[:10]


def suggest(hw):
    """Profile rules from design §12.2: no discrete GPU and 16 GB on one stick is Lean."""
    discrete = any(n for n in hw['gpu'] if any(v in n for v in ('NVIDIA', 'Radeon RX', 'Arc A', 'Arc B')))
    if hw['ram_gb'] >= 64 and discrete:
        return 'workstation'
    if discrete:
        return 'performance'
    if hw['ram_gb'] >= 32 and hw['memory_sticks'] >= 2:
        return 'balanced'
    return 'lean'


def toml_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return '[' + ', '.join(toml_value(x) for x in v) + ']'
    return "'" + str(v) + "'"


def render(hw, fp):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    server = os.path.join(LLAMA, 'cpu', 'llama-server.exe')
    small = os.path.join(LLAMA, 'models', 'Qwen3.5-2B-Q4_K_M.gguf')
    large = os.path.join(LLAMA, 'models', 'Qwen3.5-4B-Q4_K_M.gguf')
    lines = [f'# MWB machine file, written by p0_6_machine.py on {now} (P0-6 baseline)',
             f'fingerprint = {toml_value(fp)}', f'profile = {toml_value(suggest(hw))}', '', '[hardware]']
    for k in ('cpu', 'cores', 'threads', 'avx2', 'avx512', 'ram_gb', 'memory_sticks', 'memory_mts',
              'bandwidth_peak_gbs', 'gpu', 'npu'):
        lines.append(f'{k} = {toml_value(hw[k])}')
    lines.append("avx512_vnni = true                # reported by whisper.cpp on 11 Oct; Windows has no flag for it")
    lines += ['', '[calibration]']
    for k, (v, note) in MEASURED.items():
        lines.append(f'{k} = {toml_value(v)}'.ljust(34) + f'# {note}')
    lines.append(f"free_ram_gb = {hw['free_ram_gb']}".ljust(34)
                 + f"# median of 5 samples at {now}, on {hw['power']}; one moment, not a typical day")
    lines.append('# api_first_words_s: not measured yet; P0-4 adds it once the Groq key is stored')
    lines += ['', '[local_llm]                        # the fallback route, found on this machine']
    for k, p in (('server', server), ('model', small), ('model_large', large)):
        lines.append(f'{k} = {toml_value(p)}' + ('' if os.path.exists(p) else '   # MISSING'))
    lines += ['', '[effort]                           # chosen on the setup screen; these are the defaults',
              "mode = 'auto'", "lowest = 'E1'", "highest = 'E2'", "on_battery = 'lower'", '']
    return '\n'.join(lines)


def main():
    hw = probe()
    fp = fingerprint(hw)
    text = render(hw, fp)
    if '--print' in sys.argv:
        print(text)
        return
    folder = os.path.join(LOCAL, 'MWB', 'machine')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f'{fp}.toml')
    if os.path.exists(path):
        os.replace(path, path + '.bak')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(text)
    print(f'\nWritten: {path.replace(os.environ["USERPROFILE"], "%USERPROFILE%")}')


if __name__ == '__main__':
    main()
