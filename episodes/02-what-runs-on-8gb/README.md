# Episode 2: What runs on 8 GB?

Local models on a PC with an 8 GB RTX 2060 Super (target `pc-rtx2060`): what fits in 8 GB of VRAM, what still works
when part of the model spills to the CPU, how fast it runs and what each model is good for.

- `models.toml`: models, GGUF files, pinned sampling and the machines each one runs on (groups small, medium and limit).
- `results/speed.csv`: `llama-bench` per model and depth. A model that does not fit gets `status=error` and the reason.
- `results/scores.csv`, `verdicts.csv`, `verdicts.md`: per-use-case scores (coding, RAG, agent, chat in Portuguese)
  and the Good for / Not good for verdict per model and machine.
- `results/runs/2026-11-02-*`: pilot runs (before calibration, METHODOLOGY.md section 8). Not publishable.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
