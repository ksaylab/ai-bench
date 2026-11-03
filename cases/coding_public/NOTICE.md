# coding_public: third-party problems

The cases in `cases.jsonl` are the only cases in this repository not written for it (METHODOLOGY.md 8.5). They are
a reference battery: scored like `coding`, never part of a Good for / Not good for verdict.

## HumanEval

Copyright (c) OpenAI (https://openai.com). MIT License: the full notice is in
[`LICENSE-HumanEval`](LICENSE-HumanEval), which must be kept with these cases.
Source: https://github.com/openai/human-eval (`data/HumanEval.jsonl.gz`).
Paper: M. Chen et al., "Evaluating Large Language Models Trained on Code", 2021, arXiv:2107.03374.

## MBPP (sanitized split)

"Mostly Basic Python Problems", Google Research, licensed under Creative Commons Attribution 4.0 International
(CC BY 4.0, https://creativecommons.org/licenses/by/4.0/).
Source: https://github.com/google-research/google-research/tree/master/mbpp (`sanitized-mbpp.json`).
Paper: J. Austin et al., "Program Synthesis with Large Language Models", 2021, arXiv:2108.07732.

## Changes made here

- Selection: 5 HumanEval and 5 MBPP problems, listed below.
- Prompts: an instruction line is added before the original text (HumanEval: "Complete the Python function
  below..."; MBPP: "Write only the Python function..." and, as in the MBPP paper, the first test case). The original
  problem text, typos included, is unchanged.
- Tests: HumanEval's `check` function followed by `check(<entry point>)`; MBPP's `test_imports` and `test_list`.
- `example_good` is the original reference solution; `example_bad` is a wrong solution written for this
  repository, so the checker can be tested.
- `tier` is our own difficulty tag.

## Cases

| Case | Source | License |
| --- | --- | --- |
| `humaneval_0` | HumanEval/0 (openai/human-eval, data/HumanEval.jsonl.gz) | MIT |
| `humaneval_12` | HumanEval/12 (openai/human-eval, data/HumanEval.jsonl.gz) | MIT |
| `humaneval_46` | HumanEval/46 (openai/human-eval, data/HumanEval.jsonl.gz) | MIT |
| `humaneval_108` | HumanEval/108 (openai/human-eval, data/HumanEval.jsonl.gz) | MIT |
| `humaneval_129` | HumanEval/129 (openai/human-eval, data/HumanEval.jsonl.gz) | MIT |
| `mbpp_3` | MBPP sanitized, task_id 3 (google-research/google-research, mbpp/sanitized-mbpp.json) | CC-BY-4.0 |
| `mbpp_4` | MBPP sanitized, task_id 4 (google-research/google-research, mbpp/sanitized-mbpp.json) | CC-BY-4.0 |
| `mbpp_9` | MBPP sanitized, task_id 9 (google-research/google-research, mbpp/sanitized-mbpp.json) | CC-BY-4.0 |
| `mbpp_11` | MBPP sanitized, task_id 11 (google-research/google-research, mbpp/sanitized-mbpp.json) | CC-BY-4.0 |
| `mbpp_20` | MBPP sanitized, task_id 20 (google-research/google-research, mbpp/sanitized-mbpp.json) | CC-BY-4.0 |
