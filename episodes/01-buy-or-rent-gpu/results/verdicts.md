| Model | Machine | Coding | RAG (answers with sources) | Agents / tool calling | Chat & summaries in Portuguese | Good for | Not good for |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `gemma4-12b@think-2048` | runpod | 87% ✅ | 97% ✅ | 100% ✅ | 96% ✅ | Coding; RAG (answers with sources); Agents / tool calling; Chat & summaries in Portuguese | — |
| `qwen3.8-27b-q3@think-2048` | runpod | 92% ✅ | 98% ✅ | 100% ✅ | 87% ✅ | Coding; RAG (answers with sources); Agents / tool calling; Chat & summaries in Portuguese (easy only) | — |
| `qwen3.8-27b-q4@think-2048` | runpod | 88% ✅ | 98% ✅ | 100% ✅ | 84% ✅ | Coding; RAG (answers with sources); Agents / tool calling; Chat & summaries in Portuguese (easy only) (borderline) | — |

Good for: Coding ≥ 80%, RAG (answers with sources) ≥ 80%, Agents / tool calling ≥ 80%, Chat & summaries in Portuguese ≥ 80%, over at least 3 runs. Unstable: the repeats fall on both sides of the threshold. See METHODOLOGY.md.

Batteries: Coding v2 (`9ba2c5db525d`); RAG (answers with sources) v2 (`5263567493a5`); Agents / tool calling v2 (`00cdb8195bc8`); Chat & summaries in Portuguese v2 (`c578c34b848c`); Coding, public sets (reference) v2 (`908376ec7f97`).
