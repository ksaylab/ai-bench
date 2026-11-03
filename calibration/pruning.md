# Case pruning report

Discrimination check of METHODOLOGY.md 8.3, from the anchor runs only (never the local contestants). Target: 15 to 20 cases per use case, roughly one third per tier.

No anchor run yet: only the battery sizes and tiers are shown.

| Use case | Cases | easy / medium / hard | Anchor-checked | Too easy | Suspect | Ceilings disagree | Kept | Advice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent` | 7 | 4 / 3 / 0 | 0 | 0 | 0 | 0 | 7 | add 8 to 13 cases, mainly medium and hard |
| `chat_pt` | 6 | 2 / 4 / 0 | 0 | 0 | 0 | 0 | 6 | add 9 to 14 cases, mainly medium and hard |
| `coding` | 6 | 3 / 3 / 0 | 0 | 0 | 0 | 0 | 6 | add 9 to 14 cases, mainly medium and hard |
| `coding_public` | 10 | 5 / 4 / 1 | 0 | 0 | 0 | 0 | 10 | reference battery (public sets): fixed, not pruned |
| `rag` | 8 | 2 / 5 / 1 | 0 | 0 | 0 | 0 | 8 | add 7 to 12 cases, mainly medium and hard |

## Cases to act on

None (or no anchor run yet).

Removed or rewritten cases go into [`cases/CHANGELOG.md`](../cases/CHANGELOG.md) with the reason.
