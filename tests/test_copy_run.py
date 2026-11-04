import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aibench import run

SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0.0, "presence_penalty": 0.0}


def models_toml(path, entries):
    lines = []
    for e in entries:
        lines += ["[[model]]", f'name = "{e["name"]}"', f'gguf = "{e["gguf"]}"', f'group = "{e.get("group", "small")}"',
                  f'machines = {json.dumps(e.get("machines", ["pc-rtx2060"]))}', "", "[model.sampling]"]
        lines += [f"{k} = {json.dumps(v)}" for k, v in {**SAMPLING, **e.get("sampling", {})}.items()]
        lines += [f'seed = {e.get("seed", 1000)}', 'source = "card"', "verified = true", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


class TestCopyRun(unittest.TestCase):
    """A run of a model on one machine stands for another episode that lists the same model, GGUF and sampling."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        p = mock.patch.object(run, "EPISODES", self.tmp / "episodes")
        p.start()
        self.addCleanup(p.stop)
        entry = {"name": "m1", "gguf": "m1-Q4.gguf"}
        models_toml(self.tmp / "episodes" / "02-a" / "models.toml", [entry])
        models_toml(self.tmp / "episodes" / "03-b" / "models.toml", [{**entry, "group": "large"}])
        self.src = self.tmp / "episodes" / "02-a" / "results" / "runs" / "2026-11-04-1511-pc-rtx2060-m1"
        self.src.mkdir(parents=True)
        meta = {"run_id": self.src.name, "episode": "02-a", "machine": "pc-rtx2060", "models": ["m1"], "runs": 3,
                "publishable": True, "smoke": False, "simulated": False,
                "sampling": {"m1": {"sent": SAMPLING, "base_seed": 1000, "seeds": [1000, 1001, 1002]}}}
        (self.src / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (self.src / "env.json").write_text(json.dumps({"server": {"gguf": {"m1": "m1-Q4.gguf"}}}), encoding="utf-8")
        (self.src / "executions.csv").write_text("run_id,model\nx,m1\n", encoding="utf-8")

    def dest(self):
        return self.tmp / "episodes" / "03-b" / "results" / "runs" / self.src.name

    def test_the_same_setup_is_copied_and_says_where_from(self):
        d = run.copy_run(self.src, "03-b")
        self.assertEqual(d, self.dest())
        meta = json.loads((d / "meta.json").read_text())
        self.assertEqual(meta["episode"], "03-b")
        self.assertEqual(meta["copied_from"], {"episode": "02-a", "run_id": self.src.name})
        self.assertEqual((d / "executions.csv").read_text(), (self.src / "executions.csv").read_text())
        self.assertEqual(json.loads((self.src / "meta.json").read_text())["episode"], "02-a")  # source untouched

    def refused(self, match, entry=None, episode="03-b"):
        if entry is not None:
            models_toml(self.tmp / "episodes" / "03-b" / "models.toml", [entry])
        with self.assertRaisesRegex(run.RunError, match):
            run.copy_run(self.src, episode)
        self.assertFalse(self.dest().exists())

    def test_other_sampling_is_refused(self):
        self.refused("sampling", {"name": "m1", "gguf": "m1-Q4.gguf", "sampling": {"temperature": 0.6}})

    def test_another_seed_is_refused(self):
        self.refused("seed", {"name": "m1", "gguf": "m1-Q4.gguf", "seed": 2000})

    def test_another_gguf_is_refused(self):
        self.refused("GGUF", {"name": "m1", "gguf": "m1-Q8.gguf"})

    def test_a_model_the_episode_does_not_list_on_that_machine_is_refused(self):
        self.refused("m1", {"name": "m1", "gguf": "m1-Q4.gguf", "machines": ["runpod"]})
        self.refused("m1", {"name": "other", "gguf": "m1-Q4.gguf"})

    def test_an_unfinished_run_is_refused(self):
        (self.src / "meta.json").unlink()  # meta.json is written when the run ends
        self.refused("finished")

    def test_the_same_episode_or_an_unknown_one_is_refused(self):
        self.refused("same episode", episode="02-a")
        with self.assertRaisesRegex(run.RunError, "not found"):
            run.copy_run(self.src, "09-none")

    def test_an_existing_copy_is_not_overwritten(self):
        run.copy_run(self.src, "03-b")
        with self.assertRaisesRegex(run.RunError, "already"):
            run.copy_run(self.src, "03-b")

    def test_the_cli_copies(self):
        from aibench import __main__ as cli
        with mock.patch.object(cli, "EPISODES", self.tmp / "episodes"), mock.patch("sys.stdout"):
            cli.main(["copy-run", str(self.src), "--episode", "03-b"])
        self.assertTrue(self.dest().exists())


if __name__ == "__main__":
    unittest.main()
