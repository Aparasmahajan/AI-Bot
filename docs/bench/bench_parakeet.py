"""Benchmark Parakeet TDT 0.6B v2 (int8 ONNX via onnx-asr) exactly as AI-App's sidecar loads it.

usage: python bench_parakeet.py <wav> <reference.txt> <threads>
Prints JSON: load time, per-clip-length latency (median of 3), RTFx, WER, and process memory.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import sys
import time
import wave

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # model is already in the HF cache; never download here
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


k32 = ctypes.windll.kernel32
k32.GetCurrentProcess.restype = wt.HANDLE
psapi = ctypes.windll.psapi
psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]


def mem():
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    mb = 1024 * 1024
    return {"ws_mb": round(c.WorkingSetSize / mb), "peak_ws_mb": round(c.PeakWorkingSetSize / mb),
            "private_mb": round(c.PagefileUsage / mb), "peak_private_mb": round(c.PeakPagefileUsage / mb)}


def read_wav(path):
    import numpy as np
    with wave.open(path) as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0, sr


def words(t):
    t = t.lower().replace("-", " ")
    return re.sub(r"[^a-z0-9' ]+", " ", t).split()


def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / max(1, len(r))


def main():
    wav, ref_path, threads = sys.argv[1], sys.argv[2], int(sys.argv[3])
    out = {"threads": threads, "mem_python_start": mem()}

    t0 = time.perf_counter()
    import numpy as np
    import onnxruntime as ort
    import onnx_asr
    out["import_s"] = round(time.perf_counter() - t0, 2)
    out["mem_after_import"] = mem()

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    t0 = time.perf_counter()
    model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", quantization="int8", sess_options=opts)
    out["load_s"] = round(time.perf_counter() - t0, 2)
    out["mem_after_load"] = mem()

    t0 = time.perf_counter()
    model.recognize(np.zeros(16000, dtype=np.float32), sample_rate=16000)
    out["warmup_s"] = round(time.perf_counter() - t0, 2)

    audio, sr = read_wav(wav)
    total = len(audio) / sr
    out["audio_s"] = round(total, 1)
    clips = {}
    for secs in (3, 5, 10, 30):
        if secs >= total:
            continue
        seg = audio[: int(secs * sr)]
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            model.recognize(seg, sample_rate=sr)
            times.append(time.perf_counter() - t0)
        times.sort()
        clips[f"{secs}s"] = {"median_s": round(times[1], 2), "rtfx": round(secs / times[1], 1)}
    t0 = time.perf_counter()
    text = model.recognize(audio, sample_rate=sr)
    full = time.perf_counter() - t0
    clips[f"full_{round(total)}s"] = {"s": round(full, 2), "rtfx": round(total / full, 1)}
    out["clips"] = clips
    out["mem_end"] = mem()
    with open(ref_path, encoding="utf-8") as f:
        out["wer_pct"] = round(100 * wer(f.read(), text), 2)
    out["text_head"] = text[:240]
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
