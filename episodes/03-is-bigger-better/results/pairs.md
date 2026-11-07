# Is a bigger model better?

Per pair, on the same machine: each battery's score and verdict for the small and the large model, the outcome, and the minutes per battery run. Source: `pairs.csv` (from `scores.csv`) and `speed.csv`.

## 4b-vs-35b: `neohorse-4b@think-2048` vs `qwen3.6-35b-a3b@think-2048` (pc-rtx2060)

| Battery | Small | Large | Points | Outcome | Time per battery run |
| --- | --- | --- | --- | --- | --- |
| Coding | 55% ❌ | 72% ❌ | +17 | neither Good for | 10.8 → 23.7 min (2.2×) |
| RAG (answers with sources) | 92% ✅ | 93% ✅ | +2 | both Good for | 3.0 → 14.5 min (4.8×) |
| Agents / tool calling | 84% ✅ | 87% ✅ | +2 | both Good for | 0.8 → 3.7 min (4.9×) |
| Chat & summaries in Portuguese | 84% ✅ | 98% ✅ | +13 | both Good for | 5.2 → 9.0 min (1.7×) |

Good for only with the large model: none.
Energy for these batteries, one run each: 48.8 → 60.6 Wh.
Generation speed (llama-bench, depth 0): 92.2 → 25.7 tok/s (3.6× slower).
`qwen3.6-35b-a3b` does not fit on the GPU: it runs with part of the model on the CPU.

## e4b-vs-9b: `gemma4-e4b@think-2048` vs `ornith1.5-9b@think-2048` (pc-rtx2060)

| Battery | Small | Large | Points | Outcome | Time per battery run |
| --- | --- | --- | --- | --- | --- |
| Coding | 53% ❌ | 65% ❌ | +12 | neither Good for | 5.2 → 10.9 min (2.1×) |
| RAG (answers with sources) | 78% ⚠️ | 90% ✅ | +12 | unsure (Unstable) | 1.8 → 1.7 min (1.0×) |
| Agents / tool calling | 96% ✅ | 98% ✅ | +2 | both Good for | 0.7 → 0.8 min (1.0×) |
| Chat & summaries in Portuguese | 71% ⚠️ | 82% ✅ | +11 | unsure (Unstable) | 0.8 → 1.5 min (1.9×) |

Good for only with the large model: none.
Energy for these batteries, one run each: 20.9 → 36.5 Wh.
Generation speed (llama-bench, depth 0): 79.4 → 55.7 tok/s (1.4× slower).

## e4b-vs-26b: `gemma4-e4b@think-2048` vs `gemma4-26b@think-2048` (pc-rtx2060)

| Battery | Small | Large | Points | Outcome | Time per battery run |
| --- | --- | --- | --- | --- | --- |
| Coding | 53% ❌ | 87% ✅ | +33 | only the large is Good for | 5.2 → 23.6 min (4.6×) |
| RAG (answers with sources) | 78% ⚠️ | 92% ✅ | +13 | unsure (Unstable) | 1.8 → 9.6 min (5.5×) |
| Agents / tool calling | 96% ✅ | 100% ✅ | +4 | both Good for | 0.7 → 2.6 min (3.5×) |
| Chat & summaries in Portuguese | 71% ⚠️ | 100% ✅ | +29 | unsure (Unstable) | 0.8 → 6.2 min (7.6×) |

Good for only with the large model: Coding.
Energy for these batteries, one run each: 20.9 → 42.5 Wh.
Generation speed (llama-bench, depth 0): 79.4 → 30.6 tok/s (2.6× slower).
`gemma4-26b` does not fit on the GPU: it runs with part of the model on the CPU.

## 12b-vs-27b: `gemma4-12b@think-2048` vs `qwen3.8-27b-q4@think-2048` (runpod)

Not run yet.
