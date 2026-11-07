# Episode 4: Does thinking pay?

The same six local models as episode 02, on the PC with the RTX 2060 Super, each run once per thinking level: off,
or a reasoning budget of 512, 2048 or 8192 tokens (`run --thinking`). `max_tokens` is 32768 for every level, so a
level only differs in how long the model may think. Each level is its own contestant in the results
(`model@think-<level>`). There is no unlimited level
(`--thinking unlimited`): 8192 already gives little over 2048 at about twice the time, so it is not run.

The question: how much does thinking raise the score of each battery, and what does it cost in time?

- `models.toml`: the models, with the same GGUF and pinned sampling as episode 02.
- `results/verdicts.md` and `scores.csv`: score per battery and time per level.
- `results/thinking.csv` and `results/charts/thinking-<battery>.svg`: score against time per model and level
  (`python3 -m aibench thinking`).
- `results/thinking-budget.md` (and `.csv`): the thinking budget per model and battery, the lowest level whose
  score is within 2 points of that model's best level.
- The 2048 runs are also episodes 02 and 03's runs of these models (`copy-run`): those episodes pin `thinking = 2048`.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
