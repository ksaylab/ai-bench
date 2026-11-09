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
            rows = speed.measure("pc-rtx2060", "m", self.gguf, [0, 16384], 3)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["status"] == "ok" for r in rows))

    def test_out_of_memory_is_an_error_row_without_the_path(self):
        with self.fake(f"echo 'failed to allocate buffer for {self.gguf}' >&2\nexit 1\n"):
            rows = speed.measure("pc-rtx2060", "m", self.gguf, [0], 3)
        self.assertEqual((rows[0]["status"], rows[0]["reason"]), ("error", "did not fit in memory"))

    def test_a_fitted_command_lets_llama_bench_place_the_layers(self):
        cmd = speed.command("m.gguf", [0, 32768], 3, fit_target=1536)
        self.assertNotIn("-ngl", cmd)  # an explicit layer count would override the fit
        self.assertEqual(cmd[cmd.index("-fitt") + 1], "1536")
        self.assertEqual(cmd[cmd.index("-fitc") + 1], str(32768 + 512 + 128))  # room for the deepest test
        self.assertEqual(speed.command("m.gguf", [0], 3)[speed.command("m.gguf", [0], 3).index("-ngl") + 1], "99")

    def test_a_model_that_does_not_fit_is_measured_again_fitted(self):
        """The error row says it does not fit on the card (episode 02); the fitted rows say how fast it runs with
        part of it on the CPU, placed as the server places it (--fit-target)."""
        (self.tmp / "out.json").write_text(json.dumps(OUTPUT))
        script = (f'case "$*" in *-fitt*) cat {self.tmp / "out.json"} ;; '
                  f'*) echo "failed to allocate buffer" >&2; exit 1 ;; esac\n')
        with self.fake(script):
            rows = speed.measure("pc-rtx2060", "m", self.gguf, [0, 16384], 3, fit_target=1536)
        self.assertEqual([(r["status"], r["fit_target_mib"]) for r in rows],
                         [("error", ""), ("ok", 1536), ("ok", 1536)])
        self.assertEqual(rows[0]["reason"], "did not fit in memory")

    def test_a_model_that_fits_is_not_fitted(self):
        (self.tmp / "out.json").write_text(json.dumps(OUTPUT))
        calls = self.tmp / "calls"
        with self.fake(f'echo "$*" >> {calls}\ncat {self.tmp / "out.json"}\n'):
            rows = speed.measure("pc-rtx2060", "m", self.gguf, [0, 16384], 3, fit_target=1536)
        self.assertEqual(len(calls.read_text().splitlines()), 1)
        self.assertEqual({r["fit_target_mib"] for r in rows}, {""})

    def test_other_errors_are_not_retried(self):
        calls = self.tmp / "calls"
        with self.fake(f'echo "$*" >> {calls}\necho "unknown model architecture" >&2\nexit 1\n'):
            rows = speed.measure("pc-rtx2060", "m", self.gguf, [0], 3, fit_target=1536)
        self.assertEqual(len(calls.read_text().splitlines()), 1)
        self.assertEqual((rows[0]["status"], rows[0]["reason"]), ("error", "unknown model architecture"))

    def test_a_cache_type_sets_the_kv_cache_of_keys_and_values(self):
        """The server's presets quantize the KV cache (q8_0); llama-bench's default is f16, which needs more VRAM."""
        cmd = speed.command("m.gguf", [0, 32768], 3, cache_type="q8_0")
        self.assertEqual((cmd[cmd.index("-ctk") + 1], cmd[cmd.index("-ctv") + 1]), ("q8_0", "q8_0"))
        self.assertNotIn("-ctk", speed.command("m.gguf", [0], 3))  # llama-bench's default (f16), as before

    def test_the_rows_record_the_cache_type(self):
        (self.tmp / "out.json").write_text(json.dumps(OUTPUT))
        calls = self.tmp / "calls"
        with self.fake(f'echo "$*" >> {calls}\ncat {self.tmp / "out.json"}\n'):
            rows = speed.measure("pc-rtx2060", "m", self.gguf, [0, 16384], 3, cache_type="q8_0")
            default = speed.measure("pc-rtx2060", "m", self.gguf, [0, 16384], 3)
        self.assertIn("cache_type", speed.COLUMNS)
        self.assertEqual({r["cache_type"] for r in rows}, {"q8_0"})
        self.assertEqual({r["cache_type"] for r in default}, {""})  # empty = llama-bench's default (f16)
        self.assertIn("-ctk q8_0", calls.read_text().splitlines()[0])

    def test_fewer_than_3_repetitions_is_refused(self):
        with self.assertRaises(ValueError):
            speed.measure("pc-rtx2060", "m", self.gguf, [0], 2)


if __name__ == "__main__":
    unittest.main()
