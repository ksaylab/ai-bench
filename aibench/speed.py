"""Speed with llama-bench: prompt processing (pp) and generation (tg) at several context depths, with repetitions.

Runs `llama-bench -o json` with `-r` repetitions (at least 3) and writes one CSV row per measurement. When the model
does not load (not enough memory, for example), the row gets status `error` and the reason: that is how episode 2
shows what does not fit.
"""
import json
import shutil
import subprocess
from pathlib import Path

from aibench.env import scrub

COLUMNS = ["machine", "gpu", "model", "gguf", "gguf_gib", "metric", "depth", "tok_s", "stddev_tok_s", "repetitions",
           "status", "reason", "build"]


def command(gguf, depths, repetitions=3, ngl=99, flash=True, extra=()):
    cmd = ["llama-bench", "-m", str(gguf), "-p", "512", "-n", "128", "-d", ",".join(map(str, depths)),
           "-r", str(repetitions), "-ngl", str(ngl), "-o", "json"]
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


def measure(machine, model, gguf, depths=(0, 16384), repetitions=3, timeout=3600, extra=()):
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
        r = subprocess.run(command(gguf, depths, repetitions, extra=extra), capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return [{**base, "metric": "", "depth": "", "status": "error", "reason": "timeout"}]
    if r.returncode != 0 or not r.stdout.strip().startswith("["):
        reason = next((l for l in reversed(r.stderr.splitlines()) if l.strip()), "failed")
        if "out of memory" in r.stderr.lower() or "failed to allocate" in r.stderr.lower():
            reason = "did not fit in memory"
        return [{**base, "metric": "", "depth": "", "status": "error", "reason": scrub(reason)[:200]}]
    return parse(r.stdout, machine, model, gguf, repetitions)
