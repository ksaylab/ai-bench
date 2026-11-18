#!/usr/bin/env python3
"""Episode 07: the *-moecache router presets (MoE cache of llama.cpp 1.0) with long prompts, through the router.

Usage, on the machine with the GPU: python3 longprompt_test.py > longprompt.jsonl
Two scenarios (about 24,000 and 75,000 tokens), 3 repetitions each, per model. Each prompt is a generated shipping
log in Portuguese (seed = repetition) with one "needle" lot at a random position; the question asks for that lot's
city. Records prefill, generation, peak VRAM (nvidia-smi every 0.5 s) and whether the answer is right. No prompt
cache between tests. The baseline without the cache ran the same documents with MODELS = ["gemma4-26b"] and
TARGETS = [75000]. results/long-prompt.csv comes from these lines.
"""
import json
import random
import subprocess
import sys
import threading
import time
import urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
MODELS = ["qwen3.6-35b-a3b-moecache", "gemma4-26b-moecache"]
TARGETS = [24000, 75000]
CITIES = ["Recife", "Manaus", "Curitiba", "Belém", "Natal", "Goiânia", "Cuiabá", "Florianópolis", "Teresina",
          "Maceió", "Aracaju", "Vitória", "Palmas", "Macapá", "Boa Vista", "Porto Velho", "Campo Grande", "Salvador"]
GOODS = ["caixas de parafusos", "sacas de café", "rolos de cabo", "fardos de algodão", "tambores de óleo",
         "paletes de cerâmica", "engradados de frutas", "bobinas de papel", "sacos de cimento", "caixas de remédios"]
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]


def record(rng, lot, city=None):
    return (f"O lote {lot} saiu do depósito em {rng.randint(1, 28)} de {rng.choice(MONTHS)} com {rng.randint(2, 900)} "
            f"{rng.choice(GOODS)}, foi conferido pela equipe {rng.choice('ABCDEFGH')}{rng.randint(1, 9)} e seguiu para "
            f"{city or rng.choice(CITIES)}, com prazo de {rng.randint(2, 30)} dias.")


def document(n, seed):
    rng = random.Random(seed)
    lots = rng.sample(range(10000, 99999), n)
    needle = rng.randrange(n // 10, n - n // 10)
    city = rng.choice(CITIES)
    lines = [record(rng, lot, city if i == needle else None) for i, lot in enumerate(lots)]  # unique lots (sample)
    q = (f"Registro de expedições:\n\n" + "\n".join(lines) +
         f"\n\nPergunta: para qual cidade seguiu o lote {lots[needle]}? Responda só com o nome da cidade.")
    return q, city


def ask(model, prompt, max_tokens, timeout=1800):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0.0, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def vram():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return int(out.split()[0])


def main():
    for model in MODELS:
        # calibration: tokens per log line for this model (the tokenizers differ)
        q, _ = document(200, 0)
        per = ask(model, q, 1)["usage"]["prompt_tokens"] / 200
        print(f"# {model}: {per:.1f} tokens per log line", file=sys.stderr, flush=True)
        for target in TARGETS:
            for rep in (1, 2, 3):
                q, city = document(int(target / per), 1000 * target + rep)
                peak, stop = [0], threading.Event()

                def poll():
                    while not stop.is_set():
                        try:
                            peak[0] = max(peak[0], vram())
                        except Exception:
                            pass
                        time.sleep(0.5)

                threading.Thread(target=poll, daemon=True).start()
                rec = {"model": model, "target": target, "rep": rep, "expected": city}
                t0 = time.time()
                try:
                    r = ask(model, q, 64)
                    t = r.get("timings", {})
                    answer = (r["choices"][0]["message"].get("content") or "").strip()
                    rec.update(ok=True, prompt_tokens=r["usage"]["prompt_tokens"], answer=answer[:80],
                               correct=city.lower() in answer.lower(),
                               pp_tok_s=round(t.get("prompt_per_second", 0), 1),
                               tg_tok_s=round(t.get("predicted_per_second", 0), 1))
                except Exception as e:
                    rec.update(ok=False, error=f"{type(e).__name__}: {e}"[:300])
                stop.set()
                rec.update(wall_s=round(time.time() - t0, 1), peak_vram_mib=peak[0])
                print(json.dumps(rec, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
