# Case pruning report

Discrimination check of METHODOLOGY.md 8.3, from the anchor runs only (never the local contestants). Target: 15 to 20 cases per use case, roughly one third per tier.

| Use case | Cases | easy / medium / hard | Anchor-checked | Too easy | Suspect | Ceilings disagree | Kept | Advice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent` | 15 | 4 / 2 / 9 | 15 | 4 | 0 | 0 | 11 | add 4 to 9 cases, mainly medium and hard |
| `chat_pt` | 15 | 5 / 6 / 4 | 15 | 4 | 0 | 0 | 11 | add 4 to 9 cases, mainly medium and hard |
| `coding` | 20 | 2 / 12 / 6 | 20 | 2 | 0 | 0 | 18 | within the target |
| `coding_public` | 10 | 5 / 4 / 1 | 10 | 7 | 0 | 0 | 3 | reference battery (public sets): fixed, not pruned |
| `rag` | 20 | 4 / 7 / 9 | 20 | 4 | 0 | 1 | 16 | within the target |

## Cases to act on

| Use case | Case | Tier | Ceilings (passed/executions) | Floor | Action |
| --- | --- | --- | --- | --- | --- |
| `agent` | `contact_schema` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `no_tool_needed` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `priority_schema` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `weather_call` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `email_summary` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `explain_vpn` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `formal_rewrite` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `translate_keep_code` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `is_palindrome` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `word_count` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `answer_absent` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `password_length` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `single_passage` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `vacation_one_day_short` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `vpn_effective_date` | medium | deepseek/deepseek-v4-pro 0/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 0/3 | ceilings_disagree: one ceiling passed every repeat and another failed every repeat |

Removed or rewritten cases go into [`cases/CHANGELOG.md`](../cases/CHANGELOG.md) with the reason.
