import json
import shutil
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from unittest import mock

from aibench import run
from tests.test_run import QUIET, FakeServer, pinned, read


class TestThinking(unittest.TestCase):
    """--thinking off|<budget>: how much thinking improves the score and what it costs in time, per model."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "episodes" / "99-test" / "results").mkdir(parents=True)
        for target, value in ((run, "EPISODES"), (run.calibration, "CALIBRATION")):
            p = mock.patch.object(target, value, self.tmp / value.lower())
            p.start()
            self.addCleanup(p.stop)
        FakeServer.requests.clear()
        FakeServer.bad_models = set()
        srv = HTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        self.url = f"http://127.0.0.1:{srv.server_port}/v1"

    def run_with(self, thinking, models=("m1",)):
        with mock.patch.object(run.env, "capture", return_value={}):
            return run.run("99-test", "pc-rtx2060", list(models), url=self.url, use_cases={"agent"},
                           sampling=pinned(*models), thinking=thinking, **QUIET)

    def test_off_turns_thinking_off(self):
        d = self.run_with("off")
        self.assertTrue(FakeServer.requests)
        for p in FakeServer.requests:
            self.assertEqual(p["chat_template_kwargs"], {"enable_thinking": False})
            self.assertNotIn("reasoning_budget_tokens", p)
            self.assertEqual(p["max_tokens"], 32768)  # every level gets the same room
            self.assertEqual(p["model"], "m1")  # the server still gets the real model id
        meta = json.loads((d / "meta.json").read_text())
        self.assertEqual(meta["thinking"], "off")
        self.assertEqual(meta["max_tokens"], 32768)
        self.assertEqual({r["model"] for r in read(d / "executions.csv")}, {"m1@think-off"})

    def test_a_budget_caps_only_the_thinking(self):
        d = self.run_with(512)
        for p in FakeServer.requests:
            self.assertEqual(p["chat_template_kwargs"], {"enable_thinking": True})
            self.assertEqual(p["reasoning_budget_tokens"], 512)
            self.assertEqual(p["reasoning_budget_message"], run.BUDGET_MESSAGE)
            self.assertEqual(p["max_tokens"], 32768)
        self.assertEqual({r["model"] for r in read(d / "executions.csv")}, {"m1@think-512"})
        self.assertEqual([r["model"] for r in read(d / "verdicts.csv")], ["m1@think-512"])

    def test_unlimited_lifts_the_presets_budget(self):
        # the PC's presets end the thinking at 6144 or 8192 tokens; -1 is llama.cpp's "no limit"
        d = self.run_with("unlimited")
        for p in FakeServer.requests:
            self.assertEqual(p["chat_template_kwargs"], {"enable_thinking": True})
            self.assertEqual(p["reasoning_budget_tokens"], -1)
            self.assertNotIn("reasoning_budget_message", p)
        self.assertEqual({r["model"] for r in read(d / "executions.csv")}, {"m1@think-unlimited"})

    def test_each_level_is_its_own_contestant_when_runs_are_merged(self):
        for level in ("off", 512):
            with mock.patch.object(run.env, "capture", return_value={}):
                run.run("99-test", "pc-rtx2060", ["m1"], url=self.url, use_cases={"agent"}, sampling=pinned("m1"),
                        thinking=level, label=f"m1-think-{level}", **QUIET)
        run.consolidate("99-test")
        merged = read(self.tmp / "episodes" / "99-test" / "results" / "verdicts.csv")
        self.assertEqual(sorted(r["model"] for r in merged), ["m1@think-512", "m1@think-off"])

    def test_bad_levels_and_cloud_models_are_refused(self):
        for bad in ("high", "0", 0, -5, -1, "512x"):
            with self.subTest(bad=bad), self.assertRaises(run.RunError):
                self.run_with(bad)
        with self.assertRaisesRegex(run.RunError, "llama-server"):
            run.run(None, "openrouter", ["ceil-a"], use_cases={"agent"}, simulate=True, thinking="off",
                    anchors={"ceil-a": "ceiling"}, root=run.calibration.CALIBRATION, **QUIET)

    def test_the_cli_takes_the_level_and_sizes_max_tokens(self):
        from aibench import __main__ as cli
        with mock.patch.object(run.env, "capture", return_value={}), mock.patch("sys.stdout"), \
                mock.patch.object(cli, "model_sampling", return_value=pinned("m1")):
            cli.main(["run", "--episode", "99-test", "--machine", "pc-rtx2060", "--models", "m1", "--url", self.url,
                      "--use-cases", "agent", "--thinking", "2048", "--label", "m1-think-2048"])
        self.assertEqual({p["max_tokens"] for p in FakeServer.requests}, {32768})
        self.assertEqual({p["reasoning_budget_tokens"] for p in FakeServer.requests}, {2048})


class TestEpisodeThinking(unittest.TestCase):
    """An episode pins its thinking level per model (`thinking` in models.toml), as it pins the sampling: `run` sends
    it without --thinking, so a model run in the episode and a run copied from episode 04 have the same setup."""

    def setUp(self):
        from aibench import __main__ as cli
        from tests.test_copy_run import models_toml
        self.cli, self.models_toml = cli, models_toml
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        p = mock.patch.object(cli, "EPISODES", self.tmp / "episodes")
        p.start()
        self.addCleanup(p.stop)

    def toml(self, *entries):
        self.models_toml(self.tmp / "episodes" / "02-a" / "models.toml",
                         [{"gguf": f"{e['name']}.gguf", **e} for e in entries])

    def thinking_sent(self, *args):
        with mock.patch.object(self.cli.run, "run", return_value=self.tmp) as r, \
                mock.patch.object(Path, "read_text", return_value=""), mock.patch("sys.stdout"):
            code = self.cli.main(["run", "--episode", "02-a", "--machine", "pc-rtx2060", *args])
        return code, (r.call_args.kwargs["thinking"] if r.called else "not run")

    def test_the_episode_level_is_sent_without_the_flag(self):
        self.toml({"name": "m1", "thinking": 2048}, {"name": "m2", "thinking": 2048})
        self.assertEqual(self.thinking_sent(), (0, 2048))
        self.assertEqual(self.thinking_sent("--models", "m2"), (0, 2048))

    def test_no_level_in_the_episode_leaves_the_preset(self):
        self.toml({"name": "m1"})
        self.assertEqual(self.thinking_sent(), (0, None))

    def test_the_flag_wins(self):  # episode 04 runs every level of the same models
        self.toml({"name": "m1", "thinking": 2048})
        self.assertEqual(self.thinking_sent("--thinking", "off"), (0, "off"))

    def test_models_with_different_levels_are_run_apart(self):
        self.toml({"name": "m1", "thinking": 2048}, {"name": "m2", "thinking": "off"})
        with mock.patch("sys.stderr"):
            self.assertEqual(self.thinking_sent(), (1, "not run"))
            self.assertEqual(self.thinking_sent("--models", "m1"), (0, 2048))
        self.toml({"name": "m1", "thinking": 2048}, {"name": "m2"})
        with mock.patch("sys.stderr"):
            self.assertEqual(self.thinking_sent(), (1, "not run"))

    def test_a_bad_level_in_the_episode_is_refused(self):
        self.toml({"name": "m1", "thinking": "lots"})
        with mock.patch("sys.stderr"):
            self.assertEqual(self.thinking_sent(), (1, "not run"))


if __name__ == "__main__":
    unittest.main()
