# Battery changelog

Every change to a battery, with the reason, so the pruning (METHODOLOGY.md 8.3) is public. Each change makes a new
battery version (`battery` in `meta.json`): runs of different versions are never merged or compared.

## 2026-11-03

- `coding`: from 6 to 20 cases (2 easy, 12 medium, 6 hard), after the first anchor run found 5 of the 6 too easy
  (the floor passed them on every repeat).
  - Removed as too easy: `fizzbuzz`, `merge_intervals`, `top_k_frequent`. Kept: `parse_duration` (it already
    separated models) and two easy cases, `is_palindrome` and `word_count`, so the `easy` tier still exists.
  - Added 17 cases of everyday code, with the traps written into the prompt and covered by the tests: parsing
    (`split_csv_line`, `parse_headers`, `parse_log_line`), money and numbers (`compact_number_br`,
    `allocate_cents`, `reached_threshold`, `parse_brl`), dates (`add_business_days`), ordering by a spec
    (`semver_compare`, `build_order`, `natural_sort`), text (`sort_names_br`, `wrap_text`), config and data
    (`set_ini_value`, `deep_merge`, `latest_by_key`) and networks (`ip_allowed`).
  - Screened before entering (METHODOLOGY.md 8.3): of 20 candidates, the floor passed `free_slots`,
    `last_business_day` and `slugify` on every repeat, so they were left out. It failed the other 17 on every
    repeat (`allocate_cents` on 2 of 3), and `z-ai/glm-5.3-flash` passed all 17 on most repeats. `parse_brl` was
    reworded before entering: it did not say whether ungrouped digits ('1234') are valid.
  - Tiers are the author's tagging, to be checked against the next anchor run.
- `rag/answer_absent`: no longer forbids citations. In the first anchor run `z-ai/glm-5.3-flash` answered right
  in every repeat ("It is not in the document") but cited passages to show what the document does cover, and
  failed. `ok` (the answer says the information is absent) and `forbidden` (no amount, no number of 3 or more
  digits) already fail an invented value, cited or not. `no_citations` had no other case and was removed.
- All batteries: every case gets a `tier` (`easy`, `medium`, `hard`), tagged by hand before any anchor run (best
  effort; to be revisited with the first pruning report). No case removed.
- New reference battery `coding_public` (`cases/coding_public/`): 5 HumanEval and 5 MBPP (sanitized) problems, with
  `source` and `license` on every case and the attribution in `cases/coding_public/NOTICE.md`. Not part of the
  verdict.
