# Battery changelog

Every change to a battery, with the reason, so the pruning (METHODOLOGY.md 8.3) is public. Each change makes a new
battery version (`battery` in `meta.json`): runs of different versions are never merged or compared.

## 2026-11-04

- After the anchor run of the grown batteries (`calibration/runs/2026-11-04-0754-openrouter-anchors`, 720 calls,
  US$2.00), its answers were reviewed and the batteries fixed where the checker or the tagging was wrong. No prompt,
  history or tool changed, so the saved answers were rescored (`python3 -m aibench rescore`) instead of rerun: the
  rescored run (`...-rescored-20261104-1315`) is the baseline (v2). Only 3 verdicts changed, all of
  `z-ai/glm-5.3-flash` (235/240 to 238/240); the floor passed nothing new.
  - Checker version 3: an initial or a title (`D. Pedro`, `Dr. Silva`) does not end a sentence.
    `false_premise_holiday` failed the same model twice at "4 sentences" for three, cut at `D. Pedro I`. Known
    limit: a sentence that really ends in a one-letter capital (`plan B.`) is joined to the next one.
  - `rag` `sev3_no_target`: the forbidden `within (15|60) minutes` also caught a correct comparison ("severity 1
    incidents must be acknowledged within 15 minutes ... this does not apply to severity 3"). It now forbids only an
    answer that starts with a time or gives severity 3 one.
  - Tiers from the data: the floor passed every repeat of `chat_pt` `translate_keep_code` and `incident_summary`
    (medium), `rag` `answer_absent` (medium) and `vacation_one_day_short` (hard), now easy. Every case the pruning
    calls too easy is now in the easy tier, which is meant to be passed by small models (8.3).
  - Reviewed and kept: `rag` `vpn_effective_date` (`ceilings_disagree`). `deepseek/deepseek-v4-pro` gets the date
    right but also cites [7], the office hours passage, for "closed on weekends", and fails every repeat on
    `cite_only`; `z-ai/glm-5.3-flash` cites only [1]. Citing a passage that is not about the VPN policy counts as a
    failure; the floor fails on the date itself.
  - Also seen, no change: `coding` `parse_brl` was cut at 32768 tokens once out of 3 for `deepseek/deepseek-v4-pro`
    (it passed the other two); `chat_pt` `incident_summary` failed `z-ai/glm-5.3-flash` twice over 60 words, with a
    title (titles count as words).
- Checker version 2 (`cases.CHECKER_VERSION`), a new version of every battery: the checker version is now part of
  the battery version, so runs checked by different rules are never merged (before, only the case files were, and
  the rag checker change of 2026-11-03 kept the version).
  - `words`: a number with `:`, `/`, `.` or `,` inside (`14:02`, `100/100`, `1.234,56`) is one word, as a reader
    counts it. `incident_summary` failed `z-ai/glm-5.3-flash` at 61 words, 57 counted that way.
  - `sentences`: a markdown heading line (`# What is a VPN?`) is a title, not a sentence; it still counts as
    words. `explain_vpn` failed the same model at "4 sentences" for three sentences under a heading.
  - Found by screening every case on `z-ai/glm-5.3-flash` at effort `high` (1 repeat): of its 6 failures, these 2
    were the checker; the other 4 (`compact_number_br`, `parse_brl`, `sort_names_br`, `list_without_words`) were the
    model's own mistakes, and at effort `max` it passed all 6. No other verdict of the examples or of those answers
    changed.

## 2026-11-03

- `coding`: `parse_log_line` now says that the level may be in any case in the line. The prompt said "level is
  uppercase without brackets", which describes the output but reads as the input; the tests send `[warning]` and
  `[error]`. In the first run of this battery version, `deepseek/deepseek-v4-pro` matched the level with `[A-Z]+`
  and failed for that reason only (it weighed lowercase input in its reasoning and ruled it out from the prompt).
  That run was stopped after 7 calls and is not kept.
- `agent`: from 7 to 15 cases (4 easy, 2 medium, 9 hard), after the first anchor run found all 7 too easy (the
  floor passed every one on every repeat).
  - Two new checker features (`aibench/cases.py`): kind `tool_calls` (several calls in one answer, in any order)
    and `history` (earlier calls and their results sent before the answer, so a case checks the agent's next step).
  - Five new tools in `agent_tools.json`, close to the old ones on purpose: `get_order`, `update_ticket`,
    `refund_order`, `schedule_meeting`, `list_tickets`; `search_orders` now says what a customer id looks like.
  - Removed as too easy: `ticket_call`, `currency_call`, `orders_call`. Kept as easy cases: `weather_call`,
    `no_tool_needed`, and the two JSON output cases `contact_schema` and `priority_schema` (moved from medium to
    easy), so structured output is still tested.
  - Added 11 cases where the floor fails because it has to reason over the data, not because of the tool or its
    arguments: relative dates (`meeting_relative_date`, `meeting_next_week_tuesday`), picking, filtering or adding
    up a tool result (`ticket_for_oldest_order`, `refund_late_orders`, `close_old_resolved`, `refund_some_items`,
    `priority_from_sum`), acting on a result (`act_on_result_threshold`), stopping at a limit
    (`refund_above_total`), looking up before acting (`look_up_before_refund`) and asking for a missing id
    (`ask_for_customer_id`).
  - Screened before entering (METHODOLOGY.md 8.3), in three rounds: of 33 candidates, the floor passed 22 on
    every repeat, which were left out (it chooses tools and builds arguments well); `z-ai/glm-5.3-flash` passed
    the other 11 on every repeat. `ask_for_customer_id` first failed both anchors, because `search_orders` did not
    say that a customer id is not a name; the tool now says it.
  - Tiers are the author's tagging, to be checked against the next anchor run.
- `chat_pt`: from 6 to 15 cases (3 easy, 8 medium, 4 hard), after the first anchor run found 4 of the 6 too easy.
  - Removed as too easy: `false_premise_pt` (three new false premises replace it) and `meeting_owners`. Kept:
    `incident_summary` and `formal_rewrite` (they already separated models), and `explain_vpn` and
    `email_summary` as easy cases (`email_summary` moves from medium to easy: the floor passes it).
  - Added 11 cases of everyday Portuguese: false premises (`false_premise_states`, `false_premise_holiday`,
    `false_premise_capital`), grammar (`grammar_fix`), dates (`dates_in_order`, `relative_deadlines_order`,
    `weekday_of_date`) and following the instruction exactly (`yes_no_only`, `exact_word_count`,
    `list_without_words`, `translate_keep_code`).
  - Screened before entering (METHODOLOGY.md 8.3), in two rounds: of 22 candidates, the floor passed 11 on every
    repeat, which were left out; `z-ai/glm-5.3-flash` passed the other 11, `list_without_words` only at effort
    `max` (at `high` it left its draft and its self-correction in the answer). The floor still passes
    `list_without_words` and `translate_keep_code` 2 of 3 times.
  - During the screening four patterns were fixed because they failed right answers: `reassigned_task_owners`
    ("Treinar" for "treinamento") and `no_jargon_explanation` (it required repeating the 40 minutes), both then
    left out because the floor passed them; `weekday_of_date` (the GLM named another year's weekday while
    explaining); and the Portuguese check on one-line answers (`exact_word_count`, `weekday_of_date`), where the
    pattern already requires Portuguese words.
  - Tiers are the author's tagging, to be checked against the next anchor run.
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
