# How to run

Everything from the repository root, with Python 3.11 or newer (standard library only; nothing to install with pip).
Times and costs below are estimates from earlier tests with similar cases; what counts is what the run records in
the CSV.

## 0. Check first (free, no network, ~5 s)

```bash
python3 -m unittest discover -s tests -t .
python3 -m aibench run --episode 03-is-bigger-better --machine pc-rtx2060 --simulate --label dry-run
python3 -m aibench calibrate --simulate --label dry-run
python3 -m aibench cost --example
python3 -m aibench cases                     # list the batteries
```

`--simulate` answers with the cases' good examples (and gets one coding run wrong on purpose): it shows the folders,
CSVs and the verdict table. Simulated and smoke runs stay out of git and out of `verdict`; so do pilot runs
(`"status": "pilot"` in `meta.json`, like the 2026-11-02 runs). `verdict` prints each run it skips and why.

## What each command does

- `run`: the four batteries (27 cases) plus the `coding_public` reference battery (10 cases) × 3 runs = 111 calls
  per model, with the model's pinned sampling and one seed per run. Writes
  `episodes/<ep>/results/runs/<date>-<machine>-<label>/` with `meta.json`, `env.json`, `executions.csv`,
  `responses.jsonl` (raw answers), `scores.csv`, `verdicts.csv` and `verdicts.md`. `--use-cases coding,rag` runs
  only some batteries (the others then have no verdict).
- `calibrate`: the same batteries on the OpenRouter anchors of `anchors.toml`, into `calibration/runs/`;
  `calibration` merges them into `calibration/anchors.csv` and writes the pruning report `calibration/pruning.md`.
- `speed`: `llama-bench` with 3 repetitions, a 512-token prompt and 128 generated tokens, at the requested depths
  (default 0 and 16384). Needs the GGUF on the machine and the model server stopped.
- `verdict`: merges the episode's publishable runs into `results/executions.csv`, `scores.csv`, `verdicts.csv`,
  `verdicts.md` (the table for the video) and `speed.csv`; with anchor runs for the same battery version,
  `scores.csv` also has `pct_of_ceiling`, `normalized` and `calibrated`.

To keep the client machine awake during a long run: `systemd-inhibit` on Linux, `caffeinate -i` on macOS, in front
of the command.

## PC with an RTX 2060 Super (8 GB): the only local machine

Local contestants run only on this PC (target `pc-rtx2060`, METHODOLOGY.md 8.1). Cost: electricity only. Time:
~10 to 45 min per model for `run` when the model fits entirely on the card (10 to 40 s per case, depending on the
model and its reasoning); for models larger than 8 GB (partly on the CPU), unknown, probably 2× or more. `speed`:
~2 to 10 min per model.

Start the server on the PC with the model of the run (one at a time, `--parallel 1` so batching does not change the
results; `--jinja` enables the chat template with tool calling, needed by the `agent` battery):

```bash
llama-server -m ~/models/NeoHorse-1-4B.i1-Q4_K_M.gguf -c 32768 -ngl 99 -fa on --jinja --parallel 1 \
  --host 0.0.0.0 --port 8080
```

Every model needs a pinned `[model.sampling]` table with a `seed` in the episode's `models.toml` (METHODOLOGY.md
8.4); check the values against the model card and set `verified = true`. Pass the server's command line with
`--server-args` (or `AIBENCH_SERVER_ARGS`) so it goes into `meta.json`.

The client can be the PC itself (`AIBENCH_URL="http://localhost:8080/v1"`) or another computer on the same network.
From another computer, set the address through a variable (do not write the IP address in a repository file):

```bash
export AIBENCH_URL="http://<pc-address>:8080/v1"
export AIBENCH_SERVER_HOST="<user>@<pc-address>"   # ssh destination: env.json records the PC's hardware
python3 -m aibench run --episode 02-what-runs-on-8gb --machine pc-rtx2060 --models neohorse-4b --label neohorse-4b
python3 -m aibench run --episode 02-what-runs-on-8gb --machine pc-rtx2060 --models ornith1.5-9b --label ornith1.5-9b
python3 -m aibench run --episode 03-is-bigger-better --machine pc-rtx2060 --models neohorse-4b --label neohorse-4b
# longer RAG documents (the server needs -c 65536 or more)
python3 -m aibench run --episode 02-what-runs-on-8gb --machine pc-rtx2060 --models neohorse-4b --use-cases rag \
  --context-words 24000 --label neohorse-4b-ctx24k
```

With Ollama instead of llama-server: `--url http://localhost:11434/v1` and `--models <ollama tag>`.

`speed` runs on the PC itself, with the model server stopped so it does not compete for VRAM: copy the repository
folder there (`rsync`/`scp`), run

```bash
python3 -m aibench speed --episode 02-what-runs-on-8gb --machine pc-rtx2060 --models-dir ~/models --depths 0,16384,32768
```

and bring back the new folder in `episodes/02-what-runs-on-8gb/results/runs/`; `verdict` merges it into
`results/speed.csv`. On the PC, `speed` also samples nvidia-smi: peak VRAM and average power per model.

`run` streams the responses (time to first token in `ttft_s`) and samples nvidia-smi on the PC (peak VRAM, power,
Wh): locally when the client is the PC, over ssh when `AIBENCH_SERVER_HOST` is set. `--no-stream` and
`--no-gpu-sampling` turn them off; without a GPU the columns stay empty.
`speed` measures GGUF files with `llama-bench`; models only available in Ollama have no speed measurement.

## RunPod (rented GPU)

Cost: the hourly price of the chosen GPU, plus the time to start the pod and download the model (~4 to 5 min per
session). Reference from October 2026: ~US$0.27/h for an RTX A5000 24 GB on Secure Cloud (check the day's price in the
console). Time: ~30 to 60 min per model for `run`. **Delete the pod at the end**: left on, it keeps billing.

1. Create the pod with the `ghcr.io/ggml-org/llama.cpp:full-cuda` image, disk for the GGUF and SSH enabled.
2. On the pod: download the GGUF and start `llama-server -m /workspace/<file>.gguf -c 65536 -ngl 99 -fa on --jinja --port 8080`.
3. On the client, open the tunnel (the connection details are in the pod's console) and run:

```bash
ssh -N -L 8080:localhost:8080 <pod-ssh-connection> &
export AIBENCH_SERVER_KEY=""   # only if the server uses --api-key
export AIBENCH_SERVER_HOST="<pod-ssh-connection>"   # env.json records the pod's hardware (needs python3 on the pod)
python3 -m aibench run --episode 01-buy-or-rent-gpu --machine runpod --models gemma4-12b --label a5000-gemma4-12b
```

4. Speed, on the pod itself (copy the repository folder to `/workspace`):

```bash
python3 -m aibench speed --episode 01-buy-or-rent-gpu --machine runpod --models-dir /workspace --depths 0,16384,65536
```

## Calibration anchors (OpenRouter, paid)

The anchors (`anchors.toml`: two ceilings and one floor, METHODOLOGY.md 8.2) run the same batteries once per battery
version; their scores are the ruler for every episode (`pct_of_ceiling`, `normalized`, `calibrated` in
`scores.csv`). Check the anchors' sampling against their model cards first (`verified = true` in `anchors.toml`),
and that each anchor's `[anchor.provider]` endpoint is still listed with `seed` and `tools` in
`https://openrouter.ai/api/v1/models/<id>/endpoints`: with no fallback, an endpoint that is gone or down turns every
call into an error row.

Cost: whatever OpenRouter charges per token, recorded in `cost_usd`. Every anchor makes cases × runs calls
(80 × 3 = 240 today, 720 for the three anchors): about US$1 or less in total per battery version (estimate in METHODOLOGY.md
8.2). Time: ~5 to 60 min per anchor (`z-ai/glm-5.3-flash` at effort `max` is the slowest).

```bash
python3 -m aibench calibrate --simulate --label dry-run   # free, no network: checks the plumbing
export OPENROUTER_API_KEY="…"      # from your password manager; never in a repository file
python3 -m aibench calibrate --label anchors              # all anchors, all batteries, 3 runs
python3 -m aibench calibration                            # merge into calibration/anchors.csv
```

`calibration` also writes the case pruning report, `calibration/pruning.md` (METHODOLOGY.md 8.3): which cases are too
easy (every anchor passes, the floor included), which are suspect (no ceiling passes) and how many cases each
battery needs to reach 15 to 20. Edit the batteries by hand and log the change in `cases/CHANGELOG.md`.

`--models` runs a subset of the anchors and `--use-cases` a subset of the batteries. `--cases id1,id2` runs only
those cases, to screen new or doubtful cases cheaply before the full run; it needs `--smoke`, because a partial
battery gives no battery score, so the run stays out of `calibration/anchors.csv`:

```bash
python3 -m aibench calibrate --smoke --cases weather_call,is_palindrome --label screen
```

To fix the checker, a tier or a case's expected values after an anchor run, edit the battery and rescore the saved
answers instead of paying for a new run (free, no network; it refuses a case whose prompt, history or tools changed):

```bash
python3 -m aibench rescore calibration/runs/<run id>   # writes <run id>-rescored-<date>/ next to it
python3 -m aibench calibration                         # the rescored run stands in for its source
```

The prices are read from the model list at run time and go into `meta.json`. OpenRouter's list is public; through a
proxy (`--url`), the `OPENROUTER_API_KEY` is sent with that read too.

## OpenRouter (cloud, paid): judge only

OpenRouter models are not contestants (METHODOLOGY.md 8.1). The optional judge scores the Portuguese chat cases with
a rubric; it adds cents per run:

```bash
export OPENROUTER_API_KEY="…"      # from your password manager; never in a repository file
python3 -m aibench run --episode 02-what-runs-on-8gb --machine pc-rtx2060 --models neohorse-4b --judge z-ai/glm-5.3-flash --label neohorse-4b
```

The runner refuses a judge that is one of the compared models. The judge goes to OpenRouter (it needs
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
python3 -m aibench verdict --episode 02-what-runs-on-8gb
export PRIVATE_TERMS_FILE=<path to the private list of terms, outside this repository>
./scripts/pre-publish-check.sh
```
