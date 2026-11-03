# Battery changelog

Every change to a battery, with the reason, so the pruning (METHODOLOGY.md 8.3) is public. Each change makes a new
battery version (`battery` in `meta.json`): runs of different versions are never merged or compared.

## 2026-11-03

- `rag`: from 8 to 20 cases (2 easy, 8 medium, 10 hard), after the first anchor run found 6 of the 8 too easy.
  - Removed as too easy: `newer_rule_wins`, `similar_entity`, `two_facts`, `long_needle`. Kept: `long_two_hops` (it
    already separated models), `answer_absent`, and two easy cases, `single_passage` and `password_length`.
  - New fixed document `ops` in `rag_documents.json` (16 passages of internal policies: rules with exceptions,
    dates when a rule takes effect, limits that change, a chain of teams).
  - Added 16 cases where the answer has to be worked out from the passages, not copied: dates and deadlines
    (`credential_rotation_date`, `vpn_effective_date`, `sev2_after_midnight`, `vacation_one_day_short`), rules that
    changed (`meal_limit_by_date`, `meal_domestic_unchanged`, `purchase_quotes_after_change`, `purchase_cfo`,
    `purchase_exact_threshold`), joining passages (`payments_oncall_lead`, `long_renamed_room`,
    `long_three_hops`, `long_updates_out_of_order`), an explicit "no target" that is not "not in the document"
    (`sev3_no_target`), a half-answerable question (`partly_absent`) and a false premise
    (`false_premise_office_hours`).
  - Screened before entering (METHODOLOGY.md 8.3), in two rounds: of 24 candidates, the floor passed 8 on every
    repeat, which were left out; `z-ai/glm-5.3-flash` passed the other 16 on every repeat. The floor still passes
    some of them sometimes: `partly_absent` and `vacation_one_day_short` 2 of 3, `meal_limit_by_date` and
    `long_updates_out_of_order` 1 of 3.
  - During the screening `sev3_no_target` stopped accepting "not in the document" (wrong: the document says there
    is no target), and `long_renamed_room` only forbids 4402 as the Boreal room's code (the GLM named it as the
    other room's code and was failed).
  - Tiers are the author's tagging, to be checked against the next anchor run.
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
