# Episode 2: What runs on 16 GB and on 8 GB?

The same models on a 16 GB Mac M5 (unified memory) and on a PC with an 8 GB RTX 2060 Super: what fits, how fast it
runs and what each model is good for.

- `models.toml`: models, GGUF files and the machines each one runs on (groups small, medium and limit).
- `results/speed.csv`: `llama-bench` per model and depth. A model that does not fit gets `status=error` and the reason.
- `results/scores.csv`, `verdicts.csv`, `verdicts.md`: per-use-case scores (coding, RAG, agent, chat in Portuguese)
  and the Good for / Not good for verdict per model and machine.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
