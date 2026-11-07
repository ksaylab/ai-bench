import csv
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aibench import pairs, run, speed, verdict

TOML = """
[[model]]
name = "small1"
gguf = "s1.gguf"
pair = ["s-vs-l", "s-vs-xl"]
group = "small"
machines = ["pc-rtx2060"]
thinking = 2048

[[model]]
name = "large1"
gguf = "l1.gguf"
pair = "s-vs-l"
group = "large"
machines = ["pc-rtx2060"]
thinking = 2048

[[model]]
name = "xl1"
gguf = "xl1.gguf"
pair = "s-vs-xl"
group = "large"
machines = ["pc-rtx2060"]
thinking = 2048

[[model]]
name = "rented-s"
gguf = "rs.gguf"
pair = "rented"
group = "small"
machines = ["runpod"]

[[model]]
name = "rented-l"
gguf = "rl.gguf"
pair = "rented"
group = "large"
machines = ["runpod"]
"""


def score(model, uc, pct, v, cases=20, time_s=30.0, wh=1.0):
    return {"machine": "pc-rtx2060", "model": model, "use_case": uc, "score_pct": pct, "verdict": v,
            "cases": cases, "avg_time_s": time_s, "wh_per_run": wh, "tier_qualifier": ""}


class TestPairs(unittest.TestCase):
    """Episode 03: per pair of models on the same hardware, does the large one earn a Good for the small one does
    not, and how much slower and more costly is it?"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        p = mock.patch.object(run, "EPISODES", self.tmp / "episodes")
        p.start()
        self.addCleanup(p.stop)
        self.ep = self.tmp / "episodes" / "03-x"
        (self.ep / "results").mkdir(parents=True)
        (self.ep / "models.toml").write_text(TOML, encoding="utf-8")
        s, l, x = "small1@think-2048", "large1@think-2048", "xl1@think-2048"
        rows = [score(s, "coding", 50.0, "Not good for", time_s=6), score(l, "coding", 85.0, "Good for", time_s=30),
                score(s, "rag", 90.0, "Good for"), score(l, "rag", 92.0, "Good for"),
                score(s, "agent", 78.0, "Unstable"), score(l, "agent", 95.0, "Good for"),
                score(s, "chat_pt", 70.0, "Not good for"), score(l, "chat_pt", 60.0, "Not good for"),
                score(s, "coding_public", 80.0, "Reference only"),
                score(x, "coding", 90.0, "Good for", time_s=60, wh=4.0)]
        with open(self.ep / "results" / "scores.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=verdict.SCORE_COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        sp = [{"machine": "pc-rtx2060", "model": "small1", "metric": "tg", "depth": 0, "tok_s": 80.0, "status": "ok",
               "reason": "", "fit_target_mib": ""},
              {"machine": "pc-rtx2060", "model": "large1", "metric": "", "depth": "", "tok_s": "", "status": "error",
               "reason": "did not fit in memory", "fit_target_mib": ""},
              {"machine": "pc-rtx2060", "model": "large1", "metric": "tg", "depth": 0, "tok_s": 20.0, "status": "ok",
               "reason": "", "fit_target_mib": 1536}]
        with open(self.ep / "results" / "speed.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=speed.COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(sp)

    def rows(self):
        return {(r["pair"], r["use_case"]): r for r in pairs.table("03-x")}

    def test_each_battery_compares_the_two_sides(self):
        r = self.rows()[("s-vs-l", "coding")]
        self.assertEqual((r["small"], r["large"], r["machine"]), ("small1@think-2048", "large1@think-2048",
                                                                  "pc-rtx2060"))
        self.assertEqual((r["small_pct"], r["large_pct"], r["points"]), (50.0, 85.0, 35.0))
        self.assertEqual(r["outcome"], "only the large is Good for")
        self.assertEqual((r["small_minutes"], r["large_minutes"], r["time_ratio"]), (2.0, 10.0, 5.0))

    def test_outcomes(self):
        t = self.rows()
        self.assertEqual(t[("s-vs-l", "rag")]["outcome"], "both Good for")
        self.assertEqual(t[("s-vs-l", "agent")]["outcome"], "unsure (Unstable)")
        self.assertEqual(t[("s-vs-l", "chat_pt")]["outcome"], "neither Good for")
        self.assertNotIn(("s-vs-l", "coding_public"), t)  # reference only, as in the verdicts

    def test_a_model_can_be_in_two_pairs(self):
        r = self.rows()[("s-vs-xl", "coding")]
        self.assertEqual((r["small"], r["large"], r["points"]), ("small1@think-2048", "xl1@think-2048", 40.0))

    def test_a_battery_or_pair_not_run_yet_says_so(self):
        t = self.rows()
        self.assertEqual(t[("s-vs-xl", "rag")]["outcome"], "not run yet")
        self.assertEqual(t[("s-vs-xl", "rag")]["large_pct"], "")
        self.assertEqual(t[("rented", "coding")]["outcome"], "not run yet")
        self.assertEqual(t[("rented", "coding")]["machine"], "runpod")

    def test_a_pair_needs_one_small_and_one_large(self):
        (self.ep / "models.toml").write_text(TOML.replace('pair = "s-vs-l"\ngroup = "large"',
                                                          'pair = "s-vs-l"\ngroup = "small"'), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "s-vs-l"):
            pairs.table("03-x")

    def test_markdown_shows_each_pair_with_speed(self):
        md = pairs.markdown(pairs.table("03-x"), pairs.speeds("03-x"))
        self.assertIn("## s-vs-l: `small1@think-2048` vs `large1@think-2048` (pc-rtx2060)", md)
        self.assertIn("| Coding | 50% ❌ | 85% ✅ | +35 | only the large is Good for | 2.0 → 10.0 min (5.0×) |", md)
        self.assertIn("80.0 → 20.0 tok/s", md)  # generation at depth 0
        self.assertIn("does not fit on the GPU", md)  # the large one runs fitted, part on the CPU
        self.assertIn("## rented", md)
        self.assertIn("Not run yet.", md)

    def test_write_saves_csv_and_md(self):
        paths = pairs.write("03-x")
        self.assertEqual([p.name for p in paths], ["pairs.csv", "pairs.md"])
        with open(self.ep / "results" / "pairs.csv", encoding="utf-8") as f:
            self.assertEqual(next(csv.reader(f)), pairs.COLUMNS)

    def test_an_episode_without_pairs_writes_nothing(self):
        (self.ep / "models.toml").write_text('[[model]]\nname = "a"\nmachines = ["pc-rtx2060"]\n', encoding="utf-8")
        self.assertEqual(pairs.write("03-x"), [])


if __name__ == "__main__":
    unittest.main()
