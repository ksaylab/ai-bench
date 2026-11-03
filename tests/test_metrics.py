import csv
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aibench import __main__ as cli
from aibench import gpu, run
from tests import test_run
from tests.test_run import QUIET, FakeServer, pinned, read
from tests.test_speed import OUTPUT

# a fake nvidia-smi: GPU 0 at 3000 then 5000 MiB, 100 W then 150 W, plus a second GPU that must be ignored
FAKE_SMI = """#!/bin/sh
i=0
while true; do
  if [ $i -lt 3 ]; then echo "0, 3000, 100.0"; else echo "0, 5000, 150.0"; fi
  echo "1, 9999, 999.0"
  i=$((i+1))
  sleep 0.05
done
"""


def executable(folder, name, script):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


class TestGpuSampler(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_samples_peak_vram_and_power_of_gpu_0(self):
        smi = executable(self.tmp, "nvidia-smi", FAKE_SMI)
        s = gpu.Sampler(command=[str(smi)], interval_ms=50).start()
        t0 = gpu.time.monotonic()
        gpu.time.sleep(0.6)
        w = s.window(t0, gpu.time.monotonic())
        s.stop()
        self.assertEqual(s.status, "ok")
        self.assertEqual(w["peak_vram_mib"], 5000)
        self.assertTrue(100 <= w["avg_power_w"] <= 150)
        self.assertGreater(w["energy_wh"], 0)
        summary = s.summary()
        self.assertEqual((summary["peak_vram_mib"], summary["peak_power_w"]), (5000, 150.0))

    def test_without_nvidia_smi_it_degrades_to_empty_columns(self):
        s = gpu.Sampler(command=[str(self.tmp / "no-such-nvidia-smi")]).start()
        self.assertTrue(s.status.startswith("unavailable"))
        self.assertEqual(s.window(0, 1), gpu.EMPTY)
        self.assertEqual(s.stop().summary()["status"], s.status)

    def test_a_failing_nvidia_smi_gives_no_samples(self):
        smi = executable(self.tmp, "nvidia-smi", "#!/bin/sh\necho 'NVIDIA-SMI has failed' >&2\nexit 9\n")
        s = gpu.Sampler(command=[str(smi)]).start()
        gpu.time.sleep(0.2)
        self.assertTrue(s.stop().status.startswith("unavailable"))

    def test_remote_server_is_sampled_over_ssh(self):
        s = gpu.Sampler(server_host="gpu-box")
        self.assertEqual(s.command[:3], ["ssh", "-o", "BatchMode=yes"])
        self.assertIn("nvidia-smi --query-gpu=index,memory.used,power.draw", s.command[-1])
        f = run.sampler_factory("pc-rtx2060", "http://gpu-box.invalid/v1", env_vars={})
        self.assertIsInstance(f(), gpu.Disabled)  # remote and no AIBENCH_SERVER_HOST: not this machine's GPU
        f = run.sampler_factory("openrouter", "https://openrouter.ai/api/v1", env_vars={})
        self.assertIn("cloud", f().status)


class TestRunMetrics(unittest.TestCase):
    """TTFT and GPU columns in a run against the fake llama-server (with the TestRun fixtures)."""
    setUp = test_run.TestRun.setUp
    server = test_run.TestRun.server

    def test_streaming_measures_time_to_first_token_and_samples_the_gpu(self):
        url = self.server()
        bindir = self.tmp / "bin"
        executable(bindir, "nvidia-smi", FAKE_SMI)
        with mock.patch.object(run.env, "capture", return_value={}), \
                mock.patch.dict(os.environ, {"PATH": f"{bindir}:{os.environ['PATH']}"}):
            d = run.run("99-test", "pc-rtx2060", ["m1"], url=url, use_cases={"agent"}, sampling=pinned("m1"),
                        **QUIET)
        self.assertGreater(FakeServer.streamed, 0)
        rows = read(d / "executions.csv")
        self.assertTrue(all(r["passed"] == "1" for r in rows), [(r["case"], r["reason"]) for r in rows])
        self.assertTrue(all(r["ttft_s"] != "" for r in rows))
        self.assertTrue(all(r["peak_vram_mib"] in ("3000", "5000") for r in rows), [r["peak_vram_mib"] for r in rows])
        meta = json.loads((d / "meta.json").read_text())
        self.assertEqual(meta["gpu_sampling"]["m1"]["status"], "ok")
        self.assertTrue(meta["stream"])
        s = read(d / "scores.csv")[0]
        for col in ("avg_ttft_s", "peak_vram_mib", "avg_power_w", "wh_per_run"):
            self.assertNotEqual(s[col], "", col)

    def test_without_streaming_ttft_comes_from_the_server_timings_and_no_gpu_is_fine(self):
        url = self.server()
        with mock.patch.object(run.env, "capture", return_value={}), \
                mock.patch.object(gpu.shutil, "which", return_value=None):
            d = run.run("99-test", "pc-rtx2060", ["m1"], url=url, use_cases={"coding"}, sampling=pinned("m1"),
                        stream=False, **QUIET)
        self.assertEqual(FakeServer.streamed, 0)
        rows = read(d / "executions.csv")
        self.assertEqual({r["ttft_s"] for r in rows}, {"0.012"})
        self.assertEqual({r["peak_vram_mib"] for r in rows}, {""})
        meta = json.loads((d / "meta.json").read_text())
        self.assertTrue(meta["gpu_sampling"]["m1"]["status"].startswith("unavailable"))
        self.assertEqual(read(d / "scores.csv")[0]["peak_vram_mib"], "")


class TestSpeedIntoResults(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        ep = self.tmp / "episodes" / "99-test"
        ep.mkdir(parents=True)
        (ep / "models.toml").write_text('[[model]]\nname = "m"\ngguf = "M-Q4.gguf"\nmachines = ["pc-rtx2060"]\n')
        (self.tmp / "models").mkdir()
        (self.tmp / "models" / "M-Q4.gguf").write_bytes(b"0" * 1024)
        for target in (run, cli):
            p = mock.patch.object(target, "EPISODES", self.tmp / "episodes")
            p.start()
            self.addCleanup(p.stop)

    def test_speed_run_is_merged_into_results_speed_csv(self):
        bindir = self.tmp / "bin"
        (self.tmp / "out.json").write_text(json.dumps(OUTPUT))
        executable(bindir, "llama-bench", f"#!/bin/sh\nsleep 0.3\ncat {self.tmp / 'out.json'}\n")
        executable(bindir, "nvidia-smi", FAKE_SMI)
        with mock.patch.dict(os.environ, {"PATH": f"{bindir}:{os.environ['PATH']}"}), \
                mock.patch.object(cli.env, "capture", return_value={}), \
                mock.patch("sys.stderr"), mock.patch("sys.stdout"):
            self.assertEqual(cli.main(["speed", "--episode", "99-test", "--machine", "pc-rtx2060",
                                       "--models-dir", str(self.tmp / "models")]), 0)
            self.assertEqual(cli.main(["verdict", "--episode", "99-test"]), 0)
        with open(self.tmp / "episodes" / "99-test" / "results" / "speed.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([(r["metric"], r["tok_s"]) for r in rows], [("pp", "1000.46"), ("tg", "40.0")])
        self.assertTrue(all(r["peak_vram_mib"] in ("3000", "5000") for r in rows))
        meta = json.loads(next((self.tmp / "episodes").glob("99-test/results/runs/*/meta.json")).read_text())
        self.assertEqual((meta["kind"], meta["publishable"]), ("speed", True))


if __name__ == "__main__":
    unittest.main()
