import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aibench import speed

OUTPUT = [
    {"build_commit": "abc1234", "build_number": 9000, "gpu_info": "Test GPU", "model_size": 2 * 2**30,
     "n_prompt": 512, "n_gen": 0, "n_depth": 0, "avg_ts": 1000.456, "stddev_ts": 5.1, "samples_ts": [995, 1000, 1006]},
    {"build_commit": "abc1234", "build_number": 9000, "gpu_info": "Test GPU", "model_size": 2 * 2**30,
     "n_prompt": 0, "n_gen": 128, "n_depth": 16384, "avg_ts": 40.0, "stddev_ts": 0.4, "samples_ts": [39.6, 40, 40.4]},
]


class TestSpeed(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.gguf = self.tmp / "Model-Q4.gguf"
        self.gguf.write_bytes(b"0" * 1024)

    def fake(self, script):
        bindir = self.tmp / "bin"
        bindir.mkdir(exist_ok=True)
        path = bindir / "llama-bench"
        path.write_text("#!/bin/sh\n" + script)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return mock.patch.dict(os.environ, {"PATH": f"{bindir}:{os.environ['PATH']}"})

    def test_parse(self):
        rows = speed.parse(json.dumps(OUTPUT), "pc-rtx2060", "m", "/x/Model-Q4.gguf", 3)
        self.assertEqual([(r["metric"], r["depth"], r["tok_s"]) for r in rows], [("pp", 0, 1000.46), ("tg", 16384, 40.0)])
        self.assertEqual(rows[0]["gguf"], "Model-Q4.gguf")
        self.assertEqual(rows[0]["build"], "b9000-abc1234")

    def test_command_has_repetitions_and_depths(self):
        cmd = speed.command("m.gguf", [0, 16384], 3)
        self.assertEqual(cmd[cmd.index("-r") + 1], "3")
        self.assertEqual(cmd[cmd.index("-d") + 1], "0,16384")

    def test_measure_with_a_fake_llama_bench(self):
        (self.tmp / "out.json").write_text(json.dumps(OUTPUT))
        with self.fake(f"cat {self.tmp / 'out.json'}\n"):
            rows = speed.measure("mac-m5", "m", self.gguf, [0, 16384], 3)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["status"] == "ok" for r in rows))

    def test_out_of_memory_is_an_error_row_without_the_path(self):
        with self.fake(f"echo 'failed to allocate buffer for {self.gguf}' >&2\nexit 1\n"):
            rows = speed.measure("pc-rtx2060", "m", self.gguf, [0], 3)
        self.assertEqual((rows[0]["status"], rows[0]["reason"]), ("error", "did not fit in memory"))

    def test_fewer_than_3_repetitions_is_refused(self):
        with self.assertRaises(ValueError):
            speed.measure("pc-rtx2060", "m", self.gguf, [0], 2)


if __name__ == "__main__":
    unittest.main()
