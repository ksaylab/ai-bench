"""Calibration anchors (METHODOLOGY.md 8.2): OpenRouter models that are the ruler for every battery.

- anchors.toml lists them, each with a role (`ceiling` or `floor`) and pinned sampling.
- `python3 -m aibench calibrate` runs the batteries on them into calibration/runs/.
- `python3 -m aibench calibration` merges the publishable anchor runs into calibration/anchors.csv and writes the
  case pruning report (calibration/pruning.csv and pruning.md, METHODOLOGY.md 8.3).
- reference() gives, per use case and battery version, the best ceiling score and the floor score, from which
  verdict.scores() derives:

    pct_of_ceiling = score / best ceiling score × 100
    normalized     = (score − floor score) / (best ceiling score − floor score) × 100   (0 = floor, 100 = ceiling)
"""
import csv
import json
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANCHORS_FILE = ROOT / "anchors.toml"
CALIBRATION = ROOT / "calibration"
ROLES = ("ceiling", "floor")
ANCHOR_COLUMNS = ["use_case", "battery", "model", "role", "passed", "executions", "runs", "score_pct", "min_run_pct",
                  "max_run_pct", "cost_usd"]


class CalibrationError(Exception):
    pass


def anchors(path=None):
    """[{name, role, sampling}] from anchors.toml."""
    path = Path(path or ANCHORS_FILE)
    if not path.exists():
        return []
    with open(path, "rb") as f:
        out = tomllib.load(f).get("anchor", [])
    for a in out:
        if a.get("role") not in ROLES:
            raise CalibrationError(f"anchor {a.get('name')!r}: role must be one of {', '.join(ROLES)}")
    return out


def anchor_names(path=None):
    return [a["name"] for a in anchors(path)]


def read_rows(root=None, log=None):
    """Execution rows of the publishable anchor runs, each with the anchor's role (from that run's meta.json)."""
    from aibench import run  # run imports verdict, which imports nothing from here: no cycle at import time
    rows = []
    for meta_path in sorted(Path(root or CALIBRATION).glob("runs/*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        why = run.excluded(meta, meta_path.parent, calibration=True)
        if why:
            if log:
                log(f"skipped {meta_path.parent.name}: {why}")
            continue
        roles = {m: info.get("role", "") for m, info in (meta.get("anchors") or {}).items()}
        with open(meta_path.parent / "executions.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if roles.get(r["model"]) in ROLES:
                    rows.append({**r, "role": roles[r["model"]]})
    return rows


def anchor_scores(rows):
    """One row per use case, battery version and anchor."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["use_case"], r.get("battery", ""), r["model"], r["role"])].append(r)
    out = []
    for (uc, battery, model, role), rs in sorted(groups.items()):
        per_run = defaultdict(list)
        for r in rs:
            per_run[(r["run_id"], str(r["rep"]))].append(int(r["passed"]))
        run_scores = [100 * sum(v) / len(v) for v in per_run.values()]
        passed = sum(int(r["passed"]) for r in rs)
        costs = [float(r["cost_usd"]) for r in rs if r.get("cost_usd") not in ("", None)]
        out.append({"use_case": uc, "battery": battery, "model": model, "role": role, "passed": passed,
                    "executions": len(rs), "runs": len(per_run), "score_pct": round(100 * passed / len(rs), 1),
                    "min_run_pct": round(min(run_scores), 1), "max_run_pct": round(max(run_scores), 1),
                    "cost_usd": round(sum(costs), 6) if costs else ""})
    return out


def reference(score_rows):
    """(use_case, battery) -> {"ceiling": best ceiling score, "ceiling_model", "floor": floor score}. A battery
    version only gets a reference when it has at least one ceiling and the floor."""
    by = defaultdict(dict)
    for s in score_rows:
        key = (s["use_case"], s["battery"])
        score = float(s["score_pct"])
        if s["role"] == "ceiling" and score >= by[key].get("ceiling", -1):
            by[key].update(ceiling=score, ceiling_model=s["model"])
        elif s["role"] == "floor":
            # more than one floor model: the weakest one is the floor
            by[key]["floor"] = min(score, by[key].get("floor", score))
    return {k: v for k, v in by.items() if "ceiling" in v and "floor" in v}


def load_reference(root=None):
    return reference(anchor_scores(read_rows(root)))


def consolidate(root=None, log=None, battery_cases=None):
    """Writes calibration/anchors.csv and the pruning report (pruning.csv, pruning.md); returns (path, number of
    executions, reference)."""
    from aibench import cases, run
    root = Path(root or CALIBRATION)
    rows = read_rows(root, log)
    scores = anchor_scores(rows)
    run.write_csv(root / "anchors.csv", ANCHOR_COLUMNS, scores)
    write_pruning(rows, cases.load() if battery_cases is None else battery_cases, root)
    return root / "anchors.csv", len(rows), reference(scores)


# ---------- discrimination check (case pruning, METHODOLOGY.md 8.3) ----------

TARGET_CASES = (15, 20)
PRUNING_COLUMNS = ["use_case", "battery", "case", "tier", "ceilings", "floor", "action", "reason"]
ACTIONS = {
    "too_easy": "remove or rewrite harder",
    "suspect": "review: wrong expected value, too strict checker or ambiguous prompt",
    "ceilings_disagree": "review: check that the prompt is unambiguous",
    "keep": "keep",
}


def case_results(rows):
    """(use_case, battery, case) -> {"tier", "anchors": {model: (role, passed, executions)}}."""
    out = {}
    for r in rows:
        key = (r["use_case"], r.get("battery", ""), r["case"])
        entry = out.setdefault(key, {"tier": r.get("tier", ""), "anchors": {}})
        role, passed, n = entry["anchors"].get(r["model"], (r["role"], 0, 0))
        entry["anchors"][r["model"]] = (role, passed + int(r["passed"]), n + 1)
    return out


def classify(anchors):
    """(action, reason) for one case from its anchors' results over all repeats. Only the anchors and the floor
    decide, never the local contestants."""
    ceilings = {m: (p, n) for m, (role, p, n) in anchors.items() if role == "ceiling"}
    floors = {m: (p, n) for m, (role, p, n) in anchors.items() if role == "floor"}
    if not ceilings or not floors:
        return "", "needs at least one ceiling and the floor"
    if all(p == n for p, n in list(ceilings.values()) + list(floors.values())):
        return "too_easy", "every anchor, the floor included, passed every repeat"
    if all(p == 0 for p, _ in ceilings.values()):
        return "suspect", "no ceiling anchor passed any repeat"
    rates = [p / n for p, n in ceilings.values()]
    if len(rates) > 1 and max(rates) == 1 and min(rates) == 0:
        return "ceilings_disagree", "one ceiling passed every repeat and another failed every repeat"
    return "keep", ""


def _fmt(results):
    return "; ".join(f"{m} {p}/{n}" for m, (p, n) in sorted(results.items()))


def pruning(rows, battery_cases=None):
    """(per-case rows, per-use-case summary). `battery_cases`: the current cases (cases.load()), so the summary also
    shows the batteries that have no anchor run yet."""
    per_case = []
    for (uc, battery, case), e in sorted(case_results(rows).items()):
        action, reason = classify(e["anchors"])
        per_case.append({"use_case": uc, "battery": battery, "case": case, "tier": e["tier"],
                         "ceilings": _fmt({m: (p, n) for m, (role, p, n) in e["anchors"].items() if role == "ceiling"}),
                         "floor": _fmt({m: (p, n) for m, (role, p, n) in e["anchors"].items() if role == "floor"}),
                         "action": action, "reason": reason or ACTIONS.get(action, "")})
    summary = {}
    for c in battery_cases or []:
        s = summary.setdefault(c["use_case"], {"cases": 0, "tiers": {}, "too_easy": 0, "suspect": 0,
                                                "ceilings_disagree": 0, "checked": 0})
        s["cases"] += 1
        s["tiers"][c["tier"]] = s["tiers"].get(c["tier"], 0) + 1
    current = {(c["use_case"], c["id"]) for c in battery_cases or []}
    for r in per_case:
        if battery_cases is not None and (r["use_case"], r["case"]) not in current:
            continue  # a case already removed from the battery
        s = summary.setdefault(r["use_case"], {"cases": 0, "tiers": {}, "too_easy": 0, "suspect": 0,
                                                "ceilings_disagree": 0, "checked": 0})
        s["checked"] += 1
        if r["action"] in ("too_easy", "suspect", "ceilings_disagree"):
            s[r["action"]] += 1
    for uc, s in summary.items():
        kept = s["cases"] - s["too_easy"] - s["suspect"]
        low, high = TARGET_CASES
        if kept < low:
            s["advice"] = f"add {low - kept} to {high - kept} cases, mainly medium and hard"
        elif kept > high:
            s["advice"] = f"{kept - high} more case(s) than the target: drop the least discriminating easy ones"
        else:
            s["advice"] = "within the target"
        s["kept"] = kept
    return per_case, summary


def pruning_markdown(per_case, summary, reference_note=""):
    low, high = TARGET_CASES
    lines = ["# Case pruning report", "",
             "Discrimination check of METHODOLOGY.md 8.3, from the anchor runs only (never the local contestants). "
             f"Target: {low} to {high} cases per use case, roughly one third per tier.", ""]
    if reference_note:
        lines += [reference_note, ""]
    lines += ["| Use case | Cases | easy / medium / hard | Anchor-checked | Too easy | Suspect | Ceilings disagree | "
              "Kept | Advice |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for uc, s in sorted(summary.items()):
        tiers = " / ".join(str(s["tiers"].get(t, 0)) for t in ("easy", "medium", "hard"))
        lines.append(f"| `{uc}` | {s['cases']} | {tiers} | {s['checked']} | {s['too_easy']} | {s['suspect']} | "
                     f"{s['ceilings_disagree']} | {s['kept']} | {s['advice']} |")
    flagged = [r for r in per_case if r["action"] not in ("keep", "")]
    lines += ["", "## Cases to act on", ""]
    if not flagged:
        lines.append("None (or no anchor run yet)." if not per_case else "None: every checked case discriminates.")
    else:
        lines += ["| Use case | Case | Tier | Ceilings (passed/executions) | Floor | Action |",
                  "| --- | --- | --- | --- | --- | --- |"]
        lines += [f"| `{r['use_case']}` | `{r['case']}` | {r['tier']} | {r['ceilings']} | {r['floor']} | "
                  f"{r['action']}: {r['reason']} |" for r in flagged]
    lines += ["", "Removed or rewritten cases go into [`cases/CHANGELOG.md`](../cases/CHANGELOG.md) with the reason."]
    return "\n".join(lines) + "\n"


def write_pruning(rows, battery_cases, root=None):
    from aibench import run
    root = Path(root or CALIBRATION)
    per_case, summary = pruning(rows, battery_cases)
    run.write_csv(root / "pruning.csv", PRUNING_COLUMNS, per_case)
    note = "" if rows else "No anchor run yet: only the battery sizes and tiers are shown."
    (root / "pruning.md").write_text(pruning_markdown(per_case, summary, note), encoding="utf-8")
    return root / "pruning.md", per_case, summary
