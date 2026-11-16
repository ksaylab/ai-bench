# Episode 6: Is the battery too easy?

Seven of the local models of episode 02's battery runs, on the PC with the RTX 2060 Super, with the same GGUF,
pinned sampling and thinking budget (2048). Only the three batteries that changed run here, 3 times: `agent`,
`chat_pt` and `rag`, in version 3 (`cases/CHANGELOG.md`, 2026-11-14).

The question: episode 02 measured these models on batteries where the smallest anchor already passed some cases in
every repeat. With those cases removed and harder ones screened in, do the verdicts still hold?

- What changed from v2: each battery lost 2 cases the floor anchor passed in every repeat (a few easy ones stay
  on purpose); new candidates got in only when the floor anchor failed them and `z-ai/glm-5.3-flash` passed them.
  `agent` went from 15 to 17 cases (4 new), `chat_pt` from 15 to 19 (6 new) and `rag` from 20 to 18 (none new).
  `coding` did not change and does not run here.
- The battery version is part of the results (`battery`), so these runs live in their own episode: episode 02 merges
  only one battery version per use case. The comparison is each model against its own episode 02 score.

## Results (2026-11-15)

- The floor anchor (`mistralai/ministral-3b-2512`, no reasoning) fell: from 26.7% to 11.8% in `agent`, 37.8% to
  22.8% in `chat_pt` and 26.7% to 20.4% in `rag`. The best ceiling stayed at 98% to 100%.
- The local models barely moved: from v2 to v3 their scores changed by 2.7 points on average, at most 7.8. They
  reason with up to 2048 tokens and the floor does not, so cases screened on the floor are not much harder for them.
- Verdicts changed only near the 80% line, mostly in `chat_pt`: `lfm3-1.7b` and `ornith1.5-9b` went from Good for to
  Unstable there, `neohorse-4b` to Not good for, and `gemma4-e4b` from Unstable to Not good for (78.9% in every
  repeat). `neohorse-4b` also went from Good for to Unstable in `agent`. The other 16 verdicts did not change.
- With calibrated batteries, `results/scores.csv` now also has the relative columns (`pct_of_ceiling`,
  `normalized`).

- `models.toml`: the models, copied from episode 02 (without qwen3.8-27b-q3, which has no battery run there, and
  qwen3.5-9b, no longer on the PC).
- `results/verdicts.md` and `scores.csv`: score and verdict per model and battery.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
