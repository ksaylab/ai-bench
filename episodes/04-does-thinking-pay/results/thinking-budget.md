# Thinking budget per task

Rule: for each model and battery, the lowest thinking level (off < 512 < 2048 < 8192 tokens) whose score is within 2 points of that model's best level on that battery. Each cell: level · score · minutes per battery run. Source: `thinking-budget.csv` (and `thinking.csv` for every level).

| Model | All four batteries | Coding | RAG (answers with sources) | Agents / tool calling | Chat & summaries in Portuguese |
| --- | --- | --- | --- | --- | --- |
| `lfm3-1.7b` | 8192 · 82.4% · 26 min | 8192 · 58.3% · 19 min | 512 · 91.7% · 1.7 min | 512 · 100.0% · 0.4 min | 2048 · 84.4% · 2.0 min |
| `neohorse-4b` | 8192 · 81.9% · 46 min | 8192 · 70.0% · 27 min | off · 91.7% · 1.0 min | off · 88.9% · 0.4 min | 2048 · 84.4% · 5.2 min |
| `gemma4-e4b` | 512 · 72.9% · 6.1 min | 8192 · 56.7% · 5.5 min | 512 · 76.7% · 1.5 min | 2048 · 95.6% · 0.7 min | off · 80.0% · 0.1 min |
| `ornith1.5-9b` | 2048 · 82.9% · 15 min | 8192 · 71.7% · 26 min | 512 · 88.3% · 1.6 min | 512 · 97.8% · 0.8 min | 512 · 82.2% · 1.3 min |
| `qwen3.6-35b-a3b` | 2048 · 86.7% · 51 min | off · 76.7% · 5.2 min | 512 · 91.7% · 6.3 min | 512 · 86.7% · 2.6 min | 2048 · 97.8% · 9.0 min |
| `gemma4-26b` | 2048 · 93.8% · 42 min | 2048 · 86.7% · 24 min | 512 · 91.7% · 5.8 min | 512 · 100.0% · 2.3 min | 2048 · 100.0% · 6.2 min |
