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
  (METHODOLOGY.md section 8), kept as data and not merged. `gemma4-12b` was run on the PC itself on 2026-11-09
  (server preset: 128k context, q4_0 KV cache, every layer on the card). `qwen3.5-9b`, the base of
  `ornith1.5-9b` in the same Q4_K_M quant, was run on 2026-11-10 to compare base and fine-tune (preset: 96k, q8_0 KV
  cache as the Ornith's, no MTP: unsloth's GGUF has no MTP head; 128k with q8_0 does not load).
- `speed`: the six PC models (2026-11-06). `qwen3.6-35b-a3b` and `gemma4-26b` do not fit with every layer on the
  card (error row) and are measured again fitted, part on the CPU (`fit_target_mib` = 1536).
- `speed` for `gemma4-12b` and `qwen3.8-27b-q3` (2026-11-09). With llama-bench's default f16 KV cache,
  `gemma4-12b` does not fit at 32k and the fitted rows leave layers on the CPU (13.8 tok/s); it is measured again
  with the q8_0 KV cache of the server's presets (`cache_type` = q8_0, `--cache-type q8_0`): every layer on the
  card, 41.5 tok/s. `qwen3.8-27b-q3` (13 GB) does not fit and runs at 2.8 tok/s with part of it on the CPU.
- `speed` for `qwen3.5-9b` (2026-11-10): every layer on the card with the f16 KV cache, 57.7 tok/s.
- Not run on the PC: `qwen3.8-27b-q3`, too slow there. At 2.8 tok/s, the 240 executions of a run (~1,300 tokens
  each) would take about 31 hours; its speed rows are the result. Episode 01 runs it on a rented RTX A5000.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
