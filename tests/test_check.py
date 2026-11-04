import os
import tempfile
import unittest
from unittest import mock

from aibench import check, env


def f(*parts):
    """Joined at runtime: the test strings never appear whole in the source or the .pyc."""
    return "".join(parts)


class TestCheck(unittest.TestCase):
    def kinds(self, text, terms=()):
        return {k for k, _ in check.findings(text, terms)}

    def test_catches_what_must_not_leak(self):
        self.assertIn("IPv4", self.kinds(f("the server 10", ".1.2.3 answers")))
        self.assertIn("host:port", self.kinds(f("use http://localhost", ":8787/v1")))
        self.assertIn("host:port", self.kinds(f("tunnel on my-pc.local", ":18080 ")))
        self.assertIn("OpenRouter/OpenAI token", self.kinds(f("sk-or", "-v1-", *["0"] * 64)))
        self.assertIn("GitHub token", self.kinds(f("ghp", "_", *["x"] * 36)))
        self.assertIn("private key", self.kinds(f("-----BEGIN RSA PRI", "VATE KEY-----")))
        self.assertIn("home path", self.kinds(f("/ho", "me/someone/models")))
        self.assertIn("e-mail", self.kinds(f("write to someone", "@example.com")))
        self.assertEqual(self.kinds("project Secret X", ["secret x"]), {"private term"})

    def test_lets_public_things_through(self):
        for t in ("http://localhost:8080/v1", "http://localhost:11434/v1", "127.0.0.1", "at 14:30 ",
                  "ksaylab@users.noreply.github.com", "llama.cpp b9000, version 0.26.0", "ANSWER: 17h05"):
            self.assertEqual(self.kinds(t), set(), t)

    def test_synthetic_data_may_have_addresses_but_never_secrets(self):
        # the batteries and the models' answers to them are full of made-up IPs and e-mails (an IP parsing case,
        # fictional contacts); a token, a key, a home path or a private term is still a leak there
        for t in (f("the server 10", ".1.2.3 answers"), f("tunnel on my-pc.local", ":18080 "),
                  f("write to someone", "@example.com")):
            self.assertTrue(self.kinds(t) & {"IPv4", "host:port", "e-mail"}, t)  # still caught everywhere else
            self.assertEqual({k for k, _ in check.findings(t, synthetic=True)}, set(), t)
        for t, kind in ((f("sk-or", "-v1-", *["0"] * 64), "OpenRouter/OpenAI token"),
                        (f("-----BEGIN RSA PRI", "VATE KEY-----"), "private key"),
                        (f("/ho", "me/someone/models"), "home path")):
            self.assertIn(kind, {k for k, _ in check.findings(t, synthetic=True)}, t)
        self.assertEqual({k for k, _ in check.findings("project Secret X", ["secret x"], synthetic=True)},
                         {"private term"})

    def test_only_batteries_and_answers_are_synthetic(self):
        from pathlib import Path
        for p in ("cases/coding.jsonl", "cases/agent_tools.json", "cases/coding_public/cases.jsonl",
                  "calibration/runs/2026-11-04-0754-openrouter-anchors/responses.jsonl",
                  "episodes/02-what-runs-on-8gb/results/runs/x/responses.jsonl",
                  # the reason column repeats the checker and the tests on synthetic data ("Invalid network '10...")
                  "episodes/02-what-runs-on-8gb/results/runs/x/executions.csv",
                  "episodes/02-what-runs-on-8gb/results/executions.csv", "calibration/runs/x/executions.csv"):
            self.assertTrue(check.is_synthetic(Path(p)), p)
        for p in ("cases/CHANGELOG.md", "calibration/runs/x/env.json", "calibration/runs/x/meta.json",
                  "calibration/runs/x/scores.csv", "HOW-TO-RUN.md", "aibench/client.py", "responses.md"):
            self.assertFalse(check.is_synthetic(Path(p)), p)

    def test_excerpt_is_masked(self):
        secret = f("sk-or", "-v1-", *["a"] * 64)
        self.assertTrue(all(secret not in hit for _, hit in check.findings(secret)))

    def test_terms_come_from_outside_the_repository(self):
        self.assertIsNone(check.private_terms(env={}))
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("# comment\nAlpha\n\nbeta gamma\n")
        self.addCleanup(os.unlink, fh.name)
        self.assertEqual(check.private_terms(env={"PRIVATE_TERMS_FILE": fh.name}), ["alpha", "beta gamma"])
        with self.assertRaises(FileNotFoundError):
            check.private_terms(env={"PRIVATE_TERMS_FILE": fh.name + ".missing"})

    def test_main_refuses_without_a_terms_list(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("builtins.print"):
            self.assertEqual(check.main([]), 2)


class TestEnv(unittest.TestCase):
    def test_does_not_record_the_machine_identity(self):
        e = env.capture("pc-rtx2060")

        def values(x):
            if isinstance(x, dict):
                return [v for item in x.values() for v in values(item)]
            if isinstance(x, list):
                return [v for item in x for v in values(item)]
            return [str(x).lower()]
        body = " ".join(values(e))  # values only: the host name may match a key (e.g. "macos")
        import getpass
        import socket
        self.assertNotIn(socket.gethostname().lower(), body)
        self.assertNotIn(f"/{getpass.getuser().lower()}", body)
        for field in ("os", "cpu", "ram_gib", "gpus", "python"):
            self.assertIn(field, e)

    def test_scrub_removes_paths_and_ips(self):
        self.assertEqual(env.scrub(f("built in /Us", "ers/someone/x and 10", ".0.0.1")), "built in <path> and <ip>")


if __name__ == "__main__":
    unittest.main()
