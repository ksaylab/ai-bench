"""Calibration anchors (METHODOLOGY.md 8.2): OpenRouter models that are the ruler for every battery.

- anchors.toml lists them, each with a role (`ceiling` or `floor`) and pinned sampling.
- `python3 -m aibench calibrate` runs the batteries on them into calibration/runs/.
- `python3 -m aibench calibration` merges the publishable anchor runs into calibration/anchors.csv.
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


def consolidate(root=None, log=None):
    """Writes calibration/anchors.csv; returns (path, number of executions, reference)."""
    from aibench import run
    root = Path(root or CALIBRATION)
    rows = read_rows(root, log)
    scores = anchor_scores(rows)
    run.write_csv(root / "anchors.csv", ANCHOR_COLUMNS, scores)
    return root / "anchors.csv", len(rows), reference(scores)
