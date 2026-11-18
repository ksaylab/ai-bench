# Episode 7: Is llama.cpp 1.0 worth the update?

llama.cpp v1.0.0 (2026-11-13, build 12359) is the first release with semantic versioning. It also adds an FP8 KV
cache (`-ctk/-ctv f8_e4m3`) and a cache for MoE experts (`--moe-cache-mib`, `--moe-cache-cpu-share`). This episode
measures it against v0.9.0 (build 12110), the build of episodes 05 and 06, on the PC with the RTX 2060 Super, with the
seven models of episode 06 (`models.toml`) and the same GGUF files. Both builds are compiled the same way (CUDA for
sm_75 only, `GGML_CUDA_FA_ALL_QUANTS`), and the version is the only thing that changes.

The questions:
- Speed: `speed` (llama-bench, 3 repetitions, a 512-token prompt and 128 generated tokens, at depths 0, 16,384 and
  32,768) with each build, back to back in the same session, with the settings of episode 02 (default f16 cache,
  `--fit-target 1536` for the models larger than the card). Episode 02 measured build b12070, so it is not reused.
- Scores: the `chat_pt` v3 battery on v1.0.0, against each model's episode 06 score on v0.9.0.
- The FP8 cache on a card without FP8 hardware (Turing): `gemma4-12b` with `q8_0`, `q4_0` and `f8_e4m3`.
- The MoE cache on the two models larger than the card (`qwen3.6-35b-a3b`, `gemma4-26b`).

## Results (2026-11-16 to 2026-11-18)

**Speed (`results/speed.csv`, column `build`).** On the five dense models (`gemma4-12b` with part of it in RAM at
the default f16 cache), v1.0.0 generates within -3.4% to +1.6% of v0.9.0 at every depth (the largest drop:
`gemma4-e4b` at 32,768, 63.7 to 61.5 tokens/s), and processes prompts within -2.2% to +2.4%. With a `q8_0` cache, `gemma4-12b` is about 2% slower on v1.0.0. The two MoE
models vary too much between repetitions in llama-bench (up to ±7 tokens/s) to call a difference.

**Scores (`results/verdicts.md`, `scores.csv`).** No verdict changed. Four models got exactly their episode 06 score
(`lfm3-1.7b`, `neohorse-4b`, `gemma4-e4b`, `ornith1.5-9b`), `qwen3.6-35b-a3b` too (98.2%), `gemma4-26b` went from 98.2%
to 100% and `gemma4-12b` from 93.0% to 91.2% (52 of 57 instead of 53). That one case was in the medium tier, which
fell from 83.3% to 77.8%, so `gemma4-12b` is now Good for `chat_pt` "(easy only)".

**FP8 cache.** v0.9.0 refuses `f8_e4m3`; v1.0.0 runs it on the Turing card. On `gemma4-12b` (v1.0.0) it generates
like `q8_0` with an empty context (40.5 against 40.3 tokens/s) and 8% slower at 32,768 (30.3 against 32.9), with
prompt processing within 2%. Peak VRAM: 7,614 MiB, against 7,674 with `q8_0` and 7,424 with `q4_0`. Its quality was
not measured here.

**MoE cache (`results/moe-cache.csv`).** llama-bench has no MoE cache options, so this was measured on `llama-server`
started alone (no other model loaded): the same prompt, 512 generated tokens 3 times after a warm-up, and a prompt of
about 4,000 tokens for prefill. The cache needs the experts in host memory, so it runs with all of them in RAM
(`-cmoe`) and keeps the most used ones on the GPU. `--moe-cache-cpu-share 0.95` makes the CPU compute 95% of the cache
misses from RAM instead of uploading them.

| Model | Preset v0.9.0 | Preset v1.0.0 | All experts in RAM, no cache | With the cache |
| --- | --- | --- | --- | --- |
| `qwen3.6-35b-a3b` | 29.1 | 28.5 | 26.6 | 43.8 (2,688 MiB, share 0.95) |
| `gemma4-26b` | 29.9 | 30.0 | 26.4 | 46.6 (1,216 MiB, share 0.95) |

Generation in tokens/s. The share is what makes the gain: on `gemma4-26b`, the same cache with share 0 generated 19.0
tokens/s. Peak VRAM with the cache: 7,356 MiB (`qwen3.6-35b-a3b`) and 6,180 MiB (`gemma4-26b`). llama.cpp's
`scripts/moe-cache-tune.py` gave no recommendation: on `gemma4-26b` it found no room for a second cache size (MTP
draft model and a 131,072-token context), and on `qwen3.6-35b-a3b` its time model did not fit the runs (16% off). The
sizes above are the best it measured, measured again the same way as the other rows.

- **Battery with the cache** (`*-moecache` in `models.toml`, the same models and sampling): no verdict changed.
  `qwen3.6-35b-a3b` 96.5% (98.2% without) and `gemma4-26b` 98.2% (100% without), one case each. Generation in the
  battery went up less than in the 512-token test, where the cache stays warm: 32.8 to 39.1 tokens/s (+19%) and 35.1
  to 40.4 (+15%); time per case 7% and 16% shorter.
- **Long prompts** (`results/long-prompt.csv`): a generated shipping log with one lot to find, about 24,000 and
  75,000 tokens, 3 times each, with the cache. No out-of-memory error, which an older `qwen3.6-35b-a3b` preset had hit
  at 75,000 tokens. `qwen3.6-35b-a3b` found the lot 6 of 6 times. `gemma4-26b` found it 3 of 3 times at 24,000 and
  0 of 3 at 75,000, and without the cache it gave the same three wrong answers: that is the model's limit, not the
  cache's. With the cache, its prefill at 75,000 tokens was 6% slower (360 against 385 tokens/s).

After these runs the PC's router presets of both models use the cache.

## Files

- `models.toml`: the seven models of episode 06, plus the two `*-moecache` entries (same model, router preset with
  the MoE cache).
- `results/verdicts.md`, `scores.csv`, `executions.csv`: the `chat_pt` battery on v1.0.0.
- `results/speed.csv`: both builds; the `cache_type` column marks the `gemma4-12b` cache runs.
- `results/moe-cache.csv`, `results/long-prompt.csv`: the `llama-server` measurements above.
- `scripts/moe_bench.py`, `scripts/longprompt_test.py`: the scripts that measured them (llama.cpp's
  `scripts/moe-cache-tune.py` picked the cache sizes tried).

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
