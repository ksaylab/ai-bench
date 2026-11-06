"""CLI: python3 -m aibench <command>. See HOW-TO-RUN.md."""
import argparse
import csv
import json
import os
import sys
import tomllib
from datetime import datetime
from pathlib import Path

from aibench import calibration, cases, client, cost, env, gpu, run, speed, thinking

EPISODES = run.EPISODES
COST_EPISODE = "01-buy-or-rent-gpu"


def episode_models(episode, machine, group=None):
    path = EPISODES / episode / "models.toml"
    if not path.exists():
        return []
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    return [m for m in cfg.get("model", []) if machine in m.get("machines", [])
            and (group is None or m.get("group") == group)]


def model_sampling(episode, names):
    """name -> [model.sampling] table, from the episode's models.toml and the calibration anchors (anchors.toml)."""
    found = {}
    for path in (run.ROOT / "anchors.toml", EPISODES / episode / "models.toml"):
        if path.exists():
            with open(path, "rb") as f:
                cfg = tomllib.load(f)
            for m in cfg.get("model", []) + cfg.get("anchor", []):
                if m["name"] in names and m.get("sampling"):
                    found[m["name"]] = m["sampling"]
    return found


def episode_thinking(episode, names):
    """The thinking level the episode pins for these models (`thinking` in models.toml, as copy-run compares it);
    None when none of them pins one (the server preset's budget). One run sends one level, so models with different
    levels are refused: run them apart."""
    levels = {}
    path = EPISODES / episode / "models.toml"
    if path.exists():
        with open(path, "rb") as f:
            levels = {m["name"]: m.get("thinking") for m in tomllib.load(f).get("model", []) if m["name"] in names}
    found = {run.thinking_level(v) if v is not None else None for v in (levels.get(n) for n in names)}
    if len(found) > 1:
        raise ValueError(f"{episode} pins different thinking levels for {', '.join(names)} "
                         f"({', '.join(f'{n}: {levels.get(n) or 'the preset'}' for n in names)}): run them apart")
    return found.pop() if found else None


def _rel(p):
    return p.relative_to(run.ROOT) if p.is_relative_to(run.ROOT) else p


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m aibench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    machines = list(client.TARGETS)

    p = sub.add_parser("env", help="record the machine environment as JSON")
    p.add_argument("--machine", required=True, choices=machines)
    p.add_argument("--url")
    p.add_argument("--models", help="comma separated: records the GGUF of each one (llama-server in router mode)")
    p.add_argument("--out")

    p = sub.add_parser("run", help="run the use-case batteries (score, verdict, time, cost)")
    p.add_argument("--episode", required=True)
    p.add_argument("--machine", required=True, choices=machines)
    p.add_argument("--models", help="comma separated; default: the episode's models.toml entries for the machine")
    p.add_argument("--group", help="only the models.toml models in this group")
    p.add_argument("--runs", type=int, default=run.MIN_RUNS)
    p.add_argument("--url")
    p.add_argument("--use-cases", help=f"comma separated, from {','.join(cases.USE_CASES)} (default: all)")
    p.add_argument("--judge", help="OpenRouter model that scores the cases with a rubric (cannot be a compared model)")
    p.add_argument("--judge-url", help="OpenRouter-compatible address for the judge (default: OpenRouter)")
    p.add_argument("--context-words", type=int, default=3000, help="size of the long RAG documents")
    p.add_argument("--max-tokens", type=int, default=32768,
                   help="room to reason, as the anchors: a model cut at the limit fails for lack of room, not of skill")
    p.add_argument("--thinking", help="off, unlimited, or a reasoning budget in tokens (e.g. 512), sent per request to "
                                      "llama-server over the preset's; each level is its own contestant, "
                                      "model@think-<level>")
    p.add_argument("--server-args", help="the model server's command line, recorded in meta.json "
                                         "(default: AIBENCH_SERVER_ARGS)")
    p.add_argument("--label", default="run")
    p.add_argument("--no-stream", action="store_true", help="no streaming responses (no measured time to first token)")
    p.add_argument("--no-gpu-sampling", action="store_true", help="do not sample nvidia-smi on the model server")
    p.add_argument("--simulate", action="store_true", help="no network: answer with the cases' examples")
    p.add_argument("--smoke", action="store_true", help="allow fewer than 3 runs; the run cannot be published")
    p.add_argument("--skip-code", action="store_true", help="do not execute code written by the models")
    p.add_argument("--out")

    p = sub.add_parser("calibrate", help="run the batteries on the OpenRouter anchors (anchors.toml; paid)")
    p.add_argument("--models", help="comma separated subset of the anchors (default: all of anchors.toml)")
    p.add_argument("--runs", type=int, default=run.MIN_RUNS)
    p.add_argument("--url", help="OpenRouter-compatible address (default: OpenRouter)")
    p.add_argument("--use-cases", help=f"comma separated, from {','.join(cases.USE_CASES)} (default: all)")
    p.add_argument("--context-words", type=int, default=3000, help="size of the long RAG documents")
    p.add_argument("--max-tokens", type=int, default=32768,
                   help="room to reason: a ceiling cut at the limit fails for lack of room, not of skill")
    p.add_argument("--cases", help="comma separated case ids, to screen a few cases (needs --smoke: not publishable)")
    p.add_argument("--label", default="anchors")
    p.add_argument("--simulate", action="store_true", help="no network: answer with the cases' examples")
    p.add_argument("--smoke", action="store_true", help="allow fewer than 3 runs; the run cannot be published")
    p.add_argument("--skip-code", action="store_true", help="do not execute code written by the models")

    sub.add_parser("calibration", help="merge the anchor runs into calibration/anchors.csv and write the case "
                                       "pruning report (calibration/pruning.md)")

    p = sub.add_parser("rescore", help="check the saved answers of a run again with the current cases and checker "
                                       "(no calls, no cost), into a new run folder next to it")
    p.add_argument("folder", help="the run folder, e.g. calibration/runs/<run id>")

    p = sub.add_parser("copy-run", help="copy a finished run into another episode that lists the same model, GGUF, "
                                        "sampling and seed on that machine (instead of running it again)")
    p.add_argument("folder", help="the run folder, e.g. episodes/<episode>/results/runs/<run id>")
    p.add_argument("--episode", required=True, help="the episode to copy it into")

    p = sub.add_parser("speed", help="llama-bench (pp and tg) at several context depths")
    p.add_argument("--episode", required=True)
    p.add_argument("--machine", required=True, choices=machines)
    p.add_argument("--model", help="model name; with --gguf measures only that one")
    p.add_argument("--gguf", help="GGUF path; without it, uses models.toml (gguf field + --models-dir)")
    p.add_argument("--models-dir", help="folder with the GGUF files (the path does not go to the CSV)")
    p.add_argument("--depths", default="0,16384")
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--label", default="speed")
    p.add_argument("--no-gpu-sampling", action="store_true", help="do not sample nvidia-smi")

    p = sub.add_parser("cost", help="episode 1: monthly cost of buying vs renting")
    p.add_argument("--prices")
    p.add_argument("--assumptions")
    p.add_argument("--reference", help="id of the rental used for the break-even")
    p.add_argument("--example", action="store_true", help="use the fictional values in prices.example.csv")
    p.add_argument("--out")

    p = sub.add_parser("verdict", help="merge an episode's publishable runs into scores and verdicts")
    p.add_argument("--episode", required=True)

    p = sub.add_parser("thinking", help="score x time per model, thinking level and battery (after verdict): "
                                        "results/thinking.csv and results/charts/thinking-<battery>.svg")
    p.add_argument("--episode", default="04-does-thinking-pay")

    sub.add_parser("cases", help="list the cases of each use-case battery")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "env":
            text = json.dumps(env.capture(
                a.machine, a.url,
                server_host=os.environ.get("AIBENCH_SERVER_HOST"),
                models=a.models.split(",") if a.models else ()), ensure_ascii=False, indent=2)
            if a.out:
                Path(a.out).write_text(text + "\n", encoding="utf-8")
            print(text)
        elif a.cmd == "run":
            models = a.models.split(",") if a.models else \
                [m["name"] for m in episode_models(a.episode, a.machine, a.group)]
            use_cases = set(a.use_cases.split(",")) if a.use_cases else None
            if use_cases and use_cases - set(cases.USE_CASES):
                raise ValueError(f"unknown use case(s): {','.join(sorted(use_cases - set(cases.USE_CASES)))}")
            dest = run.run(a.episode, a.machine, models, a.runs, a.url, use_cases, a.judge, a.context_words, a.label,
                           a.simulate, a.smoke, a.skip_code, a.max_tokens, a.out, judge_url=a.judge_url,
                           sampling=model_sampling(a.episode, models), server_args=a.server_args,
                           stream=not a.no_stream, gpu_sampling=not a.no_gpu_sampling,
                           thinking=a.thinking if a.thinking is not None else episode_thinking(a.episode, models))
            print(f"run written to {_rel(dest)}")
            print((dest / "verdicts.md").read_text(encoding="utf-8"))
        elif a.cmd == "calibrate":
            table = {x["name"]: x for x in calibration.anchors()}
            names = a.models.split(",") if a.models else list(table)
            if unknown := [n for n in names if n not in table]:
                raise ValueError(f"not in anchors.toml: {', '.join(unknown)}")
            use_cases = set(a.use_cases.split(",")) if a.use_cases else None
            info = {}
            if not a.simulate:
                try:
                    info = client.models_info(names, url=a.url or client.OPENROUTER,
                                              key=os.environ.get("OPENROUTER_API_KEY"))
                except client.ClientError as e:
                    print(f"warning: prices not recorded ({e})", file=sys.stderr)
            dest = run.run(None, "openrouter", names, a.runs, a.url, use_cases, None, a.context_words, a.label,
                           a.simulate, a.smoke, a.skip_code, a.max_tokens,
                           sampling={n: table[n].get("sampling") for n in names},
                           providers={n: table[n].get("provider") for n in names},
                           reasoning={n: table[n].get("reasoning") for n in names},
                           anchors={n: table[n]["role"] for n in names}, root=calibration.CALIBRATION,
                           model_info=info, case_ids=a.cases.split(",") if a.cases else None)
            print(f"run written to {_rel(dest)}")
            print((dest / "verdicts.md").read_text(encoding="utf-8"))
        elif a.cmd == "calibration":
            path, n, ref = calibration.consolidate(log=lambda m: print(m, file=sys.stderr))
            print(f"{n} anchor executions → {_rel(path)}")
            for (uc, battery), r in sorted(ref.items()):
                print(f"{uc:14} {battery}  best ceiling {r['ceiling']:.1f}% ({r['ceiling_model']}), "
                      f"floor {r['floor']:.1f}%")
            print((path.parent / "pruning.md").read_text(encoding="utf-8"))
        elif a.cmd == "rescore":
            dest = run.rescore(a.folder)
            print(f"rescored run written to {_rel(dest)}")
            print((dest / "verdicts.md").read_text(encoding="utf-8"))
        elif a.cmd == "copy-run":
            print(f"copied to {_rel(run.copy_run(a.folder, a.episode))}")
        elif a.cmd == "speed":
            if a.gguf:
                targets = [{"name": a.model or Path(a.gguf).stem, "path": a.gguf}]
            else:
                if not a.models_dir:
                    raise SystemExit("error: pass --gguf or --models-dir")
                targets = [{"name": m["name"], "path": str(Path(a.models_dir).expanduser() / m["gguf"])}
                           for m in episode_models(a.episode, a.machine) if m.get("gguf")
                           and (a.model is None or m["name"] == a.model)]
            if not targets:
                raise SystemExit("error: no model with a gguf in models.toml for this machine")
            depths = [int(x) for x in a.depths.split(",")]
            rows, start = [], datetime.now()
            for m in targets:
                print(f"measuring {m['name']}…", file=sys.stderr)
                sampler = gpu.Disabled("--no-gpu-sampling") if a.no_gpu_sampling else gpu.Sampler()
                rows += speed.measure(a.machine, m["name"], m["path"], depths, a.repetitions, sampler=sampler)
                print(f"  GPU sampling: {sampler.status}", file=sys.stderr)
            run_id = f"{start:%Y-%m-%d-%H%M}-{a.machine}-{a.label}"
            path = EPISODES / a.episode / "results" / "runs" / run_id / "speed.csv"
            run.write_csv(path, speed.COLUMNS, rows)
            (path.parent / "env.json").write_text(
                json.dumps(env.capture(a.machine), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            meta = {"run_id": run_id, "kind": "speed", "episode": a.episode, "machine": a.machine,
                    "models": [m["name"] for m in targets], "depths": depths, "repetitions": a.repetitions,
                    "start": start.isoformat(timespec="seconds"), "end": datetime.now().isoformat(timespec="seconds"),
                    "smoke": False, "simulated": False, "publishable": True}
            (path.parent / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
            print(f"written to {_rel(path)}")
        elif a.cmd == "cost":
            ep = EPISODES / COST_EPISODE
            prices = Path(a.prices) if a.prices else ep / ("prices.example.csv" if a.example else "prices.csv")
            assumptions = Path(a.assumptions) if a.assumptions else \
                ep / ("assumptions.example.csv" if a.example else "assumptions.csv")
            rows = cost.calculate(cost.read_prices(prices), cost.read_assumptions(assumptions), a.reference)
            out = Path(a.out) if a.out else ep / "results" / ("cost.EXAMPLE.csv" if a.example else "cost.csv")
            cost.write(out, rows)
            w = csv.DictWriter(sys.stdout, fieldnames=cost.COLUMNS)
            w.writeheader()
            w.writerows(rows)
            if a.example or any(r["data_status"] != "CONFIRMED" for r in rows):
                print("\nWARNING: some prices are not CONFIRMED: do not publish these numbers.", file=sys.stderr)
        elif a.cmd == "verdict":
            path, n, v = run.consolidate(a.episode, log=lambda m: print(m, file=sys.stderr))
            print(f"{n} publishable executions → {_rel(path)}")
            if v:
                print((path.parent / "verdicts.md").read_text(encoding="utf-8"))
        elif a.cmd == "thinking":
            for path in thinking.write(a.episode):
                print(f"wrote {_rel(path)}")
        elif a.cmd == "cases":
            for c in cases.load():
                print(f"{c['use_case']:14} {c['id']:24} {c['tier']:7} {c['kind']}")
    except (run.RunError, client.ClientError, cost.CostError, calibration.CalibrationError, FileNotFoundError,
            ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
