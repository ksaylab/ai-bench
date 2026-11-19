| Model | Machine | Coding | RAG (answers with sources) | Agents / tool calling | Chat & summaries in Portuguese | Good for | Not good for | Unstable ⚠️ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `gemma4-12b@think-2048` | pc-rtx2060 | — | 93% ✅ | 97% ✅ | 91% ✅ | RAG (answers with sources); Agents / tool calling; Chat & summaries in Portuguese | — | — |
| `gemma4-26b@think-2048` | pc-rtx2060 | — | 95% ✅ | 98% ✅ | 100% ✅ | RAG (answers with sources); Agents / tool calling; Chat & summaries in Portuguese | — | — |
| `gemma4-e4b@think-2048` | pc-rtx2060 | — | 74% ❌ | 95% ✅ | 80% ⚠️ | Agents / tool calling | RAG (answers with sources) | Chat & summaries in Portuguese (borderline) |
| `lfm3-1.7b@think-2048` | pc-rtx2060 | — | 91% ✅ | 88% ✅ | 79% ⚠️ | RAG (answers with sources); Agents / tool calling | — | Chat & summaries in Portuguese (borderline) |
| `neohorse-4b@think-2048` | pc-rtx2060 | — | 88% ✅ | 85% ⚠️ | 73% ❌ | RAG (answers with sources) | Chat & summaries in Portuguese | Agents / tool calling |
| `ornith1.5-9b@think-2048` | pc-rtx2060 | — | 93% ✅ | 95% ✅ | 86% ⚠️ | RAG (answers with sources) (mixed tiers); Agents / tool calling (easy only) | — | Chat & summaries in Portuguese |
| `qwen3.6-35b-a3b@think-2048` | pc-rtx2060 | — | 93% ✅ | 80% ⚠️ | 94% ✅ | RAG (answers with sources); Chat & summaries in Portuguese | — | Agents / tool calling (borderline) |

Good for: Coding ≥ 80%, RAG (answers with sources) ≥ 80%, Agents / tool calling ≥ 80%, Chat & summaries in Portuguese ≥ 80%, over at least 3 runs. Unstable: the repeats fall on both sides of the threshold. See METHODOLOGY.md.

Batteries: RAG (answers with sources) v4 (`df0f60dedfec`); Agents / tool calling v4 (`28178aaf6f13`); Chat & summaries in Portuguese v4 (`bcaa947ab167`).
