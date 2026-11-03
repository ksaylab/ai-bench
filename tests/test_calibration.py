import csv
import json
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from aibench import calibration, client, run, verdict
from tests.test_run import QUIET, FakeServer, pinned, read

ANCHORS = {"ceil-a": "ceiling", "ceil-b": "ceiling", "floor-x": "floor"}
PINNED = {"order": ["host/fp8"], "allow_fallbacks": False, "require_parameters": True}


class TestRelativeScores(unittest.TestCase):
    def test_pct_of_ceiling_and_normalized(self):
        ref = {"ceiling": 95.0, "floor": 35.0}
        self.assertEqual(verdict.relative(65.0, ref), (95.0, 35.0, 68.4, 50.0, 1))
        self.assertEqual(verdict.relative(35.0, ref)[3], 0.0)
        self.assertEqual(verdict.relative(95.0, ref)[3], 100.0)
        self.assertEqual(verdict.relative(20.0, ref)[3], -25.0)  # below the floor: not clamped
        self.assertEqual(verdict.relative(50.0, None), ("", "", "", "", ""))
        self.assertEqual(verdict.relative(50.0, {"ceiling": 60.0, "floor": 60.0})[3], "")

    def test_reference_uses_the_best_ceiling_and_the_floor(self):
        rows = [{"use_case": "coding", "battery": "b1", "model": "a", "role": "ceiling", "score_pct": 90.0},
                {"use_case": "coding", "battery": "b1", "model": "b", "role": "ceiling", "score_pct": 96.0},
                {"use_case": "coding", "battery": "b1", "model": "f", "role": "floor", "score_pct": 30.0},
                {"use_case": "rag", "battery": "b2", "model": "a", "role": "ceiling", "score_pct": 99.0}]
        ref = calibration.reference(rows)
        self.assertEqual(ref, {("coding", "b1"): {"ceiling": 96.0, "ceiling_model": "b", "floor": 30.0}})

    def test_not_calibrated_battery_has_no_verdict(self):
        rows = [{"run_id": "r", "machine": "m", "model": "x", "use_case": "coding", "case": f"c{i}", "rep": rep,
                 "passed": 1, "reason": "", "time_s": 1, "tok_s": 1, "cost_usd": "", "battery": "b1"}
                for rep in range(3) for i in range(5)]
        s = verdict.scores(rows, {("coding", "b1"): {"ceiling": 100.0, "floor": 60.0}})[0]
        self.assertEqual((s["verdict"], s["calibrated"]), ("Not calibrated", 0))
        s = verdict.scores(rows, {("coding", "b1"): {"ceiling": 100.0, "floor": 20.0}})[0]
        self.assertEqual((s["verdict"], s["calibrated"], s["normalized"]), ("Good for", 1, 100.0))
        s = verdict.scores(rows, {("coding", "other"): {"ceiling": 100.0, "floor": 20.0}})[0]
        self.assertEqual((s["pct_of_ceiling"], s["calibrated"]), ("", ""))  # other battery version: no reference


class TestTiersAndPruning(unittest.TestCase):
    def rows(self, results):
        """results: {(model, role): {case: [passed per repeat]}}"""
        out = []
        for (model, role), by_case in results.items():
            for case, reps in by_case.items():
                for rep, p in enumerate(reps):
                    out.append({"run_id": "r", "machine": "openrouter", "model": model, "role": role,
                                "use_case": "coding", "case": case, "tier": "easy", "rep": rep, "passed": p,
                                "battery": "b1"})
        return out

    def test_discrimination_check(self):
        rows = self.rows({
            ("c1", "ceiling"): {"easy": [1, 1, 1], "broken": [0, 0, 0], "split": [1, 1, 1], "good": [1, 1, 0]},
            ("c2", "ceiling"): {"easy": [1, 1, 1], "broken": [0, 0, 0], "split": [0, 0, 0], "good": [1, 1, 1]},
            ("f", "floor"): {"easy": [1, 1, 1], "broken": [0, 0, 0], "split": [0, 0, 0], "good": [0, 1, 0]}})
        battery = [{"use_case": "coding", "id": i, "tier": "easy"} for i in ("easy", "broken", "split", "good")]
        per_case, summary = calibration.pruning(rows, battery)
        actions = {r["case"]: r["action"] for r in per_case}
        self.assertEqual(actions, {"easy": "too_easy", "broken": "suspect", "split": "ceilings_disagree",
                                   "good": "keep"})
        self.assertEqual((summary["coding"]["kept"], summary["coding"]["too_easy"]), (2, 1))
        self.assertIn("add 13 to 18", summary["coding"]["advice"])
        md = calibration.pruning_markdown(per_case, summary)
        self.assertIn("`broken`", md)
        self.assertNotIn("`good`", md)

    def test_only_anchor_results_decide(self):
        self.assertEqual(calibration.classify({"local": ("", 3, 3)})[0], "")

    def test_scores_per_tier_and_the_tier_qualifier(self):
        rows = []
        for rep in range(3):
            for i, tier in enumerate(["easy"] * 6 + ["medium"] * 3 + ["hard"] * 1):
                rows.append({"run_id": "r", "machine": "m", "model": "x", "use_case": "coding", "case": f"c{i}",
                             "tier": tier, "rep": rep, "passed": int(tier != "hard" and not (tier == "medium" and
                                                                                             i == 6)),
                             "reason": "", "time_s": 1, "tok_s": 1, "cost_usd": ""})
        s = verdict.scores(rows)[0]
        self.assertEqual((s["easy_pct"], s["medium_pct"], s["hard_pct"]), (100.0, 66.7, 0.0))
        self.assertEqual((s["score_pct"], s["verdict"], s["tier_qualifier"]), (80.0, "Good for", "easy only"))
        self.assertEqual(verdict.verdicts([s])[0]["good_for"], "Coding (easy only) (borderline)")
        self.assertEqual(verdict.tier_qualifier({"easy": 100.0, "medium": 90.0, "hard": 50.0}, 80), "easy and medium")
        self.assertEqual(verdict.tier_qualifier({"easy": 100.0, "medium": 90.0}, 80), "")


class Models(BaseHTTPRequestHandler):
    def do_GET(self):
        data = json.dumps({"data": [{"id": "ceil-a", "pricing": {"prompt": "0.0000016", "completion": "0.0000032"},
                                     "supported_parameters": ["tools", "seed", "temperature"]}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


class TestAnchorRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "episodes" / "99-test" / "results").mkdir(parents=True)
        for target, value in ((run, "EPISODES"), (calibration, "CALIBRATION")):
            p = mock.patch.object(target, value, self.tmp / value.lower())
            p.start()
            self.addCleanup(p.stop)
        FakeServer.requests.clear()
        FakeServer.bad_models = set()

    def serve(self, handler):
        srv = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_port}/v1"

    def test_anchors_toml_has_two_ceilings_and_the_floor(self):
        a = {x["name"]: x for x in calibration.anchors()}
        self.assertEqual({n: x["role"] for n, x in a.items()},
                         {"deepseek/deepseek-v4-pro": "ceiling", "z-ai/glm-5.3-flash": "ceiling",
                          "mistralai/ministral-3b-2512": "floor"})
        run.check_sampling(list(a), {n: x["sampling"] for n, x in a.items()})
        run.check_provider(list(a), {n: x.get("provider") for n, x in a.items()})
        run.check_reasoning(list(a), {n: x.get("reasoning") for n, x in a.items()})
        self.assertEqual({n: (x.get("reasoning") or {}).get("effort") for n, x in a.items()},
                         {"deepseek/deepseek-v4-pro": "high", "z-ai/glm-5.3-flash": "max",
                          "mistralai/ministral-3b-2512": None})  # the floor's only endpoint has no reasoning

    def test_prices_come_from_the_public_model_list(self):
        info = client.models_info(["ceil-a", "gone"], url=self.serve(Models))
        self.assertEqual(info["ceil-a"]["usd_per_1m_input"], 1.6)
        self.assertEqual(info["ceil-a"]["usd_per_1m_output"], 3.2)
        self.assertIn("error", info["gone"])

    def test_an_anchor_run_pins_one_provider_and_records_who_answered(self):
        url = self.serve(FakeServer)
        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-token"}), \
                mock.patch.object(run.env, "capture", return_value={}):
            d = run.run(None, "openrouter", ["ceil-a"], url=url, use_cases={"agent"}, sampling=pinned("ceil-a"),
                        providers={"ceil-a": PINNED}, anchors={"ceil-a": "ceiling"}, root=calibration.CALIBRATION,
                        **QUIET)
        self.assertTrue(FakeServer.requests)
        self.assertTrue(all(p["provider"] == PINNED for p in FakeServer.requests))
        meta = json.loads((d / "meta.json").read_text())
        self.assertEqual(meta["anchors"]["ceil-a"]["provider"], PINNED)
        lines = [json.loads(line) for line in (d / "responses.jsonl").read_text().splitlines()]
        self.assertEqual({line["provider"] for line in lines}, {"FakeHost"})

    def test_an_anchor_run_pins_the_reasoning_effort_only_where_it_is_set(self):
        url = self.serve(FakeServer)
        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-token"}), \
                mock.patch.object(run.env, "capture", return_value={}):
            d = run.run(None, "openrouter", ["ceil-a", "floor-x"], url=url, use_cases={"agent"},
                        sampling=pinned("ceil-a", "floor-x"), providers={"ceil-a": PINNED, "floor-x": PINNED},
                        reasoning={"ceil-a": {"effort": "max"}}, anchors={"ceil-a": "ceiling", "floor-x": "floor"},
                        root=calibration.CALIBRATION, **QUIET)
        sent = {(p["model"], json.dumps(p["reasoning"])) for p in FakeServer.requests}
        self.assertEqual(sent, {("ceil-a", '{"effort": "max"}'), ("floor-x", "null")})
        self.assertTrue(all(p["provider"] == PINNED for p in FakeServer.requests))
        meta = json.loads((d / "meta.json").read_text())
        self.assertEqual(meta["anchors"]["ceil-a"]["reasoning"], {"effort": "max"})
        self.assertNotIn("reasoning", meta["anchors"]["floor-x"])

    def test_unknown_reasoning_keys_are_refused(self):
        with self.assertRaises(run.RunError):
            run.run(None, "openrouter", ["ceil-a"], use_cases={"coding"}, simulate=True,
                    reasoning={"ceil-a": {"effort": "max", "efort": "high"}}, anchors={"ceil-a": "ceiling"},
                    root=calibration.CALIBRATION, **QUIET)

    def test_an_anchor_run_without_one_pinned_provider_needs_smoke(self):
        loose = (None, {"order": ["host/fp8"]}, {**PINNED, "order": []}, {**PINNED, "allow_fallbacks": True},
                 {**PINNED, "require_parameters": False}, {**PINNED, "note": "sent to OpenRouter as is"})
        for provider in loose:
            with self.subTest(provider=provider), self.assertRaises(run.RunError):
                run.run(None, "openrouter", ["ceil-a"], url="http://127.0.0.1:9/v1", sampling=pinned("ceil-a"),
                        providers={"ceil-a": provider}, anchors={"ceil-a": "ceiling"}, root=calibration.CALIBRATION,
                        **QUIET)
        run.run(None, "openrouter", ["ceil-a"], use_cases={"coding"}, simulate=True, anchors={"ceil-a": "ceiling"},
                root=calibration.CALIBRATION, **QUIET)

    def test_the_judge_cannot_be_an_anchor(self):
        with self.assertRaises(run.RunError):
            run.run("99-test", "pc-rtx2060", ["m1"], judge_model="z-ai/glm-5.3-flash", simulate=True, **QUIET)

    def test_anchor_run_then_episode_scores_relative_to_the_anchors(self):
        url = self.serve(FakeServer)
        FakeServer.bad_models = {"floor-x", "weak"}
        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-token"}), \
                mock.patch.object(run.env, "capture", return_value={}):
            d = run.run(None, "openrouter", list(ANCHORS), url=url, use_cases={"coding", "agent"},
                        sampling=pinned(*ANCHORS), providers={n: PINNED for n in ANCHORS}, anchors=ANCHORS,
                        root=calibration.CALIBRATION, label="anchors",
                        model_info={"ceil-a": {"usd_per_1m_input": 1.6}}, **QUIET)
        meta = json.loads((d / "meta.json").read_text())
        self.assertEqual(meta["anchors"]["ceil-a"], {"role": "ceiling", "usd_per_1m_input": 1.6, "provider": PINNED})
        self.assertEqual(meta["anchors"]["floor-x"]["role"], "floor")
        self.assertTrue(all(p["auth"] == "Bearer test-token" for p in FakeServer.requests))
        self.assertNotIn("test-token", json.dumps(meta) + (d / "executions.csv").read_text())
        path, n, ref = calibration.consolidate()
        self.assertEqual(n, len(read(d / "executions.csv")))
        self.assertEqual({k[0]: (v["ceiling"], v["floor"]) for k, v in ref.items()},
                         {"coding": (100.0, 0.0), "agent": (100.0, 0.0)})
        self.assertEqual({r["role"] for r in read(path)}, {"ceiling", "floor"})
        # an episode run on the same battery version gets the relative columns; anchors never appear there
        with mock.patch.object(run.env, "capture", return_value={}):
            e = run.run("99-test", "pc-rtx2060", ["good", "weak"], url=url, use_cases={"coding", "agent"},
                        sampling=pinned("good", "weak"), **QUIET)
        s = {(r["model"], r["use_case"]): r for r in read(e / "scores.csv")}
        self.assertEqual((s["good", "coding"]["pct_of_ceiling"], s["good", "coding"]["normalized"]), ("100.0", "100.0"))
        self.assertEqual((s["weak", "agent"]["pct_of_ceiling"], s["weak", "agent"]["normalized"]), ("0.0", "0.0"))
        self.assertEqual(s["good", "coding"]["calibrated"], "1")
        _, merged, _ = run.consolidate("99-test")
        self.assertEqual({r["model"] for r in read(run.EPISODES / "99-test" / "results" / "scores.csv")},
                         {"good", "weak"})
        self.assertTrue(merged)

    def test_runs_of_different_battery_versions_are_not_merged(self):
        url = self.serve(FakeServer)
        with mock.patch.object(run.env, "capture", return_value={}):
            d = run.run("99-test", "pc-rtx2060", ["m1"], url=url, use_cases={"agent"}, sampling=pinned("m1"),
                        **QUIET)
        other = d.parent / (d.name + "-b")
        shutil.copytree(d, other)
        rows = read(other / "executions.csv")
        for r in rows:
            r["battery"] = "000000000000"
        run.write_csv(other / "executions.csv", run.COLUMNS, rows)
        with self.assertRaises(run.RunError):
            run.consolidate("99-test")


if __name__ == "__main__":
    unittest.main()
