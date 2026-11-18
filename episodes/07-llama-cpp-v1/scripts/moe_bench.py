#!/usr/bin/env python3
"""Episode 07: speed of a standalone llama-server (for the MoE cache, which llama-bench does not have).

Usage, on the machine with the GPU and with nothing else loaded on it:
  python3 moe_bench.py --bin <llama.cpp bin dir> --label X --out results.jsonl --log server.log -- <llama-server args>
Starts the server, warms it up (256 tokens), measures generation (3 x 512 tokens, ignore_eos, fixed seeds) and
prefill (2 x a prompt of about 4,000 tokens), records the peak VRAM from nvidia-smi and appends one JSON line to --out.
The prompts are in Portuguese, like the chat_pt battery; results/moe-cache.csv comes from these lines.
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

PROMPT = ("O faroleiro mantinha um diário havia trinta e um anos e nunca tinha escrito uma mentira. Quando o navio "
          "apareceu no horizonte, sem bandeira, sem luzes e sem ninguém no convés, ele ficou um bom tempo sentado à "
          "mesa antes de pegar a caneta. Escreveu a data, a hora e a direção do vento, e então parou. Continue a história:")
LONG = " ".join(["Registro do farol: o vento soprou de sudeste a doze nós, o mar estava calmo e a visibilidade era "
                 "boa até o fim da tarde, quando a neblina cobriu a ponta norte da ilha."] * 130) + " Resuma o registro."


def http(port, path, body=None, timeout=900):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def vram_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return int(out.split()[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    args = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = [os.path.join(os.path.expanduser(a.bin), "llama-server")] + args + ["--host", "127.0.0.1", "--port", str(port)]
    peak, stop = [0], threading.Event()

    def poll():
        while not stop.is_set():
            try:
                peak[0] = max(peak[0], vram_mib())
            except Exception:
                pass
            time.sleep(0.5)

    rec = {"label": a.label, "bin": a.bin, "args": args, "ok": False}
    t0 = time.time()
    with open(a.log, "w") as log:
        proc = subprocess.Popen(server, stdout=log, stderr=subprocess.STDOUT)
    threading.Thread(target=poll, daemon=True).start()
    try:
        while True:
            if proc.poll() is not None:
                rec["error"] = f"llama-server exited ({proc.returncode}) before it was ready"
                return
            try:
                if http(port, "/health", timeout=5).get("status") == "ok":
                    break
            except OSError:
                pass
            if time.time() - t0 > 900:
                rec["error"] = "not ready after 900 s"
                return
            time.sleep(1)
        rec["load_s"] = round(time.time() - t0, 1)
        rec["build"] = http(port, "/props").get("build_info")
        http(port, "/completion", {"prompt": PROMPT, "n_predict": 256, "ignore_eos": True, "cache_prompt": False, "seed": 100})
        tg = []
        for seed in (1, 2, 3):
            t = http(port, "/completion", {"prompt": PROMPT, "n_predict": 512, "ignore_eos": True,
                                           "cache_prompt": False, "seed": seed})["timings"]
            tg.append({"tok_s": round(t["predicted_per_second"], 2), "n": t["predicted_n"],
                       "draft_n": t.get("draft_n"), "draft_accepted": t.get("draft_n_accepted")})
        pp = []
        for seed in (1, 2):
            t = http(port, "/completion", {"prompt": LONG, "n_predict": 1, "cache_prompt": False, "seed": seed})["timings"]
            pp.append({"tok_s": round(t["prompt_per_second"], 1), "n": t["prompt_n"]})
        rec.update(ok=True, tg=tg, pp=pp, tg_mean=round(sum(x["tok_s"] for x in tg) / 3, 2),
                   pp_mean=round(sum(x["tok_s"] for x in pp) / 2, 1))
    except Exception as e:  # record it and go on with the next configuration
        rec["error"] = f"{type(e).__name__}: {e}"
    finally:
        stop.set()
        rec["peak_vram_mib"] = peak[0]
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill()
        with open(a.out, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps({k: rec.get(k) for k in ("label", "ok", "tg_mean", "pp_mean", "peak_vram_mib", "error")},
                         ensure_ascii=False), flush=True)


if __name__ == "__main__":
    sys.exit(main())
