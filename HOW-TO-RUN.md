# How to run

Everything from the repository root, with Python 3.11 or newer (standard library only; nothing to install with pip).
Times and costs below are estimates from earlier tests with similar cases; what counts is what the run records in
the CSV.

## 0. Check first (free, no network, ~5 s)

```bash
python3 -m unittest discover -s tests -t .
python3 -m aibench run --episode 03-is-bigger-better --machine mac-m5 --simulate --label dry-run
python3 -m aibench cost --example
python3 -m aibench cases                     # list the batteries
```

`--simulate` answers with the cases' good examples (and gets one coding run wrong on purpose): it shows the folders,
CSVs and the verdict table. Simulated and smoke runs stay out of git and out of `verdict`.

## What each command does

- `run`: the four batteries (27 cases) × 3 runs = 81 calls per model. Writes
  `episodes/<ep>/results/runs/<date>-<machine>-<label>/` with `executions.csv`, `scores.csv`, `verdicts.csv` and
  `verdicts.md`. `--use-cases coding,rag` runs only some batteries (the others then have no verdict).
- `speed`: `llama-bench` with 3 repetitions, a 512-token prompt and 128 generated tokens, at the requested depths
  (default 0 and 16384). Needs the GGUF on the machine and the model server stopped.
- `verdict`: merges the episode's publishable runs into `results/executions.csv`, `scores.csv`, `verdicts.csv` and
  `verdicts.md` (the table for the video).

To keep a Mac awake during a run: put `caffeinate -i` in front of the command.

## Mac M5 (16 GB)

Cost: electricity only. Time: ~10 to 45 min per model for `run` (10 to 40 s per case, depending on the model and its
reasoning; unknown for the large models) and ~2 to 10 min per model for `speed`.

```bash
brew install llama.cpp            # llama-server and llama-bench, if not installed yet
# one server per model; change the GGUF and --models on each run
llama-server -m ~/models/NeoHorse-1-4B.i1-Q4_K_M.gguf -c 32768 -ngl 99 -fa on --jinja --port 8080
```

`--jinja` enables the model's chat template with tool calling (needed by the `agent` battery).
In another terminal:

```bash
# episode 2: verdict, time and cost of each model that fits
caffeinate -i python3 -m aibench run --episode 02-what-runs-on-16gb-and-8gb --machine mac-m5 --models neohorse-4b --label neohorse-4b
# longer RAG documents (the server needs -c 65536 or more)
caffeinate -i python3 -m aibench run --episode 02-what-runs-on-16gb-and-8gb --machine mac-m5 --models neohorse-4b --use-cases rag --context-words 24000 --label neohorse-4b-ctx24k
# speed: stop llama-server first, so it does not compete for memory
caffeinate -i python3 -m aibench speed --episode 02-what-runs-on-16gb-and-8gb --machine mac-m5 --models-dir ~/models --depths 0,16384,32768
# episode 3: the small vs large pairs, one server at a time
caffeinate -i python3 -m aibench run --episode 03-is-bigger-better --machine mac-m5 --models qwen3.6-35b-a3b --label qwen3.6-35b-a3b
```

With Ollama instead of llama-server: `--url http://localhost:11434/v1` and `--models <ollama tag>`.
`speed` measures GGUF files with `llama-bench`; models only available in Ollama have no speed measurement.

## PC with an RTX 2060 Super (8 GB)

Cost: electricity only. Time: similar to the Mac for models that fit entirely on the card; for those larger than
8 GB (partly on the CPU), unknown, probably 2× or more.

On the PC, start the server listening on the local network (`--host 0.0.0.0 --port 8080 --jinja`) with the model of
the run. On the Mac, set the address through a variable (do not write the IP address in a repository file):

```bash
export AIBENCH_URL="http://<pc-address>:8080/v1"
caffeinate -i python3 -m aibench run --episode 02-what-runs-on-16gb-and-8gb --machine pc-rtx2060 --models ornith1.5-9b --label ornith1.5-9b
caffeinate -i python3 -m aibench run --episode 03-is-bigger-better --machine pc-rtx2060 --models neohorse-4b --label neohorse-4b
```

`speed` runs on the PC itself: copy the repository folder there (`rsync`/`scp`), run

```bash
python3 -m aibench speed --episode 02-what-runs-on-16gb-and-8gb --machine pc-rtx2060 --models-dir ~/models
```

and bring back the new folder in `episodes/02-what-runs-on-16gb-and-8gb/results/runs/`.

## RunPod (rented GPU)

Cost: the hourly price of the chosen GPU, plus the time to start the pod and download the model (~4 to 5 min per
session). Reference from October 2026: ~US$0.27/h for an RTX A5000 24 GB on Secure Cloud (check the day's price in the
console). Time: ~30 to 60 min per model for `run`. **Delete the pod at the end**: left on, it keeps billing.

1. Create the pod with the `ghcr.io/ggml-org/llama.cpp:full-cuda` image, disk for the GGUF and SSH enabled.
2. On the pod: download the GGUF and start `llama-server -m /workspace/<file>.gguf -c 65536 -ngl 99 -fa on --jinja --port 8080`.
3. On the Mac, open the tunnel (the connection details are in the pod's console) and run:

```bash
ssh -N -L 8080:localhost:8080 <pod-ssh-connection> &
export AIBENCH_SERVER_KEY=""   # only if the server uses --api-key
caffeinate -i python3 -m aibench run --episode 01-buy-or-rent-gpu --machine runpod --models gemma4-12b --label a5000-gemma4-12b
```

4. Speed, on the pod itself (copy the repository folder to `/workspace`):

```bash
python3 -m aibench speed --episode 01-buy-or-rent-gpu --machine runpod --models-dir /workspace --depths 0,16384,65536
```

## OpenRouter (cloud, paid)

Cost: whatever the provider charges per token; it goes in the `cost_usd` column. Estimate: US$0.05 to 0.80 per model
for the 81 calls, depending on the model (models with long reasoning cost more). The judge, if used, adds cents.
Time: ~5 to 30 min per model.

```bash
export OPENROUTER_API_KEY="…"      # from your password manager; never in a repository file
caffeinate -i python3 -m aibench run --episode 03-is-bigger-better --machine openrouter --models qwen/qwen3.8-flash,qwen/qwen3.8-27b --judge z-ai/glm-5.3-flash --label cloud-qwen
```

The runner refuses a judge that is one of the compared models. In a local run, the judge goes to OpenRouter (it needs
`OPENROUTER_API_KEY`); for another compatible address, use `--judge-url`. `AIBENCH_URL` is never used for OpenRouter.

## Episode 1: cost of buying vs renting

1. Fill in `episodes/01-buy-or-rent-gpu/prices.csv` (price, source with a link, date, `status` CONFIRMED) and the
   FILL_IN rows of `assumptions.csv` (exchange rate, electricity rate, new PSU). Review the REVIEW rows.
2. Run (free, instant):

```bash
python3 -m aibench cost
python3 -m aibench cost --reference runpod-a5000-secure   # break-even against another rental
```

It writes `results/cost.csv`. While a price is not CONFIRMED, the command warns not to publish.
Each card's speed comes from `speed` on RunPod (step above), and its verdict from `run` on the same pod.

## Closing an episode

```bash
python3 -m aibench verdict --episode 02-what-runs-on-16gb-and-8gb
export PRIVATE_TERMS_FILE=<path to the private list of terms, outside this repository>
./scripts/pre-publish-check.sh
```
