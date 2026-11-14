# Episode 5: RAG with a long document: 3,000 or 24,000 words?

Seven of the local models of episode 02's battery runs, on the PC with the RTX 2060 Super, with the same GGUF,
pinned sampling and thinking budget (2048). Only the RAG battery runs here, 3 times, with the long documents
generated at 24,000 words (`--context-words 24000`) instead of the default 3,000.

The question: does a model's RAG verdict, measured with documents of about 3,000 words, still hold when the document
grows to 24,000?

- Only 4 of the 20 RAG cases use the generated long document (`long_*`, all hard); the other 16 are the same as in
  episode 02. So the overall RAG score can move by at most 20 points, and the long cases are 12 executions per
  model (4 cases x 3 runs): one execution is about 8 points of that subset.
- The document size is part of the battery version (`battery` in the results), so these runs live in their own
  episode: episode 02 merges only one battery version per use case.
- No calibration anchor has run the 24,000-word battery, so the relative columns are empty here; the comparison is
  each model against its own episode 02 score.
- The server needs a context of 65,536 tokens or more (the PC's presets use 131,072, or 90,112 for ornith1.5-9b).

- `models.toml`: the models, copied from episode 02 (without qwen3.8-27b-q3, which has no battery run there, and qwen3.5-9b, no longer on
  the PC).
- `results/verdicts.md` and `scores.csv`: RAG score, verdict, time and TTFT per model at 24,000 words.

Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
