# Episode 5 (repeat): neohorse-4b, 3 more runs at 24,000 words

In episode 05, neohorse-4b's RAG verdict went from Good for (episode 02, 3,000 words) to Unstable (24,000 words),
but 5 of its 6 lost executions came from the 16 cases whose text does not depend on the document size. This folder
runs the same RAG battery at 24,000 words 3 more times, to see whether Unstable repeats.

- Same GGUF, pinned sampling and thinking budget (2048) as episode 05; only the base seed differs (1003, so the
  seeds are 1003-1005, the ones a 6-run episode 05 would have used for repeats 4 to 6).
- Its own folder, so episode 05 stays 3 runs per model like the other six models.

Command: the long-RAG run in [HOW-TO-RUN.md](../../HOW-TO-RUN.md), with `--episode 05-long-rag-repeat`.
