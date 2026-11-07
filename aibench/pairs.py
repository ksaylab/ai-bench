"""Episode 03 (is a bigger model better?): the comparison table per pair of models on the same hardware.

A pair is two models of the episode's models.toml with the same `pair` (a model may list several: `pair = ["a",
"b"]`), one in group "small" and one in group "large". For each verdict battery, `table` sets the two sides' scores
and verdicts side by side (from results/scores.csv) with the outcome (does the large model earn a Good for the small
one does not?), the minutes per battery run and the energy per battery run (Wh). `speeds` adds llama-bench's
generation speed at depth 0 (results/speed.csv). `write` saves results/pairs.csv and pairs.md; `verdict` calls it.
"""
import csv
import tomllib

from aibench import run, verdict

COLUMNS = ["pair", "machine", "use_case", "small", "large", "small_pct", "large_pct", "points", "small_verdict",
           "large_verdict", "outcome", "small_minutes", "large_minutes", "time_ratio", "small_wh", "large_wh"]
GOOD, NOT_GOOD = "Good for", "Not good for"
NOT_RUN = "not run yet"


def _pairs(episode):
    """{pair: {"small": entry, "large": entry, "machine": ...}} in models.toml order."""
    path = run.EPISODES / episode / "models.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        models = tomllib.load(f).get("model", [])
    found = {}
    for m in models:
        names = m.get("pair") or []
        for p in [names] if isinstance(names, str) else names:
            found.setdefault(p, []).append(m)
    out = {}
    for p, ms in found.items():
        sides = {g: [m for m in ms if m.get("group") == g] for g in ("small", "large")}
        if len(ms) != 2 or len(sides["small"]) != 1 or len(sides["large"]) != 1:
            raise ValueError(f"pair {p} needs one model in group small and one in group large, not "
                             f"{', '.join(m['name'] + ' (' + str(m.get('group')) + ')' for m in ms)}")
        small, large = sides["small"][0], sides["large"][0]
        machines = [x for x in small.get("machines", []) if x in large.get("machines", [])]
        if not machines:
            raise ValueError(f"pair {p}: {small['name']} and {large['name']} share no machine")
        out[p] = {"small": small, "large": large, "machine": machines[0]}
    return out


def _contestant(entry):
    t = entry.get("thinking")
    return run.contestant(entry["name"], None if t is None else run.thinking_level(t))


def _read(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(x):
    return float(x) if x not in ("", None) else None


def _outcome(s, l):
    if s is None or l is None:
        return NOT_RUN
    for v in (s["verdict"], l["verdict"]):
        if v not in (GOOD, NOT_GOOD):
            return f"unsure ({v})"
    return {(True, True): "both Good for", (False, True): "only the large is Good for",
            (True, False): "only the small is Good for", (False, False): "neither Good for"}[
        (s["verdict"] == GOOD, l["verdict"] == GOOD)]


def table(episode):
    scores = {(r["machine"], r["model"], r["use_case"]): r
              for r in _read(run.EPISODES / episode / "results" / "scores.csv")}
    minutes = lambda r: round(_num(r["avg_time_s"]) * int(r["cases"]) / 60, 2) \
        if r and _num(r["avg_time_s"]) is not None else ""  # noqa: E731
    out = []
    for p, x in _pairs(episode).items():
        small, large = _contestant(x["small"]), _contestant(x["large"])
        for uc in verdict.GOOD_THRESHOLD:
            s, l = scores.get((x["machine"], small, uc)), scores.get((x["machine"], large, uc))
            sm, lm = minutes(s), minutes(l)
            out.append({
                "pair": p, "machine": x["machine"], "use_case": uc, "small": small, "large": large,
                "small_pct": _num(s["score_pct"]) if s else "", "large_pct": _num(l["score_pct"]) if l else "",
                "points": round(_num(l["score_pct"]) - _num(s["score_pct"]), 1) if s and l else "",
                "small_verdict": s["verdict"] if s else "", "large_verdict": l["verdict"] if l else "",
                "outcome": _outcome(s, l), "small_minutes": sm, "large_minutes": lm,
                "time_ratio": round(lm / sm, 1) if sm and lm else "",
                "small_wh": _num(s["wh_per_run"]) if s and s["wh_per_run"] else "",
                "large_wh": _num(l["wh_per_run"]) if l and l["wh_per_run"] else ""})
    return out


def speeds(episode):
    """{(machine, model): {"tg": tok/s at depth 0, "no_fit": True when it does not fit with every layer on the
    GPU}} from results/speed.csv (model names without the thinking level: llama-bench has none)."""
    out = {}
    for r in _read(run.EPISODES / episode / "results" / "speed.csv"):
        d = out.setdefault((r["machine"], r["model"]), {"tg": None, "no_fit": False})
        if r["status"] == "error" and "did not fit" in r["reason"]:
            d["no_fit"] = True
        elif r["status"] == "ok" and r["metric"] == "tg" and str(r["depth"]) == "0":
            d["tg"] = _num(r["tok_s"])
    return out


def _mark(pct, v):
    if pct == "":
        return "—"
    return f"{pct:.0f}% " + ("✅" if v == GOOD else "❌" if v == NOT_GOOD else "⚠️")


def markdown(rows, speed_rows=None):
    speed_rows = speed_rows or {}
    lines = ["# Is a bigger model better?", "",
             "Per pair, on the same machine: each battery's score and verdict for the small and the large model, the "
             "outcome, and the minutes per battery run. Source: `pairs.csv` (from `scores.csv`) and `speed.csv`.", ""]
    for p in dict.fromkeys(r["pair"] for r in rows):
        rs = [r for r in rows if r["pair"] == p]
        small, large, machine = rs[0]["small"], rs[0]["large"], rs[0]["machine"]
        lines += [f"## {p}: `{small}` vs `{large}` ({machine})", ""]
        if all(r["outcome"] == NOT_RUN for r in rs):
            lines += ["Not run yet.", ""]
            continue
        lines += ["| Battery | Small | Large | Points | Outcome | Time per battery run |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for r in rs:
            pts = "—" if r["points"] == "" else f"{r['points']:+.0f}"
            t = "—" if r["time_ratio"] == "" else \
                f"{r['small_minutes']:.1f} → {r['large_minutes']:.1f} min ({r['time_ratio']:.1f}×)"
            lines.append(f"| {verdict.LABELS[r['use_case']]} | {_mark(r['small_pct'], r['small_verdict'])} | "
                         f"{_mark(r['large_pct'], r['large_verdict'])} | {pts} | {r['outcome']} | {t} |")
        lines.append("")
        only = [verdict.LABELS[r["use_case"]] for r in rs if r["outcome"] == "only the large is Good for"]
        lines.append("Good for only with the large model: " + (", ".join(only) if only else "none") + ".")
        both = [r for r in rs if r["small_wh"] != "" and r["large_wh"] != ""]
        if both:
            lines.append(f"Energy for these batteries, one run each: {sum(r['small_wh'] for r in both):.1f} → "
                         f"{sum(r['large_wh'] for r in both):.1f} Wh.")
        base = lambda name: name.partition("@think-")[0]  # noqa: E731
        ss, ls = speed_rows.get((machine, base(small))), speed_rows.get((machine, base(large)))
        if ss and ls and ss["tg"] and ls["tg"]:
            lines.append(f"Generation speed (llama-bench, depth 0): {ss['tg']:.1f} → {ls['tg']:.1f} tok/s "
                         f"({ss['tg'] / ls['tg']:.1f}× slower).")
        for name, s in ((base(small), ss), (base(large), ls)):
            if s and s["no_fit"]:
                lines.append(f"`{name}` does not fit on the GPU: it runs with part of the model on the CPU.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write(episode):
    """results/pairs.csv and pairs.md when the episode has pairs; [] otherwise."""
    if not _pairs(episode):
        return []
    rows = table(episode)
    results = run.EPISODES / episode / "results"
    path = results / "pairs.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    md = results / "pairs.md"
    md.write_text(markdown(rows, speeds(episode)), encoding="utf-8")
    return [path, md]
