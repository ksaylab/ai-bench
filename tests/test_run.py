import csv
import json
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from aibench import cases, client, run, verdict

BY_PROMPT = {c["prompt"]: c for c in cases.load()}
QUIET = {"log": lambda *_: None}


class FakeServer(BaseHTTPRequestHandler):
    """Speaks llama-server's /v1/chat/completions: answers each case with its good example (tool calls included)."""
    requests = []
    bad_models = set()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeServer.requests.append({"model": body["model"], "auth": self.headers.get("Authorization"),
                                    "tools": [t["function"]["name"] for t in body.get("tools") or []]})
        msg = {"role": "assistant", "content": ""}
        if body["messages"][0]["content"].startswith("You grade"):
            msg["content"] = '{"score": 5, "reason": "ok"}'
        else:
            case = BY_PROMPT.get(body["messages"][-1]["content"])
            if case is None:  # generated RAG documents depend on --context-words: match by id in the system prompt
                case = next(c for c in cases.load({"rag"}, len(body["messages"][-1]["content"].split()))
                            if c["prompt"] == body["messages"][-1]["content"])
            ex = case["example_bad" if body["model"] in FakeServer.bad_models else "example_good"]
            a = cases.as_answer(ex)
            msg["content"] = a["text"]
            if a["tool_calls"]:
                msg["tool_calls"] = [{"id": f"call_{i}", "type": "function",
                                      "function": {"name": t["name"], "arguments": json.dumps(t["arguments"])}}
                                     for i, t in enumerate(a["tool_calls"])]
        data = json.dumps({"choices": [{"message": msg, "finish_reason": "stop"}],
                           "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "episodes" / "99-test" / "results").mkdir(parents=True)
        p = mock.patch.object(run, "EPISODES", self.tmp / "episodes")
        p.start()
        self.addCleanup(p.stop)
        FakeServer.requests.clear()
        FakeServer.bad_models = set()

    def server(self):
        srv = HTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_port}/v1"

    def test_simulated_run_writes_everything_and_is_not_publishable(self):
        d = run.run("99-test", "pc-rtx2060", ["a", "b"], simulate=True, **QUIET)
        self.assertEqual(len(read(d / "executions.csv")), 2 * 3 * len(cases.load()))
        self.assertFalse(json.loads((d / "meta.json").read_text())["publishable"])
        v = read(d / "verdicts.csv")
        self.assertEqual([r["model"] for r in v], ["a", "b"])
        self.assertIn("Not good for", (d / "verdicts.md").read_text() + "Not good for")
        self.assertEqual(run.consolidate("99-test")[1], 0)

    def test_fewer_than_3_runs_only_with_smoke(self):
        with self.assertRaises(run.RunError):
            run.run("99-test", "pc-rtx2060", ["a"], runs=1, simulate=True, **QUIET)
        d = run.run("99-test", "pc-rtx2060", ["a"], runs=1, simulate=True, smoke=True, **QUIET)
        self.assertTrue(d.name.endswith("-smoke-simulated"))
        self.assertEqual(read(d / "verdicts.csv")[0]["inconclusive"].count(";"), 3)  # all four use cases

    def test_competing_judge_is_refused(self):
        with self.assertRaises(run.RunError):
            run.run("99-test", "openrouter", ["x/judge", "y"], judge_model="x/judge", simulate=True)

    def test_pc_needs_url_and_openrouter_needs_key(self):
        with self.assertRaises(client.ClientError):
            client.resolve_target("pc-rtx2060", env={})
        with self.assertRaises(client.ClientError):
            client.resolve_target("openrouter", env={})
        self.assertEqual(client.resolve_target("openrouter", env={"OPENROUTER_API_KEY": "k"})[1], "k")

    def test_local_contestants_run_only_on_the_pc(self):
        import tomllib
        self.assertNotIn("mac-m5", client.TARGETS)
        for path in run.ROOT.glob("episodes/*/models.toml"):
            for m in tomllib.loads(path.read_text(encoding="utf-8")).get("model", []):
                self.assertTrue(set(m["machines"]) <= {"pc-rtx2060", "runpod"}, (path.parent.name, m["name"]))

    def test_aibench_url_never_redirects_the_openrouter_key(self):
        env = {"OPENROUTER_API_KEY": "k", "AIBENCH_URL": "http://other/v1"}
        self.assertEqual(client.resolve_target("openrouter", env=env)[0], client.OPENROUTER)
        self.assertEqual(client.resolve_target("pc-rtx2060", env=env), ("http://other/v1", None))

    def test_all_batteries_against_a_local_http_server(self):
        url = self.server()
        FakeServer.bad_models = {"weak"}
        with mock.patch.object(run.env, "capture", return_value={"machine": "pc-rtx2060"}):
            d = run.run("99-test", "pc-rtx2060", ["strong", "weak"], url=url, **QUIET)
        rows = read(d / "executions.csv")
        strong = [r for r in rows if r["model"] == "strong"]
        self.assertTrue(all(r["passed"] == "1" for r in strong), [(r["case"], r["reason"]) for r in strong
                                                                    if r["passed"] != "1"])
        self.assertTrue(all(r["passed"] == "0" for r in rows if r["model"] == "weak"))
        self.assertTrue(all(r["completion_tokens"] == "5" for r in rows))
        self.assertTrue(all(p["auth"] is None for p in FakeServer.requests))
        agent_tools = {n for p in FakeServer.requests for n in p["tools"]}
        self.assertIn("get_weather", agent_tools)
        v = {r["model"]: r for r in read(d / "verdicts.csv")}
        self.assertEqual(v["strong"]["not_good_for"], "")
        self.assertEqual(v["strong"]["good_for"].count(";"), 3)
        self.assertEqual(v["weak"]["good_for"], "")
        path, n, _ = run.consolidate("99-test")
        self.assertEqual(n, len(rows))
        self.assertTrue((path.parent / "verdicts.md").read_text().count("✅") >= 4)

    def test_judge_on_its_own_address_only_on_rubric_cases(self):
        url = self.server()
        with mock.patch.object(run.env, "capture", return_value={}), \
                mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-token"}):
            d = run.run("99-test", "pc-rtx2060", ["m1"], url=url, use_cases={"chat_pt", "coding"},
                        judge_model="judge/x", judge_url=url, **QUIET)
        rows = read(d / "executions.csv")
        scored = {r["case"] for r in rows if r["judge_score"] == "5"}
        self.assertEqual(scored, {c["id"] for c in cases.load({"chat_pt", "coding"}) if c.get("rubric")})
        judge = [p for p in FakeServer.requests if p["model"] == "judge/x"]
        self.assertEqual(len(judge), 3 * len(scored))
        self.assertTrue(all(p["auth"] == "Bearer test-token" for p in judge))
        self.assertTrue(all(p["auth"] is None for p in FakeServer.requests if p["model"] == "m1"))

    def test_environment_is_of_the_model_server_named_in_aibench_server_host(self):
        url = self.server()
        with mock.patch.object(run.env, "capture", return_value={}) as capture, \
                mock.patch.dict(run.os.environ, {"AIBENCH_SERVER_HOST": "gpu-box"}):
            run.run("99-test", "pc-rtx2060", ["m1", "m2"], url=url, use_cases={"agent"}, **QUIET)
        capture.assert_called_once_with("pc-rtx2060", url, server_host="gpu-box", models=["m1", "m2"])

    def test_server_down_is_an_error_row_and_inconclusive(self):
        with mock.patch.object(run.env, "capture", return_value={}), mock.patch.object(client.time, "sleep"):
            d = run.run("99-test", "pc-rtx2060", ["m1"], url="http://127.0.0.1:9/v1", use_cases={"agent"}, **QUIET)
        rows = read(d / "executions.csv")
        self.assertTrue(all(r["passed"] == "0" and r["reason"].startswith("error:") for r in rows))
        self.assertEqual(read(d / "verdicts.csv")[0]["inconclusive"], verdict.LABELS["agent"])


class TestVerdict(unittest.TestCase):
    def rows(self, use_case, n_cases, runs, fails):
        out = []
        for rep in range(runs):
            for i in range(n_cases):
                out.append({"run_id": "r", "machine": "m", "model": "x", "use_case": use_case, "case": f"c{i}",
                            "rep": rep, "passed": int((rep, i) not in fails), "reason": "", "time_s": 1,
                            "tok_s": 10, "cost_usd": 0.001})
        return out

    def test_thresholds(self):
        s = verdict.scores(self.rows("coding", 5, 3, set()))[0]
        self.assertEqual((s["score_pct"], s["verdict"]), (100.0, "Good for"))
        s = verdict.scores(self.rows("coding", 5, 3, {(0, 0), (1, 0), (2, 0)}))[0]  # 12/15 = 80%
        self.assertEqual((s["score_pct"], s["verdict"], s["borderline"]), (80.0, "Good for", 1))
        s = verdict.scores(self.rows("coding", 5, 3, {(0, 0), (1, 0), (2, 0), (2, 1)}))[0]  # 11/15
        self.assertEqual(s["verdict"], "Not good for")
        self.assertEqual((s["min_run_pct"], s["max_run_pct"]), (60.0, 80.0))

    def test_inconclusive_with_few_runs_or_many_errors(self):
        self.assertEqual(verdict.scores(self.rows("rag", 5, 2, set()))[0]["verdict"], "Inconclusive")
        rows = self.rows("rag", 5, 3, {(0, 0), (0, 1)})
        for r in rows[:2]:
            r["reason"] = "error: connection refused"
        self.assertEqual(verdict.scores(rows)[0]["verdict"], "Inconclusive")  # 2/15 > 10%

    def test_verdict_table(self):
        rows = self.rows("coding", 5, 3, set()) + self.rows("rag", 5, 3, {(r, i) for r in range(3) for i in range(3)})
        v = verdict.verdicts(verdict.scores(rows))[0]
        self.assertEqual((v["good_for"], v["not_good_for"]), ("Coding", "RAG (answers with sources)"))
        self.assertEqual((v["coding_pct"], v["rag_pct"], v["agent_pct"]), (100.0, 40.0, ""))
        md = verdict.markdown([v])
        self.assertIn("100% ✅", md)
        self.assertIn("40% ❌", md)


if __name__ == "__main__":
    unittest.main()
