"""Records the machine environment (the methodology requires it): OS, CPU, memory, GPU and versions. No host name,
user name, IP address or paths: only what helps to reproduce a test."""
import json
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


def _run(cmd, timeout=10):
    if not shutil.which(cmd[0]):
        return ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (r.stdout or r.stderr).strip()


def scrub(s):
    """Removes home paths and anything that looks like an IP address."""
    s = re.sub(r"(/Users/|/home/)[^\s]+", "<path>", s)
    return re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<ip>", s)


def cpu_and_memory():
    system = platform.system()
    cpu, ram = platform.processor() or platform.machine(), None
    if system == "Darwin":
        cpu = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or cpu
        mem = _run(["sysctl", "-n", "hw.memsize"])
        ram = round(int(mem) / 2**30, 1) if mem.isdigit() else None
    elif system == "Linux":
        try:
            info = Path("/proc/cpuinfo").read_text(encoding="utf-8")
            if m := re.search(r"^model name\s*:\s*(.+)$", info, re.M):
                cpu = m.group(1).strip()
            mem = Path("/proc/meminfo").read_text(encoding="utf-8")
            if m := re.search(r"^MemTotal:\s*(\d+)", mem, re.M):
                ram = round(int(m.group(1)) / 2**20, 1)
        except OSError:
            pass
    return cpu, ram


def gpus():
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    found = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3:
            found.append({"name": parts[0], "vram_mib": int(parts[1]) if parts[1].isdigit() else parts[1],
                          "driver": parts[2]})
    if not found and platform.system() == "Darwin":
        found.append({"name": "Apple Silicon (unified memory)", "vram_mib": None, "driver": "Metal"})
    return found


def server(url):
    """llama-server build and model (/props); empty when the server is not llama-server."""
    base = url[:-3] if url.endswith("/v1") else url
    try:
        with urllib.request.urlopen(base + "/props", timeout=5) as r:
            p = json.load(r)
    except Exception:
        return {}
    model = (p.get("model_path") or "").rsplit("/", 1)[-1]
    return {k: v for k, v in {"build": p.get("build_info", ""), "gguf": model}.items() if v}


def llama_version():
    for prog in ("llama-server", "llama-bench"):
        for line in _run([prog, "--version"]).splitlines():
            if line.lower().startswith("version"):
                return line.strip()
    return ""


def capture(machine, url=None):
    cpu, ram = cpu_and_memory()
    env = {"machine": machine, "os": f"{platform.system()} {platform.release()}", "arch": platform.machine(),
           "cpu": cpu, "ram_gib": ram, "gpus": gpus(), "python": sys.version.split()[0],
           "llama_cpp": scrub(llama_version()), "ollama": scrub(_run(["ollama", "--version"]))}
    if platform.system() == "Darwin":
        env["macos_version"] = _run(["sw_vers", "-productVersion"])
    if url and "openrouter.ai" not in url:
        env["server"] = server(url)
    return env
