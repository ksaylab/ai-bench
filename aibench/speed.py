"""Speed with llama-bench: prompt processing (pp) and generation (tg) at several context depths, with repetitions.

Runs `llama-bench -o json` with `-r` repetitions (at least 3) and writes one CSV row per measurement. When the model
does not load (not enough memory, for example), the row gets status `error` and the reason: that is how episode 2
shows what does not fit. With `fit_target` (MiB), a model that does not fit with every layer on the GPU is measured
again with llama-bench's --fit-target, which leaves part of it on the CPU as the server's presets do (`fit_target_mib`
on those rows; empty when every layer is on the GPU). With an NVIDIA GPU, nvidia-smi is sampled during each model's measurement: peak VRAM and
average power go into the model's rows (empty without a GPU).
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

from aibench import gpu
from aibench.env import scrub

COLUMNS = ["machine", "gpu", "model", "gguf", "gguf_gib", "metric", "depth", "tok_s", "stddev_tok_s", "repetitions",
           "status", "reason", "build", "peak_vram_mib", "avg_power_w", "fit_target_mib"]


PROMPT, GEN = 512, 128


def command(gguf, depths, repetitions=3, ngl=99, flash=True, extra=(), fit_target=None):
    """Every layer on the GPU (-ngl), or, with `fit_target`, llama-bench places them itself (--fit-target, no -ngl:
    an explicit layer count would override the fit), leaving room for the deepest test's context."""
    cmd = ["llama-bench", "-m", str(gguf), "-p", str(PROMPT), "-n", str(GEN), "-d", ",".join(map(str, depths)),
           "-r", str(repetitions), "-o", "json"]
    if fit_target is None:
        cmd += ["-ngl", str(ngl)]
    else:
        cmd += ["-fitt", str(fit_target), "-fitc", str(max(depths) + PROMPT + GEN)]
    if flash:
        cmd += ["-fa", "1"]
    return cmd + list(extra)


def parse(output_json, machine, model, gguf, repetitions):
    rows = []
    for item in json.loads(output_json):
        rows.append({"machine": machine, "gpu": item.get("gpu_info", ""), "model": model, "gguf": Path(gguf).name,
                     "gguf_gib": round(item.get("model_size", 0) / 2**30, 2),
                     "metric": "tg" if item.get("n_gen", 0) > 0 else "pp", "depth": item.get("n_depth", 0),
                     "tok_s": round(item.get("avg_ts", 0), 2), "stddev_tok_s": round(item.get("stddev_ts", 0), 2),
                     "repetitions": len(item.get("samples_ts") or []) or repetitions, "status": "ok", "reason": "",
                     "build": f"b{item.get('build_number', '')}-{item.get('build_commit', '')}"})
    return rows


def measure(machine, model, gguf, depths=(0, 16384), repetitions=3, timeout=3600, extra=(), sampler=None,
            fit_target=None):
    """llama-bench rows for one GGUF; `sampler` (gpu.Sampler) adds peak VRAM and average power to every row, over
    each attempt's own time window. With `fit_target`, a model that does not fit on the GPU is measured again
    fitted."""
    sampler = sampler or gpu.Disabled("no sampler")
    attempts = [None] if fit_target is None else [None, fit_target]
    rows = []
    sampler.start()
    try:
        for fit in attempts:
            t0 = time.monotonic()
            got = _measure(machine, model, gguf, depths, repetitions, timeout, extra, fit)
            rows.append((got, fit, t0, time.monotonic()))
            if not got or got[0]["reason"] != NO_FIT:
                break
    finally:
        sampler.stop()
    out = []
    for got, fit, t0, t1 in rows:
        power = sampler.window(t0, t1)
        out += [{**r, "peak_vram_mib": power["peak_vram_mib"], "avg_power_w": power["avg_power_w"],
                 "fit_target_mib": "" if fit is None else fit} for r in got]
    return out


NO_FIT = "did not fit in memory"


def _measure(machine, model, gguf, depths, repetitions, timeout, extra, fit_target=None):
    if repetitions < 3:
        raise ValueError("the methodology requires at least 3 repetitions")
    if not shutil.which("llama-bench"):
        raise FileNotFoundError("llama-bench not found (install llama.cpp built with CUDA)")
    if not Path(gguf).exists():
        raise FileNotFoundError(f"GGUF not found: {Path(gguf).name}")
    base = {"machine": machine, "gpu": "", "model": model, "gguf": Path(gguf).name,
            "gguf_gib": round(Path(gguf).stat().st_size / 2**30, 2), "tok_s": "", "stddev_tok_s": "",
            "repetitions": repetitions, "build": ""}
    try:
        r = subprocess.run(command(gguf, depths, repetitions, extra=extra, fit_target=fit_target),
                           capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return [{**base, "metric": "", "depth": "", "status": "error", "reason": "timeout"}]
    if r.returncode != 0 or not r.stdout.strip().startswith("["):
        reason = next((l for l in reversed(r.stderr.splitlines()) if l.strip()), "failed")
        if "out of memory" in r.stderr.lower() or "failed to allocate" in r.stderr.lower():
            reason = NO_FIT
        return [{**base, "metric": "", "depth": "", "status": "error", "reason": scrub(reason)[:200]}]
    return parse(r.stdout, machine, model, gguf, repetitions)
