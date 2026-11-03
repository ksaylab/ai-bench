# Case pruning report

Discrimination check of METHODOLOGY.md 8.3, from the anchor runs only (never the local contestants). Target: 15 to 20 cases per use case, roughly one third per tier.

| Use case | Cases | easy / medium / hard | Anchor-checked | Too easy | Suspect | Ceilings disagree | Kept | Advice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent` | 7 | 4 / 3 / 0 | 7 | 7 | 0 | 0 | 0 | add 15 to 20 cases, mainly medium and hard |
| `chat_pt` | 6 | 2 / 4 / 0 | 6 | 4 | 0 | 0 | 2 | add 13 to 18 cases, mainly medium and hard |
| `coding` | 6 | 3 / 3 / 0 | 6 | 5 | 0 | 0 | 1 | add 14 to 19 cases, mainly medium and hard |
| `coding_public` | 10 | 5 / 4 / 1 | 10 | 5 | 0 | 0 | 5 | reference battery (public sets): fixed, not pruned |
| `rag` | 8 | 2 / 5 / 1 | 8 | 6 | 0 | 1 | 2 | add 13 to 18 cases, mainly medium and hard |

## Cases to act on

| Use case | Case | Tier | Ceilings (passed/executions) | Floor | Action |
| --- | --- | --- | --- | --- | --- |
| `agent` | `contact_schema` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `currency_call` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `no_tool_needed` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `orders_call` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `priority_schema` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `ticket_call` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `agent` | `weather_call` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `email_summary` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `explain_vpn` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `false_premise_pt` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `chat_pt` | `meeting_owners` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `fizzbuzz` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `is_palindrome` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `merge_intervals` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `top_k_frequent` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `coding` | `word_count` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `answer_absent` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 0/3 | mistralai/ministral-3b-2512 3/3 | ceilings_disagree: one ceiling passed every repeat and another failed every repeat |
| `rag` | `long_needle` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `newer_rule_wins` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `password_length` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `similar_entity` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `single_passage` | easy | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |
| `rag` | `two_facts` | medium | deepseek/deepseek-v4-pro 3/3; z-ai/glm-5.3-flash 3/3 | mistralai/ministral-3b-2512 3/3 | too_easy: every anchor, the floor included, passed every repeat |

Removed or rewritten cases go into [`cases/CHANGELOG.md`](../cases/CHANGELOG.md) with the reason.
