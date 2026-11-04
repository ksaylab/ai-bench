"""Runs the use-case batteries against one or more models, N runs each (at least 3), and writes CSVs.

Each run goes to episodes/<ep>/results/runs/<YYYY-MM-DD-HHMM>-<machine>-<label>/ with meta.json (parameters),
env.json (machine), executions.csv (one row per case and run), responses.jsonl (the raw answer of every execution,
for audit), scores.csv (per use case), verdicts.csv and verdicts.md (Good for / Not good for). `--simulate` answers
with the cases' good examples, with no network: it exercises the plumbing.
"""
import csv
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from aibench import calibration, cases, client, env, gpu, judge, verdict

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "episodes"
MIN_RUNS = verdict.MIN_RUNS
COLUMNS = ["run_id", "machine", "model", "use_case", "case", "tier", "rep", "seed", "passed", "reason", "time_s",
           "prompt_tokens", "completion_tokens", "tok_s", "ttft_s", "gen_tok_s", "peak_vram_mib", "avg_power_w",
           "energy_wh", "cost_usd", "finish", "judge_score", "judge_cost_usd", "context_words", "battery"]


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


# OpenRouter's provider routing fields (https://openrouter.ai/docs/features/provider-routing): the table is sent as is,
# so anything else (a note, a typo) would reach the API.
PROVIDER_KEYS = ("order", "allow_fallbacks", "require_parameters", "data_collection", "zdr", "only", "ignore",
                 "quantizations", "sort", "max_price")


def check_provider(models, providers, smoke=False, simulate=False):
    """Every OpenRouter model needs one pinned provider that refuses the parameters it would ignore (seed among them),
    with no fallback to another provider (METHODOLOGY.md 8.4); --smoke and --simulate are exempt."""
    if smoke or simulate:
        return
    for m in models:
        p = (providers or {}).get(m) or {}
        if not p.get("order") or p.get("allow_fallbacks") is not False or p.get("require_parameters") is not True:
            raise RunError(f"[anchor.provider] of {m} must pin a provider: order = [\"<provider>\"], "
                           "allow_fallbacks = false, require_parameters = true (or use --smoke, not publishable)")
        if unknown := set(p) - set(PROVIDER_KEYS):
            raise RunError(f"[anchor.provider] of {m}: unknown key(s) {', '.join(sorted(unknown))} (it is sent to "
                           "OpenRouter as is)")


# OpenRouter's reasoning object (https://openrouter.ai/docs/use-cases/reasoning-tokens), also sent as is.
REASONING_KEYS = ("effort", "max_tokens", "exclude", "enabled")


def check_reasoning(models, reasoning):
    """An [anchor.reasoning] table is optional (a model without reasoning has none: with require_parameters, sending
    it would remove the provider), but it reaches the API as is, so unknown keys are refused even in a smoke run."""
    for m in models:
        if unknown := set((reasoning or {}).get(m) or {}) - set(REASONING_KEYS):
            raise RunError(f"[anchor.reasoning] of {m}: unknown key(s) {', '.join(sorted(unknown))}")


def simulated_answer(case, rep):
    """No network: the case's good example, except the coding cases on run 3 (so the scores vary)."""
    ex = case["example_bad"] if (case["use_case"] == "coding" and rep == 2) else case["example_good"]
    a = cases.as_answer(ex)
    return {**a, "finish": "stop", "prompt_tokens": len(case["prompt"].split()),
            "completion_tokens": len(a["text"].split()), "cost_usd": 0.0, "time_s": 0.01, "tok_s": None,
            "ttft_s": 0.005, "gen_tok_s": None}


RESPONSE_FIELDS = ("text", "reasoning", "tool_calls", "finish", "provider", "error")


def response_line(row, answer):
    """One line of responses.jsonl: which execution it is, the verdict of the checker and the raw answer."""
    keys = ("run_id", "model", "use_case", "case", "rep", "seed", "passed", "reason")
    return {**{k: row[k] for k in keys}, **{k: answer.get(k, "" if k != "tool_calls" else []) for k in RESPONSE_FIELDS}}


def sampler_factory(machine, model_url, simulate=False, enabled=True, env_vars=os.environ):
    """A function that makes a fresh GPU sampler (one per model): nvidia-smi where the model server runs."""
    host = env_vars.get("AIBENCH_SERVER_HOST")
    if simulate or not enabled or machine == "openrouter":
        reason = "simulated run" if simulate else "cloud model" if machine == "openrouter" else "--no-gpu-sampling"
        return lambda: gpu.Disabled(reason)
    remote = env.server_is_remote(machine, model_url)
    if remote and not host:
        return lambda: gpu.Disabled("remote model server without AIBENCH_SERVER_HOST")
    return lambda: gpu.Sampler(host if remote else None)


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_results(folder, rows, reference=None):
    s = verdict.scores(rows, reference)
    v = verdict.verdicts(s)
    write_csv(folder / "scores.csv", verdict.SCORE_COLUMNS, s)
    write_csv(folder / "verdicts.csv", verdict.VERDICT_COLUMNS, v)
    (folder / "verdicts.md").write_text(verdict.markdown(v), encoding="utf-8")
    return v


def run(episode, machine, models, runs=MIN_RUNS, url=None, use_cases=None, judge_model=None, context_words=3000,
        label="run", simulate=False, smoke=False, skip_code=False, max_tokens=8192, out=None, log=print,
        judge_url=None, sampling=None, server_args=None, anchors=None, root=None, model_info=None, stream=True,
        gpu_sampling=True, providers=None, reasoning=None, case_ids=None):
    """`sampling`: model -> its [model.sampling] table (temperature, top_p, ..., base seed). `server_args`: the model
    server's command line, recorded in meta.json (paths and addresses scrubbed). `anchors`: model -> role, for a
    calibration run (`root` = calibration/, `model_info` = prices read from OpenRouter). `stream`: streaming
    responses, for the time to first token. `gpu_sampling`: nvidia-smi on the model server during the run.
    `providers`: model -> its [anchor.provider] table, sent as OpenRouter's `provider` routing object.
    `reasoning`: model -> its [anchor.reasoning] table, sent as OpenRouter's `reasoning` object (e.g. the effort).
    `case_ids`: only these cases (to screen a few on the anchors); a partial battery cannot be published."""
    ep = EPISODES / episode if episode else None
    if root is None and (ep is None or not ep.is_dir()):
        raise RunError(f"episode {episode!r} not found in {EPISODES.name}/")
    if not models:
        raise RunError("no models (use --models or the episode's models.toml)")
    if case_ids and not smoke:
        raise RunError("a run with only some cases (--cases) gives no battery score: use --smoke, it cannot be "
                       "published")
    if runs < MIN_RUNS and not smoke:
        raise RunError(f"the methodology requires at least {MIN_RUNS} runs (use --smoke for a quick test that "
                       "cannot be published)")
    if judge_model and judge_model in models:
        raise RunError(f"the judge {judge_model} is also one of the compared models: pick another judge")
    if judge_model and judge_model in calibration.anchor_names():
        raise RunError(f"the judge {judge_model} is a calibration anchor (anchors.toml): pick another judge")
    sampling = {m: dict((sampling or {}).get(m) or {}) for m in models}
    check_sampling(models, sampling, smoke, simulate)
    providers = {m: (providers or {}).get(m) for m in models}
    if machine == "openrouter":
        check_provider(models, providers, smoke, simulate)
    reasoning = {m: (reasoning or {}).get(m) for m in models}
    check_reasoning(models, reasoning)
    extra = {m: {k: v for k, v in (("provider", providers[m]), ("reasoning", reasoning[m])) if v} or None
             for m in models}
    for m in models:
        if sampling[m] and not sampling[m].get("verified", True):
            log(f"warning: the sampling of {m} is not verified against its model card (verified = false)")
    battery = cases.load(use_cases, context_words)
    if case_ids:
        if missing := sorted(set(case_ids) - {c["id"] for c in battery}):
            raise RunError(f"no case with id {', '.join(missing)}" + (" in these use cases" if use_cases else ""))
        battery = [c for c in battery if c["id"] in set(case_ids)]
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
    dest = Path(out) if out else (Path(root) if root else ep / "results") / "runs" / run_id
    dest.mkdir(parents=True, exist_ok=True)
    environment = {"machine": machine, "simulated": True} if simulate else env.capture(
        machine, model_url, server_host=os.environ.get("AIBENCH_SERVER_HOST"), models=models)
    hashes = {uc: cases.battery_hash(uc, context_words) for uc in sorted({c["use_case"] for c in battery})}
    meta = {"run_id": run_id, "episode": episode or "", "machine": machine, "models": models, "runs": runs,
            "use_cases": sorted({c["use_case"] for c in battery}), "cases": [c["id"] for c in battery],
            "context_words": context_words, "judge": judge_model or "", "start": now.isoformat(timespec="seconds"),
            "smoke": smoke, "simulated": simulate, "max_tokens": max_tokens, "publishable": not (smoke or simulate),
            "thresholds_pct": verdict.GOOD_THRESHOLD,
            "sampling": {m: {"sent": client.sampling_body({k: v for k, v in sampling[m].items() if k != "seed"}),
                             "base_seed": sampling[m].get("seed"),
                             "seeds": [rep_seed(sampling[m], rep) for rep in range(runs)],
                             **{k: sampling[m][k] for k in ("source", "card", "verified") if k in sampling[m]}}
                         for m in models},
            "server_args": env.scrub(server_args or os.environ.get("AIBENCH_SERVER_ARGS", "")),
            "battery": hashes, "checker_version": cases.CHECKER_VERSION,
            "requests": {c["id"]: cases.request_hash(c) for c in battery}}
    if anchors:
        meta["anchors"] = {m: {"role": anchors[m], **((model_info or {}).get(m) or {}),
                               **(extra[m] or {})} for m in models}
        meta["anchors_checked"] = now.date().isoformat()
    (dest / "env.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_sampler = sampler_factory(machine, model_url, simulate, gpu_sampling)
    meta["stream"] = stream and not simulate
    gpu_summary = {}
    rows = []
    with open(dest / "executions.csv", "w", newline="", encoding="utf-8") as f, \
            open(dest / "responses.jsonl", "w", encoding="utf-8") as raw:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for model in models:
            sampler = new_sampler().start()
            try:
                for rep in range(runs):
                    seed = rep_seed(sampling[model], rep)
                    params = {**sampling[model], "seed": seed} if seed is not None else sampling[model]
                    for c in battery:
                        t0 = time.monotonic()
                        try:
                            r = simulated_answer(c, rep) if simulate else client.chat(
                                model_url, model, cases.messages(c), key=key, max_tokens=max_tokens,
                                tools=c.get("tool_specs"), sampling=params, stream=stream,
                                extra=extra[model])
                            passed, reason = cases.check(c, r)
                        except client.ClientError as e:
                            r, passed, reason = {"error": str(e)}, False, f"error: {e}"
                        power = sampler.window(t0, time.monotonic())
                        score = judge_cost = ""
                        if judge_model and c.get("rubric") and r.get("text") and not simulate:
                            try:
                                s, jc = judge.grade(judge_url, judge_key, judge_model, c, r["text"])
                                score = "" if s is None else s
                                judge_cost = "" if jc is None else jc
                            except client.ClientError:
                                pass
                        row = {"run_id": run_id, "machine": machine, "model": model, "use_case": c["use_case"],
                               "case": c["id"], "tier": c["tier"], "rep": rep, "seed": "" if seed is None else seed,
                               "passed": int(passed), "reason": reason,
                               "time_s": r.get("time_s", ""), "prompt_tokens": r.get("prompt_tokens") or "",
                               "completion_tokens": r.get("completion_tokens") or "", "tok_s": r.get("tok_s") or "",
                               "ttft_s": "" if r.get("ttft_s") is None else r["ttft_s"],
                               "gen_tok_s": r.get("gen_tok_s") or "", **power,
                               "cost_usd": "" if r.get("cost_usd") is None else r["cost_usd"],
                               "finish": r.get("finish", ""), "judge_score": score, "judge_cost_usd": judge_cost,
                               "context_words": c.get("context_words", ""), "battery": hashes[c["use_case"]]}
                        w.writerow(row)
                        f.flush()
                        raw.write(json.dumps(response_line(row, r), ensure_ascii=False) + "\n")
                        raw.flush()
                        rows.append(row)
                    done = [x for x in rows if x["model"] == model and x["rep"] == rep]
                    log(f"{model} · run {rep + 1}/{runs}: {sum(x['passed'] for x in done)}/{len(done)}")
            finally:
                gpu_summary[model] = sampler.stop().summary()
    meta["gpu_sampling"] = gpu_summary
    meta["end"] = datetime.now().isoformat(timespec="seconds")
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_results(dest, rows, None if anchors else calibration.load_reference())
    return dest


def record_requests(folder):
    """Adds the request hashes (meta.json `requests`) to a run made before runs recorded them. Only allowed while
    every battery of the run is on the version it ran, because the hashes come from the current case files."""
    folder = Path(folder)
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    cw = meta.get("context_words", 3000)
    if moved := [uc for uc in meta["use_cases"] if cases.battery_hash(uc, cw) != meta["battery"].get(uc)]:
        raise RunError(f"the battery version of {', '.join(moved)} changed since {folder.name} ran: its request "
                       "hashes cannot be rebuilt from the current case files")
    by_id = {c["id"]: c for c in cases.load(meta["use_cases"], cw)}
    meta["requests"] = {i: cases.request_hash(by_id[i]) for i in meta["cases"]}
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rescore(folder, log=print):
    """Checks the saved answers of a run again with the current cases and checker, with no new calls, into a new run
    folder next to it (`<run id>-rescored-<date>`, `rescored_from` in meta.json). Only the use cases whose battery
    version changed are rescored, and only when every one of their cases still sends the same request (prompt,
    history, tools): otherwise the saved answers answer another question. Time, tokens and cost stay as measured;
    the tier comes from the current case."""
    src = Path(folder)
    old = json.loads((src / "meta.json").read_text(encoding="utf-8"))
    if old.get("judge"):
        raise RunError("a run scored by a judge is not rescored: the judge would have to grade the answers again")
    if not old.get("requests"):
        raise RunError(f"{src.name} has no request hashes (meta.json `requests`), so a changed prompt could not be "
                       "told apart: rerun it")
    cw = old.get("context_words", 3000)
    hashes = {uc: cases.battery_hash(uc, cw) for uc in old["use_cases"]}
    changed = [uc for uc in old["use_cases"] if hashes[uc] != old["battery"].get(uc)]
    if not changed:
        raise RunError(f"every battery of {src.name} is on the same battery version as when it ran: nothing to "
                       "rescore")
    with open(src / "executions.csv", encoding="utf-8") as f:
        source_rows = [r for r in csv.DictReader(f) if r["use_case"] in changed]
    answers = {(x["model"], x["case"], str(x["rep"])): x
               for x in map(json.loads, (src / "responses.jsonl").read_text(encoding="utf-8").splitlines())}
    by_id = {c["id"]: c for c in cases.load(changed, cw)}
    ids = list(dict.fromkeys(r["case"] for r in source_rows))
    if moved := [i for i in ids if i not in by_id or cases.request_hash(by_id[i]) != old["requests"].get(i)]:
        raise RunError(f"these cases are gone or send another request since {src.name} ran, so their saved answers "
                       f"cannot be rescored: {', '.join(moved)} (rerun those use cases)")
    now = datetime.now()
    run_id = f"{old['run_id']}-rescored-{now:%Y%m%d-%H%M}"
    dest = src.parent / run_id
    dest.mkdir()
    rows, lines = [], []
    for r in source_rows:
        c, a = by_id[r["case"]], answers[(r["model"], r["case"], r["rep"])]
        passed, reason = (False, r["reason"]) if a.get("error") else cases.check(c, a)
        row = {**r, "run_id": run_id, "tier": c["tier"], "passed": int(passed), "reason": reason,
               "battery": hashes[c["use_case"]]}
        rows.append(row)
        lines.append({**a, "run_id": run_id, "passed": int(passed), "reason": reason})
    write_csv(dest / "executions.csv", COLUMNS, rows)
    (dest / "responses.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines),
                                          encoding="utf-8")
    shutil.copy(src / "env.json", dest / "env.json")
    meta = {**old, "run_id": run_id, "use_cases": changed, "cases": ids,
            "battery": {uc: hashes[uc] for uc in changed}, "checker_version": cases.CHECKER_VERSION,
            "requests": {i: old["requests"][i] for i in ids}, "rescored_from": old["run_id"],
            "rescored": now.isoformat(timespec="seconds")}
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for model in old["models"]:
        done = [x for x in rows if x["model"] == model]
        before = sum(int(x["passed"]) for x in source_rows if x["model"] == model)
        log(f"{model}: {sum(x['passed'] for x in done)}/{len(done)} (was {before}/{len(done)})")
    write_results(dest, rows, None if old.get("anchors") else calibration.load_reference())
    return dest


def copy_run(folder, episode):
    """Copies a finished run into another episode that lists the same model on the same machine with the same GGUF
    and the same pinned sampling and seed: running it again would ask the same questions with the same seeds. The
    copy says where it came from (`copied_from` in meta.json); the source is not changed. The GGUF is the one the
    server reported (env.json), the sampling the one the run sent (meta.json)."""
    import tomllib  # only here: run.py reads no models.toml otherwise
    src = Path(folder)
    if not (src / "meta.json").exists():
        raise RunError(f"{src.name} has not finished (no meta.json yet): copy it when it ends")
    meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
    toml = EPISODES / episode / "models.toml"
    if not toml.exists():
        raise RunError(f"episode {episode!r} not found in {EPISODES.name}/ (or it has no models.toml)")
    if meta.get("episode") == episode:
        raise RunError(f"{src.name} is already a run of the same episode {episode}")
    with open(toml, "rb") as f:
        entries = {m["name"]: m for m in tomllib.load(f).get("model", [])}
    served = (json.loads((src / "env.json").read_text(encoding="utf-8")).get("server") or {}).get("gguf") or {}
    problems = []
    for m in meta["models"]:
        e = entries.get(m)
        if not e or meta["machine"] not in e.get("machines", []):
            problems.append(f"{m}: not in {episode}'s models.toml for {meta['machine']}")
            continue
        if served.get(m) != e.get("gguf"):
            problems.append(f"{m}: the run used the GGUF {served.get(m)!r}, {episode} lists {e.get('gguf')!r}")
        want = e.get("sampling") or {}
        ran = meta["sampling"][m]
        if client.sampling_body({k: v for k, v in want.items() if k != "seed"}) != ran["sent"]:
            problems.append(f"{m}: the run sent the sampling {ran['sent']}, {episode} pins another one")
        if want.get("seed") != ran.get("base_seed"):
            problems.append(f"{m}: the run's base seed is {ran.get('base_seed')}, {episode} pins {want.get('seed')}")
    if problems:
        raise RunError("not the same setup, run it in that episode instead: " + "; ".join(problems))
    dest = EPISODES / episode / "results" / "runs" / src.name
    if dest.exists():
        raise RunError(f"{_rel_name(dest)} already exists")
    shutil.copytree(src, dest)
    meta = {**meta, "episode": episode, "copied_from": {"episode": meta.get("episode", ""), "run_id": meta["run_id"]}}
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def _rel_name(p):
    return "/".join(Path(p).parts[-4:])


def replaced(metas):
    """{(run id, use case)} that a rescored run stands in for: its source's rows of the use cases it rescored are
    left out when runs are merged (the other use cases of the source stay)."""
    return {(m["rescored_from"], uc) for m in metas if m.get("rescored_from") for uc in m.get("battery", {})}


NOT_PUBLISHABLE_SUFFIXES = ("-simulated", "-smoke")


def excluded(meta, folder, calibration=False):
    """Why a run folder must stay out of the results ("" = it can be merged). A run is merged only when its meta.json
    says publishable, it is not simulated, smoke or pilot (by meta.json AND by folder name, so a hand-edited meta.json
    cannot sneak a dry run in), and it ran on a known local or rented target (OpenRouter runs are calibration anchors,
    never episode contestants). With calibration=True (calibration/runs/), only OpenRouter anchor runs are merged."""
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
    if calibration:
        return "" if meta.get("machine") == "openrouter" and meta.get("anchors") else "not an anchor run"
    if meta.get("machine") == "openrouter":
        return "OpenRouter runs are calibration anchors, not contestants"
    return ""


def check_battery_versions(rows):
    """verdict merges runs of one battery version per use case only (METHODOLOGY.md 8.3: frozen battery)."""
    versions = {}
    for r in rows:
        versions.setdefault(r["use_case"], set()).add(r.get("battery", ""))
    mixed = {uc: v for uc, v in versions.items() if len(v) > 1}
    if mixed:
        raise RunError("runs made with different battery versions: " + "; ".join(
            f"{uc} ({', '.join(sorted(x or 'unrecorded' for x in v))})" for uc, v in sorted(mixed.items())) +
            ". Rerun with the frozen battery or move the old runs out of results/runs/")


def consolidate(episode, log=None):
    """Merges the episode's publishable runs into results/executions.csv, scores.csv, verdicts.csv, verdicts.md and
    speed.csv (from the `speed` runs)."""
    folder = EPISODES / episode / "results"
    rows, speed_rows = [], []
    metas = {p: json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("runs/*/meta.json"))}
    gone = replaced(metas.values())
    for meta, m in metas.items():
        why = excluded(m, meta.parent)
        if why:
            if log:
                log(f"skipped {meta.parent.name}: {why}")
            continue
        for name, dest in (("executions.csv", rows), ("speed.csv", speed_rows)):
            if (meta.parent / name).exists():
                with open(meta.parent / name, encoding="utf-8") as f:
                    dest += [r for r in csv.DictReader(f) if (r.get("run_id"), r.get("use_case")) not in gone]
    from aibench import speed  # speed imports nothing from run
    write_csv(folder / "speed.csv", speed.COLUMNS, speed_rows)
    check_battery_versions(rows)
    write_csv(folder / "executions.csv", COLUMNS, rows)
    v = write_results(folder, rows, calibration.load_reference()) if rows else []
    if not rows:
        write_csv(folder / "scores.csv", verdict.SCORE_COLUMNS, [])
        write_csv(folder / "verdicts.csv", verdict.VERDICT_COLUMNS, [])
        (folder / "verdicts.md").write_text("No publishable runs yet (pilot, simulated and smoke runs are left out; "
                                            "see METHODOLOGY.md).\n", encoding="utf-8")
    return folder / "verdicts.csv", len(rows), v
