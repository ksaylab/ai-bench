| Model | Machine | Coding | RAG (answers with sources) | Agents / tool calling | Chat & summaries in Portuguese | Good for | Not good for | Unstable ⚠️ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `deepseek/deepseek-v4-pro` | openrouter | — | 100% ✅ | 97% ✅ | 100% ✅ | RAG (answers with sources); Agents / tool calling; Chat & summaries in Portuguese | — | — |
| `ibm-granite/granite-4.2-8b` | openrouter | — | 82% ⚠️ | 65% ❌ | 92% ✅ | Chat & summaries in Portuguese | Agents / tool calling | RAG (answers with sources) (borderline) |
| `mistralai/ministral-3b-2512` | openrouter | — | 32% ❌ | 18% ❌ | 20% ❌ | — | RAG (answers with sources); Agents / tool calling; Chat & summaries in Portuguese | — |
| `z-ai/glm-5.3-flash` | openrouter | — | 98% ✅ | 100% ✅ | 96% ✅ | RAG (answers with sources); Agents / tool calling; Chat & summaries in Portuguese | — | — |

Good for: Coding ≥ 80%, RAG (answers with sources) ≥ 80%, Agents / tool calling ≥ 80%, Chat & summaries in Portuguese ≥ 80%, over at least 3 runs. Unstable: the repeats fall on both sides of the threshold. See METHODOLOGY.md.

Batteries: RAG (answers with sources) v4 (`df0f60dedfec`); Agents / tool calling v4 (`28178aaf6f13`); Chat & summaries in Portuguese v4 (`bcaa947ab167`).
