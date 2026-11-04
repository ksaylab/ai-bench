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


if __name__ == "__main__":
    unittest.main()
