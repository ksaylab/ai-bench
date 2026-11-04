import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aibench import calibration, cases, run
from tests.test_run import QUIET


def rows(folder):
    with open(Path(folder) / "executions.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def lines(folder):
    return [json.loads(x) for x in (Path(folder) / "responses.jsonl").read_text(encoding="utf-8").splitlines()]


def meta(folder):
    return json.loads((Path(folder) / "meta.json").read_text(encoding="utf-8"))


class TestRescore(unittest.TestCase):
    """Rescore: the saved answers of a run checked again by the current cases and checker, with no new calls."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        p = mock.patch.object(calibration, "CALIBRATION", self.tmp / "calibration")
        p.start()
        self.addCleanup(p.stop)

    def source(self, use_cases=("agent", "chat_pt")):
        return run.run(None, "openrouter", ["ceil-a"], use_cases=set(use_cases), simulate=True,
                       anchors={"ceil-a": "ceiling"}, root=calibration.CALIBRATION, **QUIET)

    def test_a_run_records_what_it_sent_for_each_case(self):
        m = meta(self.source())
        self.assertEqual(set(m["requests"]), set(m["cases"]))
        c = next(c for c in cases.load(["agent", "chat_pt"]) if c["id"] == m["cases"][0])
        self.assertEqual(m["requests"][c["id"]], cases.request_hash(c))
        self.assertEqual(m["checker_version"], cases.CHECKER_VERSION)

    def test_a_new_checker_rescores_the_saved_answers(self):
        src = self.source()
        with mock.patch.object(cases, "CHECKER_VERSION", cases.CHECKER_VERSION + 1), \
                mock.patch.object(cases, "check", return_value=(False, "stricter rule")):
            dest = run.rescore(src, log=lambda *_: None)
            new_hashes = {uc: cases.battery_hash(uc) for uc in ("agent", "chat_pt")}
        self.assertNotEqual(dest, src)
        self.assertTrue(dest.name.startswith(src.name + "-rescored-"))
        m, old = meta(dest), meta(src)
        self.assertEqual(m["rescored_from"], old["run_id"])
        self.assertEqual(m["run_id"], dest.name)
        self.assertEqual(m["battery"], new_hashes)
        self.assertEqual(m["checker_version"], cases.CHECKER_VERSION + 1)
        self.assertEqual(m["anchors"], old["anchors"])
        new, before = rows(dest), rows(src)
        self.assertEqual(len(new), len(before))
        self.assertTrue(all(r["passed"] == "0" and r["reason"] == "stricter rule" for r in new))
        self.assertEqual({r["run_id"] for r in new}, {dest.name})
        # what the model did is kept as it was: time, tokens, cost, the raw answer
        for a, b in zip(new, before):
            self.assertEqual((a["case"], a["rep"], a["time_s"], a["cost_usd"], a["completion_tokens"]),
                             (b["case"], b["rep"], b["time_s"], b["cost_usd"], b["completion_tokens"]))
        self.assertEqual([x["text"] for x in lines(dest)], [x["text"] for x in lines(src)])
        self.assertTrue(all(x["passed"] == 0 for x in lines(dest)))
        self.assertTrue((dest / "verdicts.md").exists())

    def test_a_new_tier_is_taken_from_the_current_case(self):
        src = self.source(("agent",))
        first = meta(src)["cases"][0]
        real = cases.load

        def retagged(*a, **k):
            return [{**c, "tier": "hard"} if c["id"] == first else c for c in real(*a, **k)]
        with mock.patch.object(cases, "load", retagged), \
                mock.patch.object(cases, "CHECKER_VERSION", cases.CHECKER_VERSION + 1):
            dest = run.rescore(src, log=lambda *_: None)
        self.assertEqual({r["tier"] for r in rows(dest) if r["case"] == first}, {"hard"})

    def test_a_changed_prompt_is_refused(self):
        src = self.source(("agent",))
        m = meta(src)
        m["requests"][m["cases"][1]] = "sent something else"
        (src / "meta.json").write_text(json.dumps(m), encoding="utf-8")
        with mock.patch.object(cases, "CHECKER_VERSION", cases.CHECKER_VERSION + 1), \
                self.assertRaisesRegex(run.RunError, m["cases"][1]):
            run.rescore(src, log=lambda *_: None)

    def test_a_run_without_request_hashes_is_refused(self):
        src = self.source(("agent",))
        m = meta(src)
        del m["requests"]
        (src / "meta.json").write_text(json.dumps(m), encoding="utf-8")
        with mock.patch.object(cases, "CHECKER_VERSION", cases.CHECKER_VERSION + 1), \
                self.assertRaisesRegex(run.RunError, "request"):
            run.rescore(src, log=lambda *_: None)

    def test_only_the_use_cases_whose_version_changed_are_rescored(self):
        # a use case on the same version would be merged twice with the source run
        src = self.source()
        real = cases.battery_hash
        with mock.patch.object(cases, "battery_hash",
                               lambda uc, *a, **k: real(uc, *a, **k) + ("x" if uc == "agent" else "")):
            dest = run.rescore(src, log=lambda *_: None)
        self.assertEqual({r["use_case"] for r in rows(dest)}, {"agent"})
        self.assertEqual(set(meta(dest)["battery"]), {"agent"})
        self.assertEqual({x["use_case"] for x in lines(dest)}, {"agent"})

    def test_nothing_to_rescore_is_refused(self):
        src = self.source(("agent",))
        with self.assertRaisesRegex(run.RunError, "same battery version"):
            run.rescore(src, log=lambda *_: None)

    def test_a_judged_run_is_refused(self):
        src = self.source(("agent",))
        m = meta(src)
        m["judge"] = "some/judge"
        (src / "meta.json").write_text(json.dumps(m), encoding="utf-8")
        with mock.patch.object(cases, "CHECKER_VERSION", cases.CHECKER_VERSION + 1), \
                self.assertRaisesRegex(run.RunError, "judge"):
            run.rescore(src, log=lambda *_: None)

    def test_request_hashes_are_added_only_while_the_batteries_are_unchanged(self):
        # for a run made before runs recorded them: only safe while its battery files are the ones it ran
        src = self.source(("agent",))
        m = meta(src)
        recorded = m.pop("requests")
        (src / "meta.json").write_text(json.dumps(m), encoding="utf-8")
        run.record_requests(src)
        self.assertEqual(meta(src)["requests"], recorded)
        m = meta(src)
        del m["requests"]
        (src / "meta.json").write_text(json.dumps(m), encoding="utf-8")
        with mock.patch.object(cases, "CHECKER_VERSION", cases.CHECKER_VERSION + 1), \
                self.assertRaisesRegex(run.RunError, "battery"):
            run.record_requests(src)

    def test_the_cli_rescores_a_folder(self):
        from aibench import __main__ as cli
        src = self.source(("agent",))
        with mock.patch.object(cases, "CHECKER_VERSION", cases.CHECKER_VERSION + 1), \
                mock.patch("sys.stdout"):
            cli.main(["rescore", str(src)])
        self.assertEqual(len(list(src.parent.glob(src.name + "-rescored-*"))), 1)


def fake_run(folder, run_id, battery, rows, **extra):
    """A publishable run folder written by hand: meta.json and executions.csv."""
    d = Path(folder) / run_id
    d.mkdir(parents=True)
    meta = {"run_id": run_id, "machine": extra.pop("machine", "openrouter"), "publishable": True, "smoke": False,
            "simulated": False, "battery": battery, "use_cases": sorted(battery), **extra}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    run.write_csv(d / "executions.csv", run.COLUMNS,
                  [{"run_id": run_id, "machine": meta["machine"], "model": m, "use_case": uc, "case": f"{uc}-1",
                    "tier": "easy", "rep": rep, "passed": p, "battery": battery[uc]}
                   for m, uc, rep, p in rows])
    return d


class TestRescoredRunReplacesItsSource(unittest.TestCase):
    """A rescored run stands in for its source on the use cases it rescored; the source keeps the others."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_anchor_rows(self):
        runs = self.tmp / "runs"
        anchors = {"ceil-a": {"role": "ceiling"}}
        fake_run(runs, "r1", {"rag": "old", "coding": "same"},
                 [("ceil-a", "rag", 0, 0), ("ceil-a", "coding", 0, 1)], anchors=anchors)
        fake_run(runs, "r1-rescored-20261104-1300", {"rag": "new"}, [("ceil-a", "rag", 0, 1)],
                 anchors=anchors, rescored_from="r1")
        got = {(r["run_id"], r["use_case"], r["battery"]) for r in calibration.read_rows(self.tmp)}
        self.assertEqual(got, {("r1", "coding", "same"), ("r1-rescored-20261104-1300", "rag", "new")})

    def test_episode_rows(self):
        results = self.tmp / "episodes" / "99-test" / "results"
        fake_run(results / "runs", "r1", {"rag": "old"}, [("m1", "rag", 0, 0)], machine="pc-rtx2060")
        fake_run(results / "runs", "r1-rescored-20261104-1300", {"rag": "new"}, [("m1", "rag", 0, 1)],
                 machine="pc-rtx2060", rescored_from="r1")
        with mock.patch.object(run, "EPISODES", self.tmp / "episodes"), \
                mock.patch.object(calibration, "CALIBRATION", self.tmp / "calibration"):
            run.consolidate("99-test")  # mixing both battery versions would raise
        merged = rows(results)
        self.assertEqual({(r["run_id"], r["battery"]) for r in merged}, {("r1-rescored-20261104-1300", "new")})


if __name__ == "__main__":
    unittest.main()
