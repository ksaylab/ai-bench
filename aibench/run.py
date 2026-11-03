"""Runs the use-case batteries against one or more models, N runs each (at least 3), and writes CSVs.

Each run goes to episodes/<ep>/results/runs/<YYYY-MM-DD-HHMM>-<machine>-<label>/ with meta.json (parameters),
env.json (machine), executions.csv (one row per case and run), responses.jsonl (the raw answer of every execution,
for audit), scores.csv (per use case), verdicts.csv and verdicts.md (Good for / Not good for). `--simulate` answers with the cases' good examples, with no network: it
exercises the plumbing.
"""
import csv
import json
import os
from datetime import datetime
from pathlib import Path

from aibench import cases, client, env, judge, verdict

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "episodes"
MIN_RUNS = verdict.MIN_RUNS
COLUMNS = ["run_id", "machine", "model", "use_case", "case", "rep", "seed", "passed", "reason", "time_s",
           "prompt_tokens", "completion_tokens", "tok_s", "cost_usd", "finish", "judge_score", "judge_cost_usd",
           "context_words"]


class RunError(Exception):
    pass


def rep_seed(sampling, rep):
    """The seed of one repeat: the table's base seed + the repeat number (reproducible, yet different per repeat)."""
    return None if (sampling or {}).get("seed") is None else int(sampling["seed"]) + rep


def check_sampling(models, sampling, smoke=False, simulate=False):
    """Every model needs a pinned sampling table with a seed (METHODOLOGY.md 8.4); --smoke and --simulate are exempt."""
    if smoke or simulate:
        return
    missing = [m for m in models if not (sampling or {}).get(m)]
    if missing:
        raise RunError(f"no [model.sampling] table for {', '.join(missing)} in models.toml (or anchors.toml): "
                       "pin the sampling or use --smoke (not publishable)")
    for m in models:
        if sampling[m].get("seed") is None:
            raise RunError(f"[model.sampling] of {m} needs a seed")
        unknown = set(sampling[m]) - set(client.SAMPLING_KEYS) - {"source", "card", "verified"}
        if unknown:
            raise RunError(f"[model.sampling] of {m}: unknown key(s) {', '.join(sorted(unknown))}")


def simulated_answer(case, rep):
    """No network: the case's good example, except the coding cases on run 3 (so the scores vary)."""
    ex = case["example_bad"] if (case["use_case"] == "coding" and rep == 2) else case["example_good"]
    a = cases.as_answer(ex)
    return {**a, "finish": "stop", "prompt_tokens": len(case["prompt"].split()),
            "completion_tokens": len(a["text"].split()), "cost_usd": 0.0, "time_s": 0.01, "tok_s": None}


RESPONSE_FIELDS = ("text", "reasoning", "tool_calls", "finish", "error")


def response_line(row, answer):
    """One line of responses.jsonl: which execution it is, the verdict of the checker and the raw answer."""
    keys = ("run_id", "model", "use_case", "case", "rep", "seed", "passed", "reason")
    return {**{k: row[k] for k in keys}, **{k: answer.get(k, "" if k != "tool_calls" else []) for k in RESPONSE_FIELDS}}


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_results(folder, rows):
    s = verdict.scores(rows)
    v = verdict.verdicts(s)
    write_csv(folder / "scores.csv", verdict.SCORE_COLUMNS, s)
    write_csv(folder / "verdicts.csv", verdict.VERDICT_COLUMNS, v)
    (folder / "verdicts.md").write_text(verdict.markdown(v), encoding="utf-8")
    return v


def run(episode, machine, models, runs=MIN_RUNS, url=None, use_cases=None, judge_model=None, context_words=3000,
        label="run", simulate=False, smoke=False, skip_code=False, max_tokens=8192, out=None, log=print,
        judge_url=None, sampling=None, server_args=None):
    """`sampling`: model -> its [model.sampling] table (temperature, top_p, ..., base seed). `server_args`: the model
    server's command line, recorded in meta.json (paths and addresses scrubbed)."""
    ep = EPISODES / episode
    if not ep.is_dir():
        raise RunError(f"episode {episode!r} not found in {EPISODES.name}/")
    if not models:
        raise RunError("no models (use --models or the episode's models.toml)")
    if runs < MIN_RUNS and not smoke:
        raise RunError(f"the methodology requires at least {MIN_RUNS} runs (use --smoke for a quick test that "
                       "cannot be published)")
    if judge_model and judge_model in models:
        raise RunError(f"the judge {judge_model} is also one of the compared models: pick another judge")
    sampling = {m: dict((sampling or {}).get(m) or {}) for m in models}
    check_sampling(models, sampling, smoke, simulate)
    for m in models:
        if sampling[m] and not sampling[m].get("verified", True):
            log(f"warning: the sampling of {m} is not verified against its model card (verified = false)")
    battery = cases.load(use_cases, context_words)
    if skip_code:
        battery = [c for c in battery if c["kind"] != "code"]
    if not battery:
        raise RunError("no cases with these filters")
    if simulate:
        model_url, key = "simulated", None
    else:
        model_url, key = client.resolve_target(machine, url)
    judge_key = None
    if judge_model and not simulate:
        # the judge uses the same address as the models when the run is already on OpenRouter (or a proxy of it)
        judge_url, judge_key = client.resolve_target("openrouter", judge_url or (url if machine == "openrouter" else None))
    now = datetime.now()
    run_id = f"{now:%Y-%m-%d-%H%M}-{machine}-{label}" + ("-smoke" if smoke else "") + ("-simulated" if simulate else "")
    dest = Path(out) if out else ep / "results" / "runs" / run_id
    dest.mkdir(parents=True, exist_ok=True)
    environment = {"machine": machine, "simulated": True} if simulate else env.capture(
        machine, model_url, server_host=os.environ.get("AIBENCH_SERVER_HOST"), models=models)
    meta = {"run_id": run_id, "episode": episode, "machine": machine, "models": models, "runs": runs,
            "use_cases": sorted({c["use_case"] for c in battery}), "cases": [c["id"] for c in battery],
            "context_words": context_words, "judge": judge_model or "", "start": now.isoformat(timespec="seconds"),
            "smoke": smoke, "simulated": simulate, "max_tokens": max_tokens, "publishable": not (smoke or simulate),
            "thresholds_pct": verdict.GOOD_THRESHOLD,
            "sampling": {m: {"sent": client.sampling_body({k: v for k, v in sampling[m].items() if k != "seed"}),
                             "base_seed": sampling[m].get("seed"),
                             "seeds": [rep_seed(sampling[m], rep) for rep in range(runs)],
                             **{k: sampling[m][k] for k in ("source", "card", "verified") if k in sampling[m]}}
                         for m in models},
            "server_args": env.scrub(server_args or os.environ.get("AIBENCH_SERVER_ARGS", ""))}
    (dest / "env.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    with open(dest / "executions.csv", "w", newline="", encoding="utf-8") as f, \
            open(dest / "responses.jsonl", "w", encoding="utf-8") as raw:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for model in models:
            for rep in range(runs):
                seed = rep_seed(sampling[model], rep)
                params = {**sampling[model], "seed": seed} if seed is not None else sampling[model]
                for c in battery:
                    try:
                        r = simulated_answer(c, rep) if simulate else client.chat(
                            model_url, model, cases.messages(c), key=key, max_tokens=max_tokens,
                            tools=c.get("tool_specs"), sampling=params)
                        passed, reason = cases.check(c, r)
                    except client.ClientError as e:
                        r, passed, reason = {"error": str(e)}, False, f"error: {e}"
                    score = judge_cost = ""
                    if judge_model and c.get("rubric") and r.get("text") and not simulate:
                        try:
                            s, jc = judge.grade(judge_url, judge_key, judge_model, c, r["text"])
                            score = "" if s is None else s
                            judge_cost = "" if jc is None else jc
                        except client.ClientError:
                            pass
                    row = {"run_id": run_id, "machine": machine, "model": model, "use_case": c["use_case"],
                           "case": c["id"], "rep": rep, "seed": "" if seed is None else seed, "passed": int(passed), "reason": reason,
                           "time_s": r.get("time_s", ""), "prompt_tokens": r.get("prompt_tokens") or "",
                           "completion_tokens": r.get("completion_tokens") or "", "tok_s": r.get("tok_s") or "",
                           "cost_usd": "" if r.get("cost_usd") is None else r["cost_usd"],
                           "finish": r.get("finish", ""), "judge_score": score, "judge_cost_usd": judge_cost,
                           "context_words": c.get("context_words", "")}
                    w.writerow(row)
                    f.flush()
                    raw.write(json.dumps(response_line(row, r), ensure_ascii=False) + "\n")
                    raw.flush()
                    rows.append(row)
                done = [x for x in rows if x["model"] == model and x["rep"] == rep]
                log(f"{model} · run {rep + 1}/{runs}: {sum(x['passed'] for x in done)}/{len(done)}")
    meta["end"] = datetime.now().isoformat(timespec="seconds")
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_results(dest, rows)
    return dest


NOT_PUBLISHABLE_SUFFIXES = ("-simulated", "-smoke")


def excluded(meta, folder):
    """Why a run folder must stay out of the results ("" = it can be merged). A run is merged only when its meta.json
    says publishable, it is not simulated, smoke or pilot (by meta.json AND by folder name, so a hand-edited meta.json
    cannot sneak a dry run in), and it ran on a known local or rented target (OpenRouter runs are calibration anchors,
    never episode contestants)."""
    name = Path(folder).name
    if meta.get("simulated") or name.endswith("-simulated") or "-simulated-" in name:
        return "simulated"
    if meta.get("smoke") or any(name.endswith(s) or s + "-" in name for s in NOT_PUBLISHABLE_SUFFIXES):
        return "smoke"
    if meta.get("status") == "pilot":
        return "pilot"
    if not meta.get("publishable"):
        return "not publishable"
    if meta.get("machine") not in client.TARGETS:
        return f"unknown machine {meta.get('machine')!r}"
    if meta.get("machine") == "openrouter":
        return "OpenRouter runs are calibration anchors, not contestants"
    return ""


def consolidate(episode, log=None):
    """Merges the episode's publishable runs into results/executions.csv, scores.csv, verdicts.csv and verdicts.md."""
    folder = EPISODES / episode / "results"
    rows = []
    for meta in sorted(folder.glob("runs/*/meta.json")):
        why = excluded(json.loads(meta.read_text(encoding="utf-8")), meta.parent)
        if why:
            if log:
                log(f"skipped {meta.parent.name}: {why}")
            continue
        with open(meta.parent / "executions.csv", encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    write_csv(folder / "executions.csv", COLUMNS, rows)
    v = write_results(folder, rows) if rows else []
    if not rows:
        write_csv(folder / "scores.csv", verdict.SCORE_COLUMNS, [])
        write_csv(folder / "verdicts.csv", verdict.VERDICT_COLUMNS, [])
        (folder / "verdicts.md").write_text("No publishable runs yet (pilot, simulated and smoke runs are left out; "
                                            "see METHODOLOGY.md).\n", encoding="utf-8")
    return folder / "verdicts.csv", len(rows), v
