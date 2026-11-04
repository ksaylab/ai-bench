# Methodology

Rules every published result follows. The code enforces the ones it can; the rest are in the checklist at the end.

## 1. Public, synthetic, identical batteries per use case

Every LLM test answers one question per model: **what is it good for, and what is it not good for?** Each use case
has a short battery in [`cases/`](cases/). The batteries are the same for every model and machine, written for this
repository (except the `coding_public` reference battery, 8.5), and scored automatically. Nothing comes from real companies' or people's code, data or conversations.

| Use case | File | Cases | What passes |
| --- | --- | --- | --- |
| `coding` | `cases/coding.jsonl` | 20 | The model writes a Python function; hidden assertions run in an isolated subprocess with a timeout. All assertions must pass. |
| `rag` | `cases/rag.jsonl` + `rag_documents.json` | 20 | The answer is correct **and** cites the source passage as `[n]`. Wrong passage, no citation or extra unrelated citations fail. Includes a question whose answer is not in the document (must say so, with no citation), an outdated vs. newer rule, similar entities and two long generated documents (needle in a haystack). |
| `agent` | `cases/agent.jsonl` + `agent_tools.json` | 15 | Tool/function calling through the API's `tools` field: the right tool, arguments valid against the tool's JSON Schema and equal to the expected values; several calls in one answer when the task needs them; the next step after a fixed history of earlier calls and their results (filter, add up or compare the results, retry after a tool error, ask when an id is missing, do not act past a limit). Also: not calling a tool when none is needed, and JSON output in an exact schema (types, enums, required keys, no extra keys). |
| `chat_pt` | `cases/chat_pt.jsonl` | 15 | Chat and summaries in Brazilian Portuguese: required facts present, length limits (words/sentences/lines), answer in Portuguese, false premises corrected. |
| `coding_public` | `cases/coding_public/cases.jsonl` | 10 | Reference only (8.5): 5 HumanEval and 5 MBPP problems, scored like `coding`, never part of the verdict. |

- Every case has `example_good` and `example_bad`; the tests check that the checker passes the first and fails the
  second. A new case only goes in with both.
- The long RAG documents are generated on the fly by a deterministic generator (no `random`), with a size chosen per
  run (`--context-words`, default 3000). A test pins the text's hash.
- The content of `chat_pt` is in Portuguese on purpose (it tests Portuguese). Everything else in the repository is
  English.

## 2. Score and verdict

For each machine, model and use case:

```
score = passed executions / all executions of the battery, over all runs   (in %)
```

| Verdict | Rule |
| --- | --- |
| **Good for** | score ≥ 80% |
| **Not good for** | score < 80% |
| **Inconclusive** | fewer than 3 runs, or more than 10% of the executions failed for a technical reason (connection or server error) |
| **Unstable** | the worst and the best run fall on different sides of the threshold (shown like Inconclusive, never as Good for / Not good for) |

- The thresholds are in [`aibench/verdict.py`](aibench/verdict.py) (`GOOD_THRESHOLD`, `MIN_RUNS`, `MAX_ERROR_RATE`).
  80% means the model gets at least 4 out of 5 tasks right, on every run: below that, you would have to double-check
  everything it does in that use case.
- **borderline**: the score is less than one case's worth (100 / number of cases in the battery) away from the threshold. The
  video should say so: one case more or less flips the verdict.
- `scores.csv` also has the worst and best run (`min_run_pct`, `max_run_pct`) and `unstable_cases` (cases whose
  pass/fail changed between repeats), so you can see how stable the model is, plus average time, tokens per second
  and cost.
- `verdicts.csv` and `verdicts.md` have one row per model and machine with the four scores, the **Good for** and
  **Not good for** lists, runs, average time and cost: this is the table the video shows.

## 3. Record the environment

Every run writes `env.json`: OS, CPU, memory, GPU (name, VRAM, driver), Python, llama.cpp or Ollama version and,
when the server reports it, the build and the GGUF in use (per model, in router mode). When the model server is
another machine (the PC on the network, a RunPod pod through a tunnel), the hardware is read from that machine over
ssh (`AIBENCH_SERVER_HOST`); without it, `env.json` says the hardware was not recorded instead of recording the
machine that sent the requests. No host name, user name, IP address or paths.
`meta.json` keeps the parameters: models, cases, runs, context size, judge, thresholds, times, the sampling actually
sent with the seed of every repeat, and the model server's command line (`--server-args` or `AIBENCH_SERVER_ARGS`,
with paths and addresses scrubbed).

## 4. At least 3 runs

`run` and `speed` refuse fewer than 3 runs/repetitions. With `--smoke`, they accept fewer, but the run is marked as
not publishable and is left out of `verdict`. Scores are always passed/executions over all runs (e.g. 16/18), never a
single run.

## 5. A judge that does not compete

The verdict comes from the automatic checker only. The judge (optional, `--judge`) gives a 0 to 5 score only on the
cases with a `rubric` (the Portuguese chat cases), in a separate column. The runner refuses a judge that is one of the
compared models. When a judge is used, the episode says which one.

## 6. Cost and time

Each execution records response time, input and output tokens, tokens per second and, in the cloud, the cost in USD
reported by the provider (the judge's cost in its own column). Episode 1 computes the monthly cost from `prices.csv`
and `assumptions.csv`, with the source and date of each price; a price without a source or a date is not published.

## 7. Isolation

- Code written by the models runs in a temporary directory, with `python3 -I`, no environment variables and a
  10-second timeout. It is still model code running on the machine: use `--skip-code` if you do not want that.
- During a local run, nothing else uses the GPU or the model server. Note whether a laptop was plugged in.
- API keys only through environment variables; never in a file in the repository.

## 8. Calibration

The first pilot runs on the PC showed two problems. First, the batteries are too easy: `gemma4-e4b` scored 88.9% in
`coding`, so a frontier model would likely score ~100% and the battery could not tell a good model from a great one.
Second, the scores did not repeat: `neohorse-4b` went from 77.8% to 100% in `coding` between two runs an hour apart,
which flipped its verdict, because sampling was not pinned and, with 6 to 8 cases, one case is worth 12.5 to 16.7
points. This section is the plan to fix both. Since 2026-11-03 every item below is implemented in the code
(marked **implemented**); what is still open is running it and acting on the results:

- the first anchor run (2026-11-03, first battery versions) found every battery too easy: the floor scored 83% to
  100%, so no battery is calibrated. The batteries were then grown to 15 to 20 cases and screened on the anchors
  (8.3); the new versions still need their anchor run;
- the local contestants have not run with pinned sampling on the PC.

Until then, the runs are pilot runs and are not published.

### 8.1 Machines

- **Local contestants run only on the PC with the RTX 2060 Super 8 GB** (Arch Linux, llama.cpp `llama-server`,
  target `pc-rtx2060`). The Mac M5 is no longer part of any episode: it is gone from the targets
  (`aibench/client.py`), from the `machines` lists in the episodes' `models.toml` and from HOW-TO-RUN.md. Episode 2
  is now `02-what-runs-on-8gb` ("What runs on 8 GB?").
- **OpenRouter models are calibration anchors only** (target `openrouter`). They are never "local" contestants and
  never get a Good for / Not good for verdict of their own in an episode table; they appear only as the reference
  line. Episode 3 no longer has an OpenRouter pair.
- **Simulated and dry-run data never go into results.** `--simulate` and `--smoke` runs write
  `"publishable": false` in `meta.json` and `.gitignore` keeps them out of git. `verdict` (`run.excluded` in
  `run.consolidate`) skips a run folder when its `meta.json` is not publishable, says `simulated`, `smoke` or
  `"status": "pilot"`, when the folder name ends in `-simulated` or `-smoke` (so a hand-edited `meta.json` cannot
  bring one back), when its machine is not a current target (for example the old `mac-m5`) and when it ran on
  `openrouter` (anchors live in `calibration/`, 8.2). It prints every skipped folder and why. This covers the local
  dry run `2026-11-02-2048-mac-m5-dry-run-simulated` in episode 3: it is simulated, untracked and never merged; delete
  it from the working copy when convenient. Simulated numbers (perfect scores, 0.01 s per case) are plumbing checks,
  not measurements.
- **The 2026-11-02 runs on the PC are pilot runs, not publishable.** Their `meta.json` has `"publishable": false` and
  `"status": "pilot"`; they stay in `results/runs/` for reference (they motivated this section), and the episode's
  merged `results/*.csv` and `verdicts.md` no longer include them.

### 8.2 Anchors

Every battery is run, with the same prompts, the same `cases/` version and pinned parameters (8.4), on:

- **Ceiling anchors:** 2 strong, low-cost models through OpenRouter. They show what a top open-weights model
  scores today. Expensive closed frontier models are deliberately left out to keep anchor runs cheap.
- **Floor anchor:** one deliberately small, weak model through OpenRouter. It shows what a model with almost no
  skill in the use case scores (format luck, trivial cases).

Anchors, in [`anchors.toml`](anchors.toml) (role and pinned sampling), with ids checked on
`https://openrouter.ai/api/v1/models` on 2026-11-03 (price in USD per 1M input / output tokens on that date):

| Role | OpenRouter id | USD / 1M in / out | Status |
| --- | --- | --- | --- |
| Ceiling | `deepseek/deepseek-v4-pro` | 1.60 / 3.20 | Approved |
| Ceiling | `z-ai/glm-5.3-flash` | 0.0313 / 0.0846 | Approved |
| Floor | `mistralai/ministral-3b-2512` | 0.10 / 0.10 | Approved |

All three accept `temperature`, `top_p`, `seed` and tool calling, so every anchor runs with pinned parameters (8.4).

Cost estimate of one full anchor run (every battery, 37 cases × 3 repeats = 111 calls per anchor, 333 in total, RAG
documents at the default 3000 words): ~45k input tokens per anchor, and 35k to 220k output tokens depending on how
much the model reasons. At the prices above that is about US$0.10 to 0.80 for `deepseek/deepseek-v4-pro`, under
US$0.03 for `z-ai/glm-5.3-flash` and about US$0.01 for `mistralai/ministral-3b-2512`: **under US$1 per battery
version**. The first anchor run, on that battery version, cost US$0.35 (US$0.32 of it `deepseek/deepseek-v4-pro`).
With `coding` and `rag` at 20 cases and `chat_pt` and `agent` at 15 there are 80 cases (240 calls per anchor, 720
in total), harder ones and up to 32768 output tokens per call for the anchors, so expect roughly US$0.80 to 1.60. Every new battery version (after pruning or
new cases) needs a new anchor run.

- The floor must support tool calling, or every `agent` case fails for a technical reason instead of for lack of
  skill. `meta-llama/llama-3.2-1b-instruct` is weaker but its OpenRouter listing has no `tools` parameter, so it
  can only be a floor for `coding`, `rag` and `chat_pt`.
- If the ceiling anchors themselves stay well below 90% on a use case, the battery is too hard or broken for that
  use case (8.7), not a sign that a pricier anchor is needed.
- The judge (`--judge`) must not be one of the anchors. The runner refuses a judge that is one of the compared
  models in the same run, and also one that is listed in `anchors.toml`.
- Anchor ids, prices and accepted parameters change. Each anchor run (`python3 -m aibench calibrate`) records in
  `meta.json`, per anchor, its role, the price per 1M input / output tokens and the accepted parameters read from
  the public `/api/v1/models` list at run time (no key, no cost), plus the date (`anchors_checked`).
- Anchor runs go to `calibration/runs/`, never to an episode; `python3 -m aibench calibration` merges the
  publishable ones into `calibration/anchors.csv` (score of each anchor per use case and battery version).

Every local score is also reported relative to the anchors, in `scores.csv`, when anchor runs exist for the **same
battery version** (8.3):

```
ceiling        = the best ceiling anchor's score on that use case and battery version
floor          = the floor anchor's score on that use case and battery version
pct_of_ceiling = score / ceiling × 100
normalized     = (score − floor) / (ceiling − floor) × 100    (0 = floor, 100 = ceiling)
```

- `ceiling_pct` and `floor_pct` are written next to them, so every relative number can be recomputed from the CSV.
- `normalized` is not clamped: a model below the floor gets a negative value, one above the best ceiling more
  than 100. It is empty when ceiling = floor (the battery separates nobody).
- The best ceiling (not the mean of the two) is the reference, so "N% of the ceiling" means "of the best cheap
  open-weights model we measured"; with only two ceilings the mean would move with the weaker one.
- Without anchor runs for that battery version the columns are empty.

"Model X reaches N% of the ceiling anchors in coding" is the sentence the video can say; a raw 88.9% on a battery
that everyone passes is not.

### 8.3 Difficulty tiers and battery size

- A `tier` field (`easy`, `medium`, `hard`) on every case in `cases/*.jsonl` (implemented): `cases.load` refuses
  a case without one and `tests/test_cases.py` checks it like `example_good` and `example_bad`. `executions.csv`
  has a `tier` column and `scores.csv` one score per tier (`easy_pct`, `medium_pct`, `hard_pct`) next to the
  overall `score_pct`.
- Rough meaning: **easy** = a small local model should pass; **medium** = needs real skill (multi-step logic,
  several constraints at once, longer context); **hard** = ceiling anchors pass and small models usually do not
  (edge cases in the hidden tests, distractor passages, ambiguous tool choice, long schemas).
- **Target: 15 to 20 cases per use case** (`coding` and `rag` have 20, `chat_pt` and `agent` 15), roughly one third per tier. With 18 cases one case is
  worth 5.6 points instead of 12 to 17. All new cases follow section 1: synthetic, written for this repository,
  with `example_good` and `example_bad`.
- The current 27 cases are tagged (best effort, before any anchor run: 11 easy, 15 medium, 1 hard); new cases go
  mainly into `medium` and `hard`. `python3 -m aibench cases` lists them with their tier.

**Discrimination check (case pruning, implemented).** After the anchors and the floor run a new battery version,
`python3 -m aibench calibration` writes `calibration/pruning.csv` (one row per case: each anchor's passed/executions
and the suggested action) and `calibration/pruning.md` (per use case: cases, tiers, flagged cases, how many are kept
and how far the battery is from the 15 to 20 target). Every case is looked at once:

| Result over all repeats | Action |
| --- | --- |
| All ceiling anchors **and** the floor pass, on every repeat (`too_easy`) | Too easy: removed, or rewritten harder. It cannot separate anyone. |
| No ceiling anchor passes on any repeat (`suspect`) | Reviewed: most likely a wrong expected value, a too strict checker or an ambiguous prompt. Fixed or removed. |
| One ceiling passes every repeat and another fails every repeat (`ceilings_disagree`) | Reviewed: check the prompt is unambiguous. |

- The check uses **only the anchors and the floor, never the local contestants**, so the battery is not tuned to
  make a particular local model look good or bad.
- After the check the battery version is frozen for the episode. Each run records the version of every battery
  (`cases.battery_hash`: SHA-256 of the checker version `cases.CHECKER_VERSION`, raised with any change to the
  checking rules that can flip a verdict, of the use case's files, plus the size of the generated RAG documents) in
  `meta.json` (`battery`) and in the `battery` column of `executions.csv` and `scores.csv`; `verdict` refuses to
  merge runs made with different versions of the same battery, and the anchors are only matched on the same
  version.
- Removed cases and the reason go into [`cases/CHANGELOG.md`](cases/CHANGELOG.md), so the pruning is public. The
  tool only suggests: a person edits the battery and the changelog.

**Screening new cases (before they enter a battery).** A candidate is run on the anchors only, 3 repeats each, in
order of cost: the floor first, and a candidate it passes on every repeat is dropped or made harder; then
`z-ai/glm-5.3-flash`, and a candidate it passes on most repeats is kept. Only the candidates it fails go to effort
`max` and then to `deepseek/deepseek-v4-pro`; one that no ceiling passes is reviewed like a `suspect` case (most
often the prompt is ambiguous). The screening may run the GLM at effort `high` to save time: it only decides which
candidates enter, and the anchor run of the new battery version uses the pinned settings (8.4). In the `coding`
screening of 2026-11-03, the floor failed 17 of 20 candidates on every repeat and the GLM passed all 17 (one only
after its prompt was made unambiguous); in the `rag` screening, the floor passed 8 of 24 candidates on every
repeat and the GLM passed the other 16; in the `chat_pt` screening, the floor passed 11 of 22 and the GLM passed
the other 11 (one only at effort `max`); in the `agent` screening, the floor passed 22 of 33 and the GLM passed
the other 11.

### 8.4 Reproducibility

- **Pinned sampling per model (implemented).** A `[model.sampling]` table in `models.toml` (and `[anchor.sampling]`
  in `anchors.toml`) with `temperature`, `top_p`, `top_k`, `min_p`, `presence_penalty` and `seed`, taken from the
  model card's recommended settings: the card's link goes in `card`, and `verified = true` once checked (the runner
  warns while it is `false`). Every table was checked against its card on 2026-11-03. When a card gives more than
  one set, a model keeps one set for every battery, in its default (thinking) mode: the Qwen3.6 and Ornith tables
  use the cards' precise-coding set (temperature 0.6, `presence_penalty` 0.0), Ministral 3 uses the 0.1 the card
  recommends in its text (not the 0.15 of its code examples), and NeoHorse uses the evaluation protocol on its card,
  which gives no explicit recommendation. `source` says which set each table took. `run.run` sends them
  through `client.chat(sampling=...)` and `meta.json` records the values actually sent (`sampling.<model>.sent`).
  A model without a `sampling` table, or without a `seed`, cannot be run without `--smoke`; unknown keys are refused.
- **One pinned provider per anchor (implemented).** On OpenRouter the same model is served by many providers, at
  different precisions, and several of them silently ignore `seed` (among them Z.AI's own endpoint for
  `z-ai/glm-5.3-flash`). Each anchor has an `[anchor.provider]` table, sent as OpenRouter's `provider` routing
  object: one endpoint in `order` (fp8, with `seed` and tool calling: `novita/fp8` for both ceilings, `mistral`
  for the floor), `allow_fallbacks = false`, and `require_parameters = true`, so a provider that would drop a
  parameter refuses the call (an error row) instead of answering without it. An anchor run without such a table
  needs `--smoke`. `meta.json` records the table (`anchors.<model>.provider`) and `responses.jsonl` the provider that
  answered each call. A provider that accepts `seed` does not promise identical output on batched GPU servers: what
  this pins is that the seed is sent and the provider and precision do not change during a run; what still varies
  shows in the min–max range.
- **Pinned reasoning effort per anchor (implemented).** Without it, the effort is whatever the provider (or a proxy
  in front of OpenRouter) defaults to. An optional `[anchor.reasoning]` table is sent as OpenRouter's `reasoning`
  object: `effort = "max"` for `z-ai/glm-5.3-flash` (its card, also for benchmark reproduction) and `"high"` for
  `deepseek/deepseek-v4-pro` (DeepSeek's API default; Think Max needs its own system prompt and a 384K context).
  The floor has none: its only endpoint does not take `reasoning`, and with `require_parameters` sending it would
  leave no provider. `meta.json` records it (`anchors.<model>.reasoning`); unknown keys are refused.
  The anchors also get more room: `calibrate` defaults to `--max-tokens 32768` (8192 for `run`). In the first anchor
  run, 4 of the 333 answers were cut at 8192 while still reasoning (`deepseek/deepseek-v4-pro` on `humaneval_129`
  twice and `humaneval_46`, `z-ai/glm-5.3-flash` on `parse_duration`); a cut ceiling fails for lack of room, not
  of skill, and lowers the ruler of the whole battery. Only the cases that reason long use the extra room, so the
  cost barely changes.
- The `seed` is fixed per repeat: base seed + repeat number (`run.rep_seed`), recorded in the `seed` column of
  `executions.csv` and in `meta.json`, so a repeat is reproducible on the same build and GGUF, while the repeats
  still differ from each other.
- **Local server settings are recorded (implemented):** the `llama-server` command line (context size, `-ngl`,
  `-fa`, `--n-cpu-moe`, `--parallel`) goes into `meta.json` (`server_args`, from `--server-args` or
  `AIBENCH_SERVER_ARGS`); `env.json` keeps the build and the GGUF. Use `--parallel 1` so batching does not change the
  results.
- **At least 3 repeats**, as today (`MIN_RUNS`). For the calibration episodes the target is 5 for the local
  contestants when time allows.
- Scores are reported as **mean and min–max over the repeats**. `scores.csv` already has `score_pct`,
  `min_run_pct` and `max_run_pct`; the video shows the range, not only the mean.
- **A verdict is published only if it is stable (implemented).** Rule in `aibench/verdict.py`: if the worst run and
  the best run fall on different sides of the threshold, the verdict is **Unstable** (shown like Inconclusive, with
  its own column in `verdicts.csv` and `verdicts.md`) instead of Good for / Not good for. `unstable_cases` in
  `scores.csv` counts the cases whose result changed between repeats. The existing **borderline** mark stays.
- **Raw responses are saved for audit (implemented).** Each run writes `responses.jsonl` next to `executions.csv`:
  one line per execution (same order) with the case, repeat, seed, the checker's result and reason, and the model's
  text, reasoning, tool calls, finish reason and the technical error, if any, so a failure can be traced to the
  model or to the checker. The cases are synthetic, so the file holds nothing private; it still goes
  through `./scripts/pre-publish-check.sh`.

### 8.5 External sanity check (coding)

- **Implemented:** a small `coding_public` battery (10 problems) in `cases/coding_public/`, taken from well-known
  public sets, scored with the same isolated subprocess as `coding`:
  - 5 from HumanEval (`openai/human-eval`, MIT license: the copyright notice is kept in `LICENSE-HumanEval`);
  - 5 from MBPP, sanitized split (`google-research/google-research`, `mbpp/`, CC BY 4.0: attribution in the NOTICE).
  Each case carries `source` and `license` fields (`cases.load` refuses one without them), and
  `cases/coding_public/NOTICE.md` lists them with the changes made. They are the only cases in the repository not
  written for it. It runs by default with the other batteries (`--use-cases` to leave it out).
- It is **not part of the verdict** (`Reference only` in `scores.csv`; `coding_public_pct` in `verdicts.csv`). Public problems are very likely in the models' training data, so a high score
  there says little. It only answers one question: does our ranking agree with the public one?
- The anchors and the local models are ranked on `coding` and on `coding_public`, and both rankings are compared
  with the HumanEval / MBPP numbers in the model cards or public leaderboards, where they exist (with source and
  date). If our `coding` ranking disagrees clearly with both, the `coding` battery is reviewed before publishing.

### 8.6 Metrics to add

Local (PC):

| Metric | How | Status |
| --- | --- | --- |
| Prompt processing and generation speed (pp512, tg128, tok/s at several depths) | `python3 -m aibench speed` (`aibench/speed.py`, `llama-bench`, ≥ 3 repetitions); each speed run writes `meta.json` and `verdict` merges the publishable ones into `results/speed.csv` | Implemented; not yet run on the PC for episodes 2 and 3 |
| Time to first token (TTFT) | streaming responses in `client.chat` (`ttft_s` in `executions.csv`, `avg_ttft_s` in `scores.csv`); with `--no-stream`, llama-server's reported prompt time instead | Implemented |
| Peak VRAM (MiB) | `nvidia-smi --query-gpu=index,memory.used,power.draw -lms 500` sampled during the run where the model server runs (over ssh with `AIBENCH_SERVER_HOST`), `aibench/gpu.py`: `peak_vram_mib` per execution and use case, and in `speed.csv` | Implemented |
| Power (W, average and peak; Wh per battery) | same sampler: `avg_power_w` and `energy_wh` per execution, `avg_power_w` and `wh_per_run` (Wh per battery run) in `scores.csv`, peak power per model in `meta.json` (`gpu_sampling`) | Implemented |

- Without nvidia-smi (no NVIDIA GPU, a remote server without `AIBENCH_SERVER_HOST`, OpenRouter, simulated runs)
  the GPU columns stay empty and `meta.json` says why (`gpu_sampling.<model>.status`); the run itself is unaffected.
  `--no-gpu-sampling` turns it off.
- The sampler reads GPU 0 every 500 ms. An execution shorter than that gets the last sample before it ends, so
  per-execution numbers of very short cases are approximate; the per-battery numbers are what the video uses.
- The `tok_s` column of `executions.csv` is completion tokens divided by the whole response time (prompt processing
  included); `gen_tok_s` divides by the time after the first token. Neither replaces `speed`, which the video uses
  for speed.

OpenRouter anchors:

| Metric | How | Status |
| --- | --- | --- |
| Cost per execution and per battery (USD) | `cost_usd` reported by OpenRouter | Exists |
| Price per 1M input / output tokens | read from `/api/v1/models` at run time, with the date, into `meta.json` | Implemented (`calibrate`) |

### 8.7 Verdict rules with anchors

- The absolute rule stays: **Good for** = score ≥ 80% (`GOOD_THRESHOLD`), over at least 3 runs. 80% keeps its
  practical meaning (4 out of 5 tasks right).
- **A use case only gets verdicts if its battery is calibrated (implemented):** the best ceiling score is ≥ 90%
  and the floor score is ≤ 40% on the frozen battery (`CALIBRATED_CEILING_MIN`, `CALIBRATED_FLOOR_MAX` in
  `aibench/verdict.py`; `calibrated` column in `scores.csv`: 1, 0, or empty when there are no anchor runs for that
  battery version yet). Otherwise that use case is shown as **Not calibrated** for every model and the battery goes
  back to 8.3. (The 90% / 40% values are a starting point, to be reviewed after the first anchor run.)
- **The verdict says up to which tier (implemented):** "Good for" is qualified with the tiers, counted from easy up,
  where the model scores ≥ 80% (`tier_qualifier` in `scores.csv`), e.g. "Good for coding (easy and medium)". A model
  that is ≥ 80% overall only because of the easy tier gets "Good for coding (easy only)". No qualifier when it passes
  every tier present in the battery.
- **Stable** (8.4): the verdict is published only if every repeat falls on the same side of the threshold.
- `pct_of_ceiling` and `normalized` (8.2) are shown next to the score, never instead of it, and do not change the
  verdict.

## Before publishing (checklist)

1. `./scripts/pre-publish-check.sh` passes (tests, secret patterns, private terms, commit authors and gitleaks).
2. No private project, company, person or machine names in the files or the history.
3. No IP addresses, internal service ports, tokens or home paths.
4. Commit e-mails are GitHub noreply addresses.
5. Prices have a source and a date, with `status` CONFIRMED.
6. Every number in the video points to a CSV in this repository.
7. No simulated, smoke or pilot run in the results (`verdict` lists what it skipped); every published use case has
   `calibrated` = 1 in `scores.csv` and every published verdict is stable across repeats (no Unstable).
