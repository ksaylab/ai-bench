"""Episode 04 (does thinking pay?): score x time per model, thinking level and battery.

`table` reads the episode's merged results/executions.csv (what `verdict` writes from the publishable runs) and
returns one row per model, level and battery, plus `all`: the verdict batteries pooled (coding_public is reference
only and left out, as in the verdicts). `write` saves them to results/thinking.csv and draws one chart per battery
in results/charts/thinking-<battery>.svg: score (y) against minutes per battery run (x, log scale), one line per
model through its levels. Every number in the charts is a row of thinking.csv. `budget` picks the thinking budget
per model and battery (the lowest level within 2 points of that model's best), saved to thinking-budget.csv and,
as the table for the video, thinking-budget.md.
"""
import csv
import math
from collections import defaultdict
from fractions import Fraction
from html import escape

from aibench import run, verdict

LEVELS = ["off", "512", "2048", "8192", "unlimited"]
COLUMNS = ["model", "level", "use_case", "cases", "runs", "executions", "passed", "score_pct", "min_run_pct",
           "max_run_pct", "minutes_per_run", "length_cuts", "points_vs_off", "time_vs_off"]
ALL = "all"
BUDGET_MARGIN = 2.0  # points: rule A of the budget table (chosen 2026-11-06)
BUDGET_COLUMNS = ["model", "use_case", "level", "score_pct", "minutes_per_run", "best_level", "best_score_pct",
                  "best_minutes_per_run", "points_below_best", "time_vs_best"]

# Categorical slots in fixed order (dataviz reference palette, light and dark steps; validated for six series on the
# adjacent pairlist). Three light steps are under 3:1 on the surface: every line carries a direct label.
LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"]


def _split(name):
    """("model", "level") for a thinking contestant (model@think-<level>), else None."""
    model, sep, level = name.partition("@think-")
    return (model, level) if sep and level in LEVELS else None


def _pct(passed, n):
    return round(100 * passed / n, 1) if n else 0.0


def table(episode):
    path = run.EPISODES / episode / "results" / "executions.csv"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    groups = defaultdict(list)
    order = []
    for r in rows:
        key = _split(r["model"])
        if not key or r["use_case"] in verdict.REFERENCE:
            continue
        if key[0] not in order:
            order.append(key[0])
        groups[(*key, r["use_case"])].append(r)
        groups[(*key, ALL)].append(r)
    out = []
    for (model, level, uc), rs in groups.items():
        reps = sorted({int(r["rep"]) for r in rs})
        per_rep = [[r for r in rs if int(r["rep"]) == rep] for rep in reps]
        passed = sum(int(r["passed"]) for r in rs)
        out.append({
            "model": model, "level": level, "use_case": uc,
            "cases": len({(r["use_case"], r["case"]) for r in rs}), "runs": len(reps), "executions": len(rs),
            "passed": passed, "score_pct": _pct(passed, len(rs)),
            "min_run_pct": min(_pct(sum(int(r["passed"]) for r in x), len(x)) for x in per_rep),
            "max_run_pct": max(_pct(sum(int(r["passed"]) for r in x), len(x)) for x in per_rep),
            "minutes": sum(float(r["time_s"] or 0) for r in rs) / len(reps) / 60,
            "length_cuts": sum(r["finish"] == "length" for r in rs)})
    off = {(r["model"], r["use_case"]): r for r in out if r["level"] == "off"}
    for r in out:
        base = off.get((r["model"], r["use_case"]))
        r["points_vs_off"] = round(r["score_pct"] - base["score_pct"], 1) if base else ""
        r["time_vs_off"] = round(r["minutes"] / base["minutes"], 1) if base and base["minutes"] else ""
    for r in out:  # rounded only once every ratio is taken
        r["minutes_per_run"] = round(r.pop("minutes"), 2)
    ucs = [ALL] + [u for u in verdict.LABELS if u not in verdict.REFERENCE]
    return sorted(out, key=lambda r: (ucs.index(r["use_case"]) if r["use_case"] in ucs else len(ucs),
                                      order.index(r["model"]), LEVELS.index(r["level"])))


def budget(rows, margin=BUDGET_MARGIN):
    """The thinking budget per model and battery (rule A): the lowest level whose score is within `margin` points
    of that model's best level on that battery (inclusive). A tie for best goes to the lowest level. Scores are
    compared as exact fractions (passed / executions), not as the rounded percentages."""
    exact = lambda r: Fraction(100 * int(r["passed"]), int(r["executions"]))  # noqa: E731
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["use_case"])].append(r)
    out = []
    for (model, uc), rs in groups.items():
        rs = sorted(rs, key=lambda r: LEVELS.index(r["level"]))
        top = max(exact(r) for r in rs)
        best = next(r for r in rs if exact(r) == top)
        pick = next(r for r in rs if exact(r) >= top - Fraction(str(margin)))
        out.append({"model": model, "use_case": uc, "level": pick["level"], "score_pct": pick["score_pct"],
                    "minutes_per_run": pick["minutes_per_run"], "best_level": best["level"],
                    "best_score_pct": best["score_pct"], "best_minutes_per_run": best["minutes_per_run"],
                    "points_below_best": round(float(top - exact(pick)), 1),
                    "time_vs_best": round(float(pick["minutes_per_run"]) / float(best["minutes_per_run"]), 2)
                    if float(best["minutes_per_run"]) else ""})
    return out


def budget_markdown(rows, margin=BUDGET_MARGIN):
    """The budget table for the video: one row per model, one column per battery, `level · score · minutes`."""
    ucs = list(dict.fromkeys(r["use_case"] for r in rows))
    cell = {(r["model"], r["use_case"]): r for r in rows}
    head = ["All four batteries" if u == ALL else verdict.LABELS.get(u, u) for u in ucs]
    lines = ["# Thinking budget per task", "",
             f"Rule: for each model and battery, the lowest thinking level (off < 512 < 2048 < 8192 tokens) whose "
             f"score is within {margin:g} points of that model's best level on that battery. Each cell: level · "
             f"score · minutes per battery run. Source: `thinking-budget.csv` (and `thinking.csv` for every level).",
             "", "| Model | " + " | ".join(head) + " |", "| --- |" + " --- |" * len(ucs)]
    for m in dict.fromkeys(r["model"] for r in rows):
        cells = []
        for u in ucs:
            r = cell.get((m, u))
            mins = float(r["minutes_per_run"]) if r else 0
            cells.append(f"{r['level']} · {r['score_pct']}% · {mins:.{1 if mins < 10 else 0}f} min" if r else "—")
        lines.append(f"| `{m}` | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def write(episode):
    rows = table(episode)
    results = run.EPISODES / episode / "results"
    path = results / "thinking.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    picks = budget(rows)
    with open(results / "thinking-budget.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=BUDGET_COLUMNS)
        w.writeheader()
        w.writerows(picks)
    (results / "thinking-budget.md").write_text(budget_markdown(picks), encoding="utf-8")
    (results / "charts").mkdir(exist_ok=True)
    paths = [path, results / "thinking-budget.csv", results / "thinking-budget.md"]
    for uc in dict.fromkeys(r["use_case"] for r in rows):
        svg = results / "charts" / f"thinking-{uc}.svg"
        svg.write_text(chart([r for r in rows if r["use_case"] == uc], uc), encoding="utf-8")
        paths.append(svg)
    return paths


def chart(rows, use_case):
    """SVG line chart: x = minutes per battery run (log2), y = score %; one line per model, off -> highest level."""
    W, H, L, R, T, B = 840, 480, 56, 200, 122, 52
    pw, ph = W - L - R, H - T - B
    models = list(dict.fromkeys(r["model"] for r in rows))
    mins = [max(r["minutes_per_run"], 0.01) for r in rows]
    lo, hi = math.floor(math.log2(min(mins))), math.ceil(math.log2(max(mins)))
    hi = max(hi, lo + 1)
    x = lambda m: L + (math.log2(max(m, 0.01)) - lo) / (hi - lo) * pw  # noqa: E731
    y = lambda p: T + (100 - p) / 100 * ph  # noqa: E731
    name = "All four batteries" if use_case == ALL else verdict.LABELS.get(use_case, use_case)
    css_vars = lambda pal, ink: "".join(f"--s{i}:{c};" for i, c in enumerate(pal)) + ink  # noqa: E731
    light_ink = "--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;"
    dark_ink = "--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="system-ui, -apple-system, Segoe UI, sans-serif" role="img">',
           f"<title>{escape(name)}: score x time per thinking level</title>",
           "<style>"
           f"svg{{{css_vars(LIGHT, light_ink)}}}"
           f"@media (prefers-color-scheme: dark){{svg{{{css_vars(DARK, dark_ink)}}}}}"
           ".t{fill:var(--ink)}.t2{fill:var(--ink2)}.m{fill:var(--muted)}"
           ".tick{font-size:11px;font-variant-numeric:tabular-nums}"
           "</style>",
           f'<rect width="{W}" height="{H}" fill="var(--surface)"/>',
           f'<text class="t" x="{L}" y="28" font-size="17" font-weight="600">{escape(name)}: does thinking pay?</text>',
           f'<text class="t2" x="{L}" y="48" font-size="12">Score against time per battery run. Each line is one '
           f'model through its thinking levels:</text>',
           f'<text class="t2" x="{L}" y="64" font-size="12">off, then a budget of 512, 2048 and 8192 tokens '
           f'(a bigger dot is more thinking).</text>']
    # legend: one row, model order = color order, one fixed-width slot per model
    slot = max(len(m) for m in models) * 6.4 + 22
    for i, m in enumerate(models):
        lx = L + i * slot
        out.append(f'<circle cx="{lx + 5}" cy="88" r="5" fill="var(--s{i % len(LIGHT)})"/>'
                   f'<text class="t2" x="{lx + 14}" y="92" font-size="12">{escape(m)}</text>')
    # grid and axes
    for p in range(0, 101, 20):
        out.append(f'<line x1="{L}" x2="{L + pw}" y1="{y(p)}" y2="{y(p)}" stroke="var(--grid)" stroke-width="1"/>'
                   f'<text class="m tick" x="{L - 8}" y="{y(p) + 4}" text-anchor="end">{p}%</text>')
    for e in range(lo, hi + 1):
        v = 2 ** e
        label = f"{v:g} min" if v >= 1 else f"{round(v * 60)} s"
        out.append(f'<line x1="{x(v)}" x2="{x(v)}" y1="{T}" y2="{T + ph}" stroke="var(--grid)" stroke-width="1"/>'
                   f'<text class="m tick" x="{x(v)}" y="{T + ph + 18}" text-anchor="middle">{label}</text>')
    out.append(f'<line x1="{L}" x2="{L + pw}" y1="{T + ph}" y2="{T + ph}" stroke="var(--axis)" stroke-width="1"/>'
               f'<text class="m" x="{L + pw / 2}" y="{H - 10}" font-size="12" text-anchor="middle">'
               f'time per battery run (log scale)</text>')
    if use_case != ALL:  # the Good for line of the verdicts
        out.append(f'<line x1="{L}" x2="{L + pw}" y1="{y(80)}" y2="{y(80)}" stroke="var(--ink2)" stroke-width="1" '
                   f'stroke-dasharray="4 4"/><text class="t2" x="{L + 6}" y="{y(80) - 6}" font-size="11">'
                   f'Good for (80%)</text>')
    ends = []
    for i, m in enumerate(models):
        pts = sorted((r for r in rows if r["model"] == m), key=lambda r: LEVELS.index(r["level"]))
        color = f"var(--s{i % len(LIGHT)})"
        coords = " ".join(f"{x(r['minutes_per_run']):.1f},{y(r['score_pct']):.1f}" for r in pts)
        out.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        for r in pts:
            radius = 3.5 + 1.5 * LEVELS.index(r["level"])
            tip = (f"{m}, thinking {r['level']}: {r['score_pct']}% (runs {r['min_run_pct']} to {r['max_run_pct']}%), "
                   f"{r['minutes_per_run']} min per run" + (f", {r['length_cuts']} cut at max_tokens"
                                                             if r["length_cuts"] else ""))
            out.append(f'<circle cx="{x(r["minutes_per_run"]):.1f}" cy="{y(r["score_pct"]):.1f}" r="{radius}" '
                       f'fill="{color}" stroke="var(--surface)" stroke-width="2"><title>{escape(tip)}</title></circle>')
        last = pts[-1]
        ends.append([y(last["score_pct"]), m, color, x(last["minutes_per_run"])])
    # direct labels in the right margin, nudged apart so they never overlap
    ends.sort()
    for k in range(1, len(ends)):
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 14)
    for ly, m, color, ex in ends:
        out.append(f'<circle cx="{L + pw + 14}" cy="{ly:.1f}" r="4" fill="{color}"/>'
                   f'<text class="t" x="{L + pw + 22}" y="{ly + 4:.1f}" font-size="12">{escape(m)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
