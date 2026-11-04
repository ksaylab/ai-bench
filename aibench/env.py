"""Records the machine environment (the methodology requires it): OS, CPU, memory, GPU and versions. No host name,
user name, IP address or paths: only what helps to reproduce a test."""
import json
import platform
import re
import shutil
import subprocess
import sys
import urllib.parse
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


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.load(r)
    except Exception:
        return None


def server(url, models=()):
    """llama-server build and GGUF file name (/props); empty when the server is not llama-server. In router mode
    /props has no model, so the GGUF of each of `models` comes from its preset arguments in /v1/models."""
    base = url[:-3] if url.endswith("/v1") else url
    p = _get(base + "/props")
    if p is None:
        return {}
    model = (p.get("model_path") or "").rsplit("/", 1)[-1]
    presets = {}
    if p.get("role") == "router":
        model = {}
        for m in (_get(base + "/v1/models") or {}).get("data", []):
            status = m.get("status") or {}
            args = status.get("args") or []
            if m.get("id") in models and "--model" in args[:-1]:
                model[m["id"]] = args[args.index("--model") + 1].rsplit("/", 1)[-1]
            if m.get("id") in models and status.get("preset"):
                presets[m["id"]] = preset_settings(status["preset"])
    return {k: v for k, v in {"build": p.get("build_info", ""), "gguf": model, "preset": presets}.items() if v}


def preset_settings(text):
    """A router preset ("key = value" lines under [name]) as a dict: file paths reduced to the file name, then
    scrubbed. Settings such as reasoning-budget or ctx-size change what a model can answer, so they are recorded."""
    out = {}
    for line in text.splitlines():
        if "=" not in line or line.lstrip().startswith((";", "#", "[")):
            continue
        k, v = (x.strip() for x in line.split("=", 1))
        out[k] = scrub(v.rsplit("/", 1)[-1] if "/" in v and k.startswith("model") else v)
    return out


def local():
    """This machine's hardware and versions."""
    cpu, ram = cpu_and_memory()
    hw = {"os": f"{platform.system()} {platform.release()}", "arch": platform.machine(), "cpu": cpu, "ram_gib": ram,
          "gpus": gpus(), "python": sys.version.split()[0], "llama_cpp": scrub(llama_version()),
          "ollama": scrub(_run(["ollama", "--version"]))}
    if platform.system() == "Darwin":
        hw["macos_version"] = _run(["sw_vers", "-productVersion"])
    return hw


def remote(host, command=None):
    """The server machine's hardware: this file (standard library only) runs there with `python3 -I -` over ssh.
    `host` is an ssh destination from the environment and never goes into the result. Empty if it fails."""
    command = command or ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "python3", "-I", "-"]
    source = Path(__file__).read_text(encoding="utf-8") + "\nprint(json.dumps(local()))\n"
    try:
        r = subprocess.run(command, input=source, capture_output=True, text=True, timeout=60)
        hw = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {}
    return hw if isinstance(hw, dict) else {}


# Machines whose model server is never this one, even through a local tunnel (RunPod: ssh -L on localhost).
TUNNELED = {"runpod"}


def server_is_remote(machine, url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return machine in TUNNELED or host not in ("localhost", "127.0.0.1", "::1")


def llama_version():
    for prog in ("llama-server", "llama-bench"):
        for line in _run([prog, "--version"]).splitlines():
            if line.lower().startswith("version"):
                return line.strip()
    return ""


def capture(machine, url=None, server_host=None, models=()):
    """Environment of the machine that runs the models. When the model server is another machine, its hardware is
    read over ssh from `server_host` (AIBENCH_SERVER_HOST); without it, no hardware is recorded rather than this
    machine's."""
    env = {"machine": machine}
    if url and "openrouter.ai" not in url and server_is_remote(machine, url):
        hw = remote(server_host) if server_host else {}
        env.update(hw or {"hardware": "not recorded: remote model server (set AIBENCH_SERVER_HOST to the ssh "
                                      "destination of the server to record it)"})
    else:
        env.update(local())
    if url and "openrouter.ai" not in url:
        env["server"] = server(url, models)
    return env
