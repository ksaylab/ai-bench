# Episode 8: What if the floor also reasons?

Episode 06 made the batteries harder (v3) by screening cases on the floor anchor, which answers without reasoning.
The floor fell a lot, but the seven local models, which reason with up to 2048 tokens, barely moved. This episode adds
a small model that reasons, `ibm-granite/granite-4.2-8b`, as a reference anchor (METHODOLOGY.md 8.2: shown next to
the ruler, never part of it), screens new cases on it, and runs the seven local models of episode 06 on the result
(v4) on the PC with the RTX 2060 Super.

The questions:
- How does a small model that reasons score on v3? Is v3 easy for it?
- Can new cases be found that it fails and a ceiling passes?
- Do the local models' scores and verdicts change from v3 to v4?

Batteries: v4 of `agent`, `chat_pt` and `rag` (`cases/versions.csv`, `cases/CHANGELOG.md` of 2026-11-19): v3 plus 7
screened cases. The battery version (v3, v4) is in `battery_version` in `results/scores.csv` and under
`results/verdicts.md`.

## Results (2026-11-18 to 2026-11-19)

- On v3, the reasoning reference scored 78.4% in `agent`, 93.0% in `chat_pt` and 94.4% in `rag`
  (`calibration/runs/2026-11-18-1731-openrouter-granite-reference`): `chat_pt` and `rag` were easy for it, `agent` was
  not. It reasons with `reasoning.enabled` (OpenRouter turned a 2048-token budget into its low-effort mode, which
  reasoned one line); about 20% of its answers reasoned past 2048 tokens.
- Screening 21 candidates on it (a smoke run, not published) kept 7 that `z-ai/glm-5.3-flash` passed in every
  repeat and the reference failed at least once: 3 in `agent`, 3 in `chat_pt`, 1 in `rag`. The 14 left out and why
  are in `cases/CHANGELOG.md`.
- On v4 (`calibration/runs/2026-11-19-0820-openrouter-anchors-v4`) the ceilings stayed at 95.5% to 100%, the floor
  at 18.3% to 31.6%, and the reference fell to 65.0% in `agent` (it failed the 3 new cases in every repeat), 92.4% in
  `chat_pt` and 82.5% in `rag`. No new case is suspect; `weekday_new_year_2027` came out too easy (the floor passed
  it in every repeat) and stays, so that v4 needs no second anchor run.
- The seven local models, on the PC with llama.cpp 1.0 and the MoE-cache presets of episode 07, all scored above the
  reference in `agent` (80.0% to 98.3%). From v3 to v4 their scores changed by 2.7 points on average, at most 6.2
  (`neohorse-4b` in `chat_pt`). Verdicts changed only near the 80% line: `qwen3.6-35b-a3b` went from Good for to
  Unstable in `agent` (it failed `refund_budget_skip` twice), `gemma4-e4b` from Not good for to Unstable in
  `chat_pt` and from Unstable to Not good for in `rag`. The other 18 did not change.
- The v3 runs of episode 06 used llama.cpp 0.9 without the MoE cache, so the comparison is not of the battery alone:
  some old cases also changed result between the two runs, in both directions (`qwen3.6-35b-a3b`:
  `two_matching_orders` 2/3 to 0/3, `refund_late_orders` 0/3 to 2/3).
- `ornith1.5-9b`'s first v4 run is not used. Its process ran out of GPU memory three times (CUDA out of memory,
  under its preset with the MTP draft and a 90k context), always on `rag`'s `sev3_no_target`, and the router
  restarted it. The client read each cut stream as an empty answer, so `rag` showed 84.2% for a server failure. Since
  then a stream that ends without a `finish_reason` is asked again (METHODOLOGY.md, "Verdict"). In the second run
  the process ran out of memory three more times, the client asked again each time, and the run has no errors.
  The preset was not changed.

## Files

- `models.toml`: the seven models of episode 06.
- `results/verdicts.md`, `scores.csv`, `executions.csv`: the v4 batteries, 3 runs per model.


Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
