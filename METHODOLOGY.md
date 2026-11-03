# Methodology

Rules every published result follows. The code enforces the ones it can; the rest are in the checklist at the end.

## 1. Public, synthetic, identical batteries per use case

Every LLM test answers one question per model: **what is it good for, and what is it not good for?** Each use case
has a short battery in [`cases/`](cases/). The batteries are the same for every model and machine, written for this
repository, and scored automatically. Nothing comes from real companies' or people's code, data or conversations.

| Use case | File | Cases | What passes |
| --- | --- | --- | --- |
| `coding` | `cases/coding.jsonl` | 6 | The model writes a Python function; hidden assertions run in an isolated subprocess with a timeout. All assertions must pass. |
| `rag` | `cases/rag.jsonl` + `rag_documents.json` | 8 | The answer is correct **and** cites the source passage as `[n]`. Wrong passage, no citation or extra unrelated citations fail. Includes a question whose answer is not in the document (must say so, with no citation), an outdated vs. newer rule, similar entities and two long generated documents (needle in a haystack). |
| `agent` | `cases/agent.jsonl` + `agent_tools.json` | 7 | Tool/function calling through the API's `tools` field: exactly one call, the right tool, arguments valid against the tool's JSON Schema and equal to the expected values. Also: not calling a tool when none is needed, and JSON output in an exact schema (types, enums, required keys, no extra keys). |
| `chat_pt` | `cases/chat_pt.jsonl` | 6 | Chat and summaries in Brazilian Portuguese: required facts present, length limits (words/sentences/lines), answer in Portuguese, false premises corrected. |

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

- The thresholds are in [`aibench/verdict.py`](aibench/verdict.py) (`GOOD_THRESHOLD`, `MIN_RUNS`, `MAX_ERROR_RATE`).
  80% means the model gets at least 4 out of 5 tasks right, on every run: below that, you would have to double-check
  everything it does in that use case.
- **borderline**: the score is less than one case's worth (100 / number of cases in the battery) away from the threshold. The
  video should say so: one case more or less flips the verdict.
- `scores.csv` also has the worst and best run (`min_run_pct`, `max_run_pct`), so you can see how stable the model
  is, plus average time, tokens per second and cost.
- `verdicts.csv` and `verdicts.md` have one row per model and machine with the four scores, the **Good for** and
  **Not good for** lists, runs, average time and cost: this is the table the video shows.

## 3. Record the environment

Every run writes `env.json`: OS, CPU, memory, GPU (name, VRAM, driver), Python, llama.cpp or Ollama version and,
when the server reports it, the build and the GGUF in use (per model, in router mode). When the model server is
another machine (the PC on the network, a RunPod pod through a tunnel), the hardware is read from that machine over
ssh (`AIBENCH_SERVER_HOST`); without it, `env.json` says the hardware was not recorded instead of recording the
machine that sent the requests. No host name, user name, IP address or paths.
`meta.json` keeps the parameters: models, cases, runs, context size, judge, thresholds and times.

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
points. This section is the plan to fix both. Items marked **Planned** do not exist in the code yet; until they do,
the runs are pilot runs and are not published.

### 8.1 Machines

- **Local contestants run only on the PC with the RTX 2060 Super 8 GB** (Arch Linux, llama.cpp `llama-server`,
  target `pc-rtx2060`). The Mac M5 is no longer part of any episode. **Planned:** remove `mac-m5` from the
  `machines` lists in the episodes' `models.toml` and from HOW-TO-RUN.md.
- **OpenRouter models are calibration anchors only** (target `openrouter`). They are never "local" contestants and
  never get a Good for / Not good for verdict of their own in an episode table; they appear only as the reference
  line.
- **Simulated and dry-run data never go into results.** `--simulate` and `--smoke` runs already write
  `"publishable": false` in `meta.json`, `verdict` (`run.consolidate`) skips them and `.gitignore` keeps them out of
  git. Their numbers (perfect scores, 0.01 s per case) are plumbing checks, not measurements.

### 8.2 Anchors

Every battery is run, with the same prompts, the same `cases/` version and pinned parameters (8.4), on:

- **Ceiling anchors:** 2 or 3 frontier models through OpenRouter. They show what "the best available" scores today.
- **Floor anchor:** one deliberately small, weak model through OpenRouter. It shows what a model with almost no
  skill in the use case scores (format luck, trivial cases).

Suggested anchors, with ids checked on `https://openrouter.ai/api/v1/models` on 2026-11-03 (price in USD per 1M
input / output tokens on that date). **To be confirmed by the channel before the first anchor run**:

| Role | OpenRouter id | USD / 1M in / out | Sampling parameters the API accepts |
| --- | --- | --- | --- |
| Ceiling | `anthropic/claude-opus-5.5` | 4.00 / 20.00 | no `temperature`, `top_p` or `seed` (provider defaults) |
| Ceiling | `openai/gpt-5.6-sol` | 4.00 / 20.00 | `seed` only; no `temperature` or `top_p` |
| Ceiling (open weights) | `deepseek/deepseek-v4-pro` | 1.60 / 3.20 | `temperature`, `top_p`, `seed`, `presence_penalty` |
| Floor | `mistralai/ministral-3b-2512` | 0.10 / 0.10 | `temperature`, `top_p`, `seed`, tool calling |

- The floor must support tool calling, or every `agent` case fails for a technical reason instead of for lack of
  skill. `meta-llama/llama-3.2-1b-instruct` is weaker but its OpenRouter listing has no `tools` parameter, so it
  can only be a floor for `coding`, `rag` and `chat_pt`.
- Ceiling anchors that do not accept sampling parameters are run with the provider's defaults; that is written in
  `meta.json` and their spread over the repeats (8.4) is reported like any other model's.
- The judge (`--judge`) must not be one of the anchors. The runner already refuses a judge that is one of the
  compared models in the same run; **Planned:** the same check against the anchor list.
- Anchor ids, prices and accepted parameters change. Each anchor run records the id, the date and the price read
  from `/api/v1/models` in `meta.json` (**Planned**).

Every local score is also reported relative to the anchors (**Planned** columns in `scores.csv`):

```
pct_of_ceiling = score / mean(ceiling anchors' scores) × 100
normalized     = (score − floor score) / (mean ceiling score − floor score) × 100    (0 = floor, 100 = ceiling)
```

"Model X reaches N% of the frontier level in coding" is the sentence the video can say; a raw 88.9% on a battery
that everyone passes is not.

### 8.3 Difficulty tiers and battery size

- **Planned:** a `tier` field (`easy`, `medium`, `hard`) on every case in `cases/*.jsonl`, checked by
  `tests/test_cases.py` like `example_good` and `example_bad`. `scores.csv` gets one score per tier
  (`easy_pct`, `medium_pct`, `hard_pct`) next to the overall `score_pct`.
- Rough meaning: **easy** = a small local model should pass; **medium** = needs real skill (multi-step logic,
  several constraints at once, longer context); **hard** = frontier anchors pass and small models usually do not
  (edge cases in the hidden tests, distractor passages, ambiguous tool choice, long schemas).
- **Target: 15 to 20 cases per use case** (today 6 to 8), roughly one third per tier. With 18 cases one case is
  worth 5.6 points instead of 12 to 17. All new cases follow section 1: synthetic, written for this repository,
  with `example_good` and `example_bad`.
- The current 27 cases are tagged first (most are expected to be `easy`); new cases go mainly into `medium` and
  `hard`.

**Discrimination check (case pruning).** After the anchors and the floor run a new battery version, every case is
looked at once:

| Result over all repeats | Action |
| --- | --- |
| All ceiling anchors **and** the floor pass | Too easy: removed, or rewritten harder. It cannot separate anyone. |
| No ceiling anchor passes | Reviewed: most likely a wrong expected value, a too strict checker or an ambiguous prompt. Fixed or removed. |
| Ceiling anchors disagree with each other on every repeat | Reviewed: check the prompt is unambiguous. |

- The check uses **only the anchors and the floor, never the local contestants**, so the battery is not tuned to
  make a particular local model look good or bad.
- After the check the battery version is frozen for the episode. **Planned:** a hash of `cases/` in `meta.json`;
  `verdict` refuses to merge runs made with different battery versions.
- Removed cases and the reason go into a short changelog in `cases/` (**Planned**), so the pruning is public.

### 8.4 Reproducibility

- **Pinned sampling per model (Planned).** A `[model.sampling]` table in `models.toml` with `temperature`,
  `top_p`, `top_k`, `min_p`, `presence_penalty` and `seed`, taken from the model card's recommended settings (the
  card's link goes in a comment next to the table). `run.run` passes them to `client.chat` (which today accepts only
  `temperature` and an `extra` dict, and `run.run` passes neither) and `meta.json` records the values actually sent.
  A model without a `sampling` table cannot be run without `--smoke`.
- The `seed` is fixed per repeat (e.g. base seed + repeat number), so a repeat is reproducible on the same build and
  GGUF, while the repeats still differ from each other.
- **Local server settings are recorded:** the `llama-server` command line (context size, `-ngl`, `-fa`,
  `--n-cpu-moe`, `--parallel`) goes into `meta.json` (**Planned**; today `env.json` records only the build and the
  GGUF). Use `--parallel 1` so batching does not change the results.
- **At least 3 repeats**, as today (`MIN_RUNS`). For the calibration episodes the target is 5 for the local
  contestants when time allows.
- Scores are reported as **mean and min–max over the repeats**. `scores.csv` already has `score_pct`,
  `min_run_pct` and `max_run_pct`; the video shows the range, not only the mean.
- **A verdict is published only if it is stable.** **Planned** rule in `aibench/verdict.py`: if the worst run and
  the best run fall on different sides of the threshold, the verdict is **Unstable** (shown like Inconclusive)
  instead of Good for / Not good for. The existing **borderline** mark stays.
- **Raw responses are saved for audit (Planned).** Each run writes `responses.jsonl` next to `executions.csv`:
  one line per execution with the model's text, reasoning, tool calls and finish reason, so a failure can be
  traced to the model or to the checker. The cases are synthetic, so the file holds nothing private; it still goes
  through `./scripts/pre-publish-check.sh`.

### 8.5 External sanity check (coding)

- **Planned:** a small `coding_public` battery (about 10 problems) taken from well-known public sets, scored with the
  same isolated subprocess as `coding`:
  - HumanEval (`openai/human-eval`, MIT license: the copyright notice must be kept);
  - MBPP, sanitized split (`google-research-datasets/mbpp`, CC BY 4.0: attribution required).
  Each case carries `source` and `license` fields, and a NOTICE file lists them. They are the only cases in the
  repository not written for it.
- It is **not part of the verdict.** Public problems are very likely in the models' training data, so a high score
  there says little. It only answers one question: does our ranking agree with the public one?
- The anchors and the local models are ranked on `coding` and on `coding_public`, and both rankings are compared
  with the HumanEval / MBPP numbers in the model cards or public leaderboards, where they exist (with source and
  date). If our `coding` ranking disagrees clearly with both, the `coding` battery is reviewed before publishing.

### 8.6 Metrics to add

Local (PC):

| Metric | How | Status |
| --- | --- | --- |
| Prompt processing and generation speed (pp512, tg128, tok/s at several depths) | `python3 -m aibench speed` (`aibench/speed.py`, `llama-bench`, ≥ 3 repetitions) | Exists; not yet run on the PC for episodes 2 and 3 |
| Time to first token (TTFT) | streaming responses in `client.chat` | Planned |
| Peak VRAM (MiB) | `nvidia-smi --query-gpu=memory.used` sampled during the run, on the PC | Planned |
| Power (W, average and peak; Wh per battery) | `nvidia-smi --query-gpu=power.draw` sampled during the run, on the PC | Planned |

The `tok_s` column of `executions.csv` today is completion tokens divided by the whole response time (prompt
processing included); it is not the generation speed. The video uses `speed` for speed.

OpenRouter anchors:

| Metric | How | Status |
| --- | --- | --- |
| Cost per execution and per battery (USD) | `cost_usd` reported by OpenRouter | Exists |
| Price per 1M input / output tokens | read from `/api/v1/models` at run time, with the date, into `meta.json` | Planned |

### 8.7 Verdict rules with anchors

- The absolute rule stays: **Good for** = score ≥ 80% (`GOOD_THRESHOLD`), over at least 3 runs. 80% keeps its
  practical meaning (4 out of 5 tasks right).
- **A use case only gets verdicts if its battery is calibrated (Planned):** the mean ceiling score is ≥ 90% and the
  floor score is ≤ 40% on the frozen battery. Otherwise that use case is shown as **Not calibrated** for every model
  and the battery goes back to 8.3. (The 90% / 40% values are a starting point, to be reviewed after the first anchor
  run.)
- **The verdict says up to which tier (Planned):** "Good for" is qualified with the highest tier where the model
  scores ≥ 80%, e.g. "Good for coding (easy and medium)". A model that is ≥ 80% overall only because of the easy
  tier gets "Good for coding (easy only)".
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
7. No simulated, smoke or pilot run in the results; once section 8 is implemented, the battery is calibrated and
   every published verdict is stable across repeats.
