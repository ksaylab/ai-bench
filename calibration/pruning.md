# Case pruning report

Discrimination check of METHODOLOGY.md 8.3, from the anchor runs only (never the local contestants). Target: 15 to 20 cases per use case, roughly one third per tier.

| Use case | Cases | easy / medium / hard | Anchor-checked | Too easy | Suspect | Ceilings disagree | Kept | Advice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent` | 20 | 2 / 3 / 15 | 20 | 3 | 0 | 0 | 17 | within the target |
| `chat_pt` | 22 | 3 / 7 / 12 | 22 | 2 | 0 | 0 | 20 | within the target |
| `coding` | 20 | 2 / 12 / 6 | 20 | 2 | 0 | 0 | 18 | within the target |
| `coding_public` | 10 | 5 / 4 / 1 | 10 | 7 | 0 | 0 | 3 | reference battery (public sets): fixed, not pruned |
| `rag` | 19 | 2 / 7 / 10 | 19 | 3 | 0 | 0 | 16 | within the target |

## Cases to act on

| Use case | Case | Tier | Ceilings (passed/executions) | Floor | Action |
| --- | --- | --- | --- | --- | --- |
| `agent` | `contact_schema` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `refund_some_items` | hard | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `weather_call` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `explain_vpn` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `weekday_new_year_2027` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `is_palindrome` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `word_count` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `answer_absent` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `long_two_hops` | hard | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `single_passage` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |

Removed or rewritten cases go into [`cases/CHANGELOG.md`](../cases/CHANGELOG.md) with the reason.
