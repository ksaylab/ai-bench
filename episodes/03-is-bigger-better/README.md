# Episode 3: Is a bigger model better?

Small vs large pairs on the same hardware (`pair` in `models.toml`): does the large model earn a "Good for" that the
small one does not, and how much slower and more expensive is it?

- `models.toml`: the pairs, locally (PC with the RTX 2060 Super) and on RunPod. Every model thinks with a budget of
  2048 tokens (`thinking = 2048`, chosen from episode 04); the PC runs are copies of episode 04's 2048 runs.
- `results/verdicts.md`: the comparison table for the video; `scores.csv` has the details (worst and best run, time,
  tokens per second, cost).

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
