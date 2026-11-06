# Episode 2: What runs on 8 GB?

Local models on a PC with an 8 GB RTX 2060 Super (target `pc-rtx2060`): what fits in 8 GB of VRAM, what still works
when part of the model spills to the CPU, how fast it runs and what each model is good for.

- `models.toml`: models, GGUF files, pinned sampling, thinking level and the machines each one runs on (groups
  small, medium and limit). Every model thinks with a budget of 2048 tokens (`thinking = 2048`, chosen from episode
  04), so the results name them `model@think-2048`.
- `results/speed.csv`: `llama-bench` per model and depth. A model that does not fit gets `status=error` and the reason.
- `results/scores.csv`, `verdicts.csv`, `verdicts.md`: per-use-case scores (coding, RAG, agent, chat in Portuguese)
  and the Good for / Not good for verdict per model and machine.
- `results/runs/`: the six PC models are copies of episode 04's 2048 runs (`copied_from` in `meta.json`). The
  2026-11-02 runs (unpinned sampling) and the 2026-11-04 runs (8192 tokens, or no thinking level) are pilot runs
  (METHODOLOGY.md section 8), kept as data and not merged.
- Not run yet: `gemma4-12b` and `qwen3.8-27b-q3` (no preset on the PC's server yet), and `speed`.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
