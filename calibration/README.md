# Calibration

The anchor runs (METHODOLOGY.md 8.2): the same batteries on the OpenRouter anchors listed in
[`anchors.toml`](../anchors.toml), two ceilings and one floor. They are the ruler for every episode: the
`pct_of_ceiling` and `normalized` columns of the episodes' `scores.csv` and the pruning report come from here.

- `runs/<date>-openrouter-<label>/`: one folder per `python3 -m aibench calibrate` run (same files as an episode run,
  plus the anchors' roles and prices in `meta.json`).
- `anchors.csv`: written by `python3 -m aibench calibration`: the score of each anchor per use case and battery
  version, and the reference (best ceiling, floor) used by the episodes.
- `pruning.csv`, `pruning.md`: the per-case discrimination check (METHODOLOGY.md 8.3) and how far each battery is
  from 15 to 20 cases.

Commands: [HOW-TO-RUN.md](../HOW-TO-RUN.md#calibration-anchors-openrouter-paid).
