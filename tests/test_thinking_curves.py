import csv
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from aibench import run, thinking

COLUMNS = ["run_id", "machine", "model", "use_case", "case", "tier", "rep", "seed", "passed", "reason", "time_s",
           "finish", "battery"]


def row(model, use_case, case, rep, passed, time_s, finish="stop"):
    return {"run_id": "r", "machine": "pc-rtx2060", "model": model, "use_case": use_case, "case": case,
            "tier": "easy", "rep": rep, "seed": 1000 + rep, "passed": passed, "reason": "", "time_s": time_s,
            "finish": finish, "battery": "b"}


class TestThinkingCurves(unittest.TestCase):
    """Episode 04's score x time per model, thinking level and battery, from the merged executions.csv."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        p = mock.patch.object(run, "EPISODES", self.tmp / "episodes")
        p.start()
        self.addCleanup(p.stop)
        self.results = self.tmp / "episodes" / "04-x" / "results"
        self.results.mkdir(parents=True)
        rows = []
        for rep in range(3):
            # off: coding 1 of 2 passes, 10 s per case; rag 2 of 2, 5 s
            rows += [row("m1@think-off", "coding", "c1", rep, 1, 10), row("m1@think-off", "coding", "c2", rep, 0, 10),
                     row("m1@think-off", "rag", "r1", rep, 1, 5), row("m1@think-off", "rag", "r2", rep, 1, 5)]
            # 512: coding passes all but c2 on rep 0, which hits max_tokens; 60 s per case
            rows += [row("m1@think-512", "coding", "c1", rep, 1, 60),
                     row("m1@think-512", "coding", "c2", rep, int(rep > 0), 60, "length" if rep == 0 else "stop"),
                     row("m1@think-512", "rag", "r1", rep, 1, 30), row("m1@think-512", "rag", "r2", rep, 1, 30),
                     row("m1@think-512", "coding_public", "p1", rep, 1, 600)]  # reference only: never in "all"
        rows.append(row("anchor-without-level", "coding", "c1", 0, 1, 1))  # not a thinking contestant: ignored
        with open(self.results / "executions.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)

    def table(self):
        return {(r["model"], r["level"], r["use_case"]): r for r in thinking.table("04-x")}

    def test_score_time_and_cuts_per_model_level_and_battery(self):
        t = self.table()
        off, b512 = t[("m1", "off", "coding")], t[("m1", "512", "coding")]
        self.assertEqual((off["cases"], off["runs"], off["executions"], off["passed"]), (2, 3, 6, 3))
        self.assertEqual(off["score_pct"], 50.0)
        self.assertEqual(off["minutes_per_run"], round(20 / 60, 2))  # 2 cases x 10 s per run
        self.assertEqual(b512["score_pct"], 83.3)
        self.assertEqual((b512["min_run_pct"], b512["max_run_pct"]), (50.0, 100.0))
        self.assertEqual(b512["length_cuts"], 1)
        self.assertEqual(b512["points_vs_off"], 33.3)
        self.assertEqual(b512["time_vs_off"], 6.0)
        self.assertEqual(off["points_vs_off"], 0.0)

    def test_all_pools_the_verdict_batteries_only(self):
        t = self.table()
        a = t[("m1", "512", "all")]
        self.assertEqual((a["cases"], a["executions"], a["passed"]), (4, 12, 11))  # coding_public left out
        self.assertEqual(a["score_pct"], 91.7)
        self.assertEqual(a["minutes_per_run"], round(180 / 60, 2))
        self.assertNotIn(("m1", "512", "coding_public"), t)
        self.assertFalse([k for k in t if k[0] == "anchor-without-level"])

    def test_levels_run_in_order(self):
        levels = [r["level"] for r in thinking.table("04-x") if r["use_case"] == "all"]
        self.assertEqual(levels, ["off", "512"])

    def test_write_saves_the_csv_and_one_chart_per_battery(self):
        paths = thinking.write("04-x")
        self.assertTrue((self.results / "thinking.csv").exists())
        self.assertTrue((self.results / "thinking-budget.csv").exists())
        md = (self.results / "thinking-budget.md").read_text()
        self.assertIn("| `m1` | 512 · 91.7% · 3.0 min |", md)  # all: 512 is 16.7 points over off
        self.assertIn("2 points", md)  # the rule is stated with the table
        charts = sorted(p.name for p in paths if p.suffix == ".svg")
        self.assertEqual(charts, ["thinking-all.svg", "thinking-coding.svg", "thinking-rag.svg"])
        svg = ET.parse(self.results / "charts" / "thinking-all.svg").getroot()  # well-formed XML
        ns = "{http://www.w3.org/2000/svg}"
        self.assertIn("m1", [t.text for t in svg.iter(f"{ns}text")])  # the direct label
        tips = [t.text for c in svg.iter(f"{ns}circle") for t in c.iter(f"{ns}title")]
        self.assertEqual(len(tips), 2)  # hover: every point names model, level, score and time
        self.assertIn("m1, thinking 512: 91.7%", tips[1])


def level_row(model, use_case, level, passed, minutes, executions=100):
    return {"model": model, "use_case": use_case, "level": level, "passed": passed, "executions": executions,
            "score_pct": round(100 * passed / executions, 1), "minutes_per_run": minutes}


class TestBudget(unittest.TestCase):
    """Rule A: per model and battery, the lowest thinking level that scores within 2 points of that model's best."""

    def budget(self, *rows):
        return {(b["model"], b["use_case"]): b for b in thinking.budget(list(rows))}

    def test_the_lowest_level_within_two_points_of_the_best(self):
        b = self.budget(level_row("m", "coding", "off", 50, 1), level_row("m", "coding", "512", 70, 2),
                        level_row("m", "coding", "2048", 79, 4), level_row("m", "coding", "8192", 80, 9))
        r = b[("m", "coding")]
        self.assertEqual((r["level"], r["score_pct"], r["minutes_per_run"]), ("2048", 79.0, 4))
        self.assertEqual((r["best_level"], r["best_score_pct"], r["best_minutes_per_run"]), ("8192", 80.0, 9))
        self.assertEqual(r["points_below_best"], 1.0)
        self.assertEqual(r["time_vs_best"], 0.44)

    def test_exactly_two_points_below_counts(self):
        b = self.budget(level_row("m", "rag", "off", 78, 1), level_row("m", "rag", "512", 80, 3))
        self.assertEqual(b[("m", "rag")]["level"], "off")

    def test_the_best_need_not_be_the_highest_level(self):
        b = self.budget(level_row("m", "agent", "off", 60, 1), level_row("m", "agent", "512", 90, 2),
                        level_row("m", "agent", "2048", 85, 5))
        r = b[("m", "agent")]
        self.assertEqual((r["level"], r["best_level"], r["points_below_best"]), ("512", "512", 0.0))

    def test_a_tie_for_best_takes_the_lowest_level(self):
        b = self.budget(level_row("m", "chat_pt", "2048", 90, 5), level_row("m", "chat_pt", "8192", 90, 9))
        self.assertEqual((b[("m", "chat_pt")]["level"], b[("m", "chat_pt")]["best_level"]), ("2048", "2048"))

    def test_scores_compare_unrounded(self):  # 2/3 of a point apart, not 0.7 after rounding twice
        b = self.budget(level_row("m", "coding", "off", 196, 1, executions=300),
                        level_row("m", "coding", "512", 202, 2, executions=300))
        self.assertEqual(b[("m", "coding")]["level"], "off")  # 65.33 vs 67.33: exactly 2.0 below
        b = self.budget(level_row("m", "coding", "off", 195, 1, executions=300),
                        level_row("m", "coding", "512", 202, 2, executions=300))
        self.assertEqual(b[("m", "coding")]["level"], "512")  # 65.0 vs 67.33: 2.33 below


if __name__ == "__main__":
    unittest.main()
