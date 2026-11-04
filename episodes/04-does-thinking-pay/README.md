# Episode 4: Does thinking pay?

The same six local models as episode 02, on the PC with the RTX 2060 Super, each run once per thinking level: off,
a reasoning budget of 512, 2048 or 8192 tokens, and unlimited (`run --thinking`). `max_tokens` is 32768 for every
level, so a level only differs in how long the model may think. Each level is its own contestant in the results
(`model@think-<level>`).

The question: how much does thinking raise the score of each battery, and what does it cost in time?

- `models.toml`: the models, with the same GGUF and pinned sampling as episode 02.
- `results/verdicts.md` and `scores.csv`: score per battery and time per level.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
