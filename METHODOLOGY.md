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

## Before publishing (checklist)

1. `./scripts/pre-publish-check.sh` passes (tests, secret patterns, private terms, commit authors and gitleaks).
2. No private project, company, person or machine names in the files or the history.
3. No IP addresses, internal service ports, tokens or home paths.
4. Commit e-mails are GitHub noreply addresses.
5. Prices have a source and a date, with `status` CONFIRMED.
6. Every number in the video points to a CSV in this repository.
