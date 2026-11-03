"""Per-use-case scores and the "Good for / Not good for" verdict (METHODOLOGY.md, "Verdict").

score = passed executions / all executions of the use case's battery, over every run (in %).
- Good for: score >= GOOD_THRESHOLD
- Not good for: score < GOOD_THRESHOLD
- Inconclusive: fewer than MIN_RUNS runs, or more than MAX_ERROR_RATE of the executions failed for a
  technical reason (connection, server error), which says nothing about the model
- Unstable: the worst and the best run (repeat) fall on different sides of the threshold, so the verdict would
  change with the repeat that happened to be chosen. Shown like Inconclusive; never published as Good for / Not good for.
unstable_cases = cases whose result (pass/fail) changed between repeats.

Relative to the calibration anchors (aibench/calibration.py), when anchor runs exist for the same battery version:
- pct_of_ceiling = score / best ceiling anchor's score × 100
- normalized = (score − floor anchor's score) / (best ceiling score − floor score) × 100 (0 = floor, 100 = ceiling;
  not clamped: below the floor is negative, above the best ceiling is over 100)
- Not calibrated: the battery version's best ceiling scored below CALIBRATED_CEILING_MIN or the floor above
  CALIBRATED_FLOOR_MAX. No Good for / Not good for for anyone on that use case until the battery is fixed.
They are shown next to the score and never change Good for / Not good for.
borderline = the score is less than one case's worth (100 / cases in the battery) away from the threshold: mention it.
"""
from collections import defaultdict

GOOD_THRESHOLD = {"coding": 80.0, "rag": 80.0, "agent": 80.0, "chat_pt": 80.0}
MIN_RUNS = 3
MAX_ERROR_RATE = 0.10
CALIBRATED_CEILING_MIN = 90.0
CALIBRATED_FLOOR_MAX = 40.0
LABELS = {"coding": "Coding", "rag": "RAG (answers with sources)", "agent": "Agents / tool calling",
          "chat_pt": "Chat & summaries in Portuguese"}
SCORE_COLUMNS = ["machine", "model", "use_case", "battery", "passed", "executions", "cases", "runs", "score_pct",
                 "min_run_pct", "max_run_pct", "unstable_cases", "errors", "threshold_pct", "verdict", "borderline",
                 "ceiling_pct", "floor_pct", "pct_of_ceiling", "normalized", "calibrated", "avg_time_s", "avg_tok_s",
                 "cost_usd"]
VERDICT_COLUMNS = ["machine", "model"] + [f"{uc}_pct" for uc in GOOD_THRESHOLD] + [
    "good_for", "not_good_for", "inconclusive", "unstable", "not_calibrated", "runs", "avg_time_s", "cost_usd"]
UNSURE = ("Inconclusive", "Not calibrated", "Unstable")


def _order(uc):
    return list(GOOD_THRESHOLD).index(uc) if uc in GOOD_THRESHOLD else len(GOOD_THRESHOLD)


def _f(x):
    return float(x) if x not in ("", None) else None


def relative(score, ref):
    """(ceiling_pct, floor_pct, pct_of_ceiling, normalized, calibrated) against an anchor reference (or empty)."""
    if not ref:
        return "", "", "", "", ""
    ceiling, floor = ref["ceiling"], ref["floor"]
    pct = round(100 * score / ceiling, 1) if ceiling > 0 else ""
    norm = round(100 * (score - floor) / (ceiling - floor), 1) if ceiling != floor else ""
    calibrated = int(ceiling >= CALIBRATED_CEILING_MIN and floor <= CALIBRATED_FLOOR_MAX)
    return ceiling, floor, pct, norm, calibrated


def scores(rows, reference=None):
    """One row per machine, model and use case from execution rows (dicts with the run.COLUMNS keys).
    `reference`: (use_case, battery) -> {"ceiling", "floor"} from calibration.reference(), for the relative columns."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["machine"], r["model"], r["use_case"])].append(r)
    out = []
    for (machine, model, uc), rs in sorted(groups.items()):
        per_run, per_case = defaultdict(list), defaultdict(set)
        for r in rs:
            per_run[(r["run_id"], str(r["rep"]))].append(int(r["passed"]))
            per_case[r["case"]].add(int(r["passed"]))
        n, passed = len(rs), sum(int(r["passed"]) for r in rs)
        errors = sum(str(r["reason"]).startswith("error:") for r in rs)
        cases = len({r["case"] for r in rs})
        score = round(100 * passed / n, 1)
        run_scores = [100 * sum(v) / len(v) for v in per_run.values()]
        threshold = GOOD_THRESHOLD.get(uc, 80.0)
        battery = next((r.get("battery") for r in rs if r.get("battery")), "")
        ceiling, floor, pct, norm, calibrated = relative(score, (reference or {}).get((uc, battery)))
        if len(per_run) < MIN_RUNS or errors / n > MAX_ERROR_RATE:
            verdict = "Inconclusive"
        elif calibrated == 0:
            verdict = "Not calibrated"
        elif min(run_scores) < threshold <= max(run_scores):
            verdict = "Unstable"
        else:
            verdict = "Good for" if score >= threshold else "Not good for"
        times = [t for t in (_f(r["time_s"]) for r in rs) if t is not None]
        tps = [t for t in (_f(r["tok_s"]) for r in rs) if t is not None]
        costs = [c for c in (_f(r["cost_usd"]) for r in rs) if c is not None]
        costs += [c for c in (_f(r.get("judge_cost_usd")) for r in rs) if c is not None]
        out.append({"machine": machine, "model": model, "use_case": uc, "battery": battery, "passed": passed,
                    "executions": n,
                    "cases": cases, "runs": len(per_run), "score_pct": score,
                    "min_run_pct": round(min(run_scores), 1), "max_run_pct": round(max(run_scores), 1),
                    "unstable_cases": sum(len(v) > 1 for v in per_case.values()),
                    "errors": errors, "threshold_pct": threshold, "verdict": verdict,
                    "borderline": int(abs(score - threshold) < 100 / max(cases, 1)),
                    "ceiling_pct": ceiling, "floor_pct": floor, "pct_of_ceiling": pct, "normalized": norm,
                    "calibrated": calibrated,
                    "avg_time_s": round(sum(times) / len(times), 2) if times else "",
                    "avg_tok_s": round(sum(tps) / len(tps), 2) if tps else "",
                    "cost_usd": round(sum(costs), 6) if costs else ""})
    return out


def verdicts(score_rows):
    """One row per machine and model: the score of each use case and the Good for / Not good for lists."""
    groups = defaultdict(list)
    for s in score_rows:
        groups[(s["machine"], s["model"])].append(s)
    out = []
    for (machine, model), ss in sorted(groups.items()):
        by = {s["use_case"]: s for s in ss}
        row = {"machine": machine, "model": model}
        for uc in GOOD_THRESHOLD:
            row[f"{uc}_pct"] = by[uc]["score_pct"] if uc in by else ""
        for key, label in (("good_for", "Good for"), ("not_good_for", "Not good for"),
                           ("inconclusive", "Inconclusive"), ("unstable", "Unstable"),
                           ("not_calibrated", "Not calibrated")):
            row[key] = "; ".join(LABELS.get(uc, uc) + (" (borderline)" if s["borderline"] else "")
                                 for uc, s in sorted(by.items(), key=lambda kv: _order(kv[0]))
                                 if s["verdict"] == label)
        times = [s["avg_time_s"] for s in ss if s["avg_time_s"] != ""]
        costs = [s["cost_usd"] for s in ss if s["cost_usd"] != ""]
        row["runs"] = min(s["runs"] for s in ss)
        row["avg_time_s"] = round(sum(times) / len(times), 2) if times else ""
        row["cost_usd"] = round(sum(costs), 6) if costs else ""
        out.append(row)
    return out


def markdown(verdict_rows):
    """The table the video shows."""
    any_unsure = any(r.get("inconclusive") for r in verdict_rows)
    any_unstable = any(r.get("unstable") for r in verdict_rows)
    any_uncal = any(r.get("not_calibrated") for r in verdict_rows)
    head = ["Model", "Machine"] + [LABELS[uc] for uc in GOOD_THRESHOLD] + ["Good for", "Not good for"] + (
        ["Inconclusive ⚠️"] if any_unsure else []) + (["Unstable ⚠️"] if any_unstable else []) + (
        ["Not calibrated ⚠️"] if any_uncal else [])
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * len(head)) + " |"]
    for r in verdict_rows:
        cells = [f"`{r['model']}`", r["machine"]]
        for uc in GOOD_THRESHOLD:
            v = r[f"{uc}_pct"]
            unsure = any(LABELS[uc] in r.get(k, "") for k in ("inconclusive", "unstable", "not_calibrated"))
            mark = "⚠️" if unsure else ("✅" if v != "" and v >= GOOD_THRESHOLD[uc] else "❌")
            cells.append("—" if v == "" else f"{v:.0f}% {mark}")
        cells += [r["good_for"] or "—", r["not_good_for"] or "—"]
        if any_unsure:
            cells.append(r["inconclusive"] or "—")
        if any_unstable:
            cells.append(r["unstable"] or "—")
        if any_uncal:
            cells.append(r["not_calibrated"] or "—")
        lines.append("| " + " | ".join(cells) + " |")
    rules = ", ".join(f"{LABELS[uc]} ≥ {t:.0f}%" for uc, t in GOOD_THRESHOLD.items())
    return ("\n".join(lines) + f"\n\nGood for: {rules}, over at least {MIN_RUNS} runs. Unstable: the repeats fall on "
            "both sides of the threshold. See METHODOLOGY.md.\n")
