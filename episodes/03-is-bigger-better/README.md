# Episode 3: Is a bigger model better?

Small vs large pairs on the same hardware (`pair` in `models.toml`): does the large model earn a "Good for" that the
small one does not, and how much slower and more expensive is it?

- `models.toml`: the pairs, locally (PC with the RTX 2060 Super) and on RunPod: `4b-vs-35b` (neohorse-4b vs
  qwen3.6-35b-a3b), `e4b-vs-9b` (gemma4-e4b vs ornith1.5-9b) and `e4b-vs-26b` (gemma4-e4b vs gemma4-26b) on the PC,
  `12b-vs-27b` (gemma4-12b vs qwen3.8-27b-q4) on RunPod. Every model thinks with a budget of 2048 tokens
  (`thinking = 2048`, chosen from episode 04); the PC runs are copies of episode 04's 2048 runs.
- `results/pairs.md`: the comparison table for the video, per pair (score and verdict of each side per battery, the
  outcome, minutes and energy per battery run, generation speed); `pairs.csv` has its numbers.
- `results/verdicts.md` and `scores.csv`: every model's verdicts and the details (worst and best run, time, tokens
  per second, cost); `speed.csv`: llama-bench per model and depth.
- The RunPod pair `12b-vs-27b` ran on an RTX A5000; its runs are copies of episode 01's.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
