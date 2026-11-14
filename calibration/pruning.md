# Case pruning report

Discrimination check of METHODOLOGY.md 8.3, from the anchor runs only (never the local contestants). Target: 15 to 20 cases per use case, roughly one third per tier.

| Use case | Cases | easy / medium / hard | Anchor-checked | Too easy | Suspect | Ceilings disagree | Kept | Advice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent` | 17 | 2 / 3 / 12 | 17 | 2 | 0 | 0 | 15 | within the target |
| `chat_pt` | 19 | 3 / 6 / 10 | 19 | 3 | 0 | 0 | 16 | within the target |
| `coding` | 20 | 2 / 12 / 6 | 20 | 2 | 0 | 0 | 18 | within the target |
| `coding_public` | 10 | 5 / 4 / 1 | 10 | 7 | 0 | 0 | 3 | reference battery (public sets): fixed, not pruned |
| `rag` | 18 | 2 / 7 / 9 | 18 | 2 | 0 | 0 | 16 | within the target |

## Cases to act on

| Use case | Case | Tier | Ceilings (passed/executions) | Floor | Action |
| --- | --- | --- | --- | --- | --- |
| `agent` | `contact_schema` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `weather_call` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `explain_vpn` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `formal_rewrite` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `incident_summary` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `is_palindrome` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `word_count` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `answer_absent` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `single_passage` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |

Removed or rewritten cases go into [`cases/CHANGELOG.md`](../cases/CHANGELOG.md) with the reason.
