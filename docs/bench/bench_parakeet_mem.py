"""Memory behaviour of Parakeet int8 under dictation-sized vs meeting-sized inputs.

usage: python bench_parakeet_mem.py <wav> <threads> <arena 0|1>
Steps: load -> 10 dictation-sized utterances (4-10 s) -> the 62 s file in 10 s chunks -> the 62 s file in one pass.
Prints current working set / private bytes after each step (peaks are cumulative, so current values tell the story).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench_parakeet import mem, read_wav  # noqa: E402  (same folder; sets HF offline env)


def main():
    wav, threads, arena = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "1"
    import numpy as np
    import onnxruntime as ort
    import onnx_asr

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    opts.enable_cpu_mem_arena = arena
    out = {"threads": threads, "cpu_mem_arena": arena}
    model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", quantization="int8", sess_options=opts)
    model.recognize(np.zeros(16000, dtype=np.float32), sample_rate=16000)
    out["after_load"] = mem()

    audio, sr = read_wav(wav)
    lat = []
    for i, dur in enumerate((4, 6, 8, 10, 5, 7, 9, 4, 6, 8)):
        start = int((i * 5) % 50 * sr)
        seg = audio[start: start + int(dur * sr)]
        t0 = time.perf_counter()
        model.recognize(seg, sample_rate=sr)
        lat.append(round(time.perf_counter() - t0, 2))
    out["dictation_latencies_s"] = lat
    out["after_10_dictations"] = mem()

    t0 = time.perf_counter()
    step = 10 * sr
    for s in range(0, len(audio), step):
        model.recognize(audio[s: s + step], sample_rate=sr)
    out["chunked_62s_in_10s_s"] = round(time.perf_counter() - t0, 2)
    out["after_chunked"] = mem()

    t0 = time.perf_counter()
    model.recognize(audio, sample_rate=sr)
    out["single_pass_62s_s"] = round(time.perf_counter() - t0, 2)
    out["after_single_pass"] = mem()
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
