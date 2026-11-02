import hashlib
import json
import unittest

from aibench import cases, schema, text

ALL = cases.load()


class TestBatteries(unittest.TestCase):
    def test_every_use_case_has_a_battery(self):
        self.assertEqual({c["use_case"] for c in ALL}, set(cases.USE_CASES))
        for uc in cases.USE_CASES:
            self.assertGreaterEqual(sum(c["use_case"] == uc for c in ALL), 5, uc)

    def test_ids_are_unique(self):
        ids = [c["id"] for c in ALL]
        self.assertEqual(len(ids), len(set(ids)))

    def test_good_example_passes_and_bad_example_fails(self):
        for c in ALL:
            with self.subTest(case=c["id"]):
                ok, why = cases.check(c, c["example_good"])
                self.assertTrue(ok, why)
                self.assertFalse(cases.check(c, c["example_bad"])[0])

    def test_long_rag_document_is_deterministic(self):
        c = next(c for c in cases.load({"rag"}, context_words=2000) if c["id"] == "long_needle")
        again = next(c for c in cases.load({"rag"}, context_words=2000) if c["id"] == "long_needle")
        self.assertEqual(c["prompt"], again["prompt"])
        self.assertEqual(hashlib.sha256(c["prompt"].encode()).hexdigest()[:12],
                         hashlib.sha256(again["prompt"].encode()).hexdigest()[:12])
        bigger = next(c for c in cases.load({"rag"}, context_words=8000) if c["id"] == "long_needle")
        self.assertGreater(len(bigger["prompt"].split()), 7000)
        self.assertTrue(cases.check(bigger, bigger["example_good"])[0])

    def test_agent_cases_send_the_tools(self):
        for c in cases.load({"agent"}):
            if c["kind"] in ("tool_call", "no_tool"):
                self.assertTrue(c["tool_specs"], c["id"])
                self.assertEqual(c["tool_specs"][0]["type"], "function")


class TestCheckers(unittest.TestCase):
    def case(self, cid):
        return next(c for c in ALL if c["id"] == cid)

    def test_rag_needs_the_right_citation(self):
        c = self.case("single_passage")
        good = cases.as_answer(c["example_good"])["text"]
        self.assertFalse(cases.check(c, cases.CITATION.sub("", good))[0])        # no citation
        self.assertFalse(cases.check(c, cases.CITATION.sub("[4]", good))[0])     # wrong passage

    def test_rag_absent_answer_must_not_cite(self):
        c = self.case("answer_absent")
        self.assertFalse(cases.check(c, cases.as_answer(c["example_good"])["text"] + " [1]")[0])

    def test_tool_call_wrong_enum_or_extra_call_fails(self):
        c = self.case("weather_call")
        good = cases.as_answer(c["example_good"])
        call = good["tool_calls"][0]
        bad_unit = {"text": "", "tool_calls": [{**call, "arguments": {**call["arguments"], "unit": "kelvin"}}]}
        self.assertFalse(cases.check(c, bad_unit)[0])
        self.assertFalse(cases.check(c, {"text": "", "tool_calls": [call, call]})[0])
        self.assertFalse(cases.check(c, {"text": "", "tool_calls": [{**call, "arguments": "{not json"}]})[0])

    def test_code_timeout_and_crash_fail(self):
        c = self.case("fizzbuzz")
        self.assertFalse(cases.check(c, "```python\nwhile True:\n    pass\n```")[0])
        self.assertFalse(cases.check(c, "```python\nraise SystemExit(0)\n```")[0])

    def test_code_runs_without_the_callers_environment(self):
        c = {**self.case("fizzbuzz"), "tests": "import os\nassert 'OPENROUTER_API_KEY' not in os.environ"}
        self.assertTrue(cases.check(c, "```python\nx = 1\n```")[0])

    def test_portuguese_cases_reject_english(self):
        c = self.case("explain_vpn")
        self.assertFalse(cases.check(c, "A VPN creates an encrypted tunnel between your computer and the network.")[0])

    def test_schema(self):
        s = {"type": "object", "required": ["a"], "additionalProperties": False,
             "properties": {"a": {"type": "string", "enum": ["x", "y"]}, "b": {"type": ["integer", "null"]}}}
        self.assertEqual(schema.errors({"a": "x", "b": None}, s), [])
        self.assertTrue(schema.errors({"a": "z"}, s))
        self.assertTrue(schema.errors({"a": "x", "c": 1}, s))
        self.assertTrue(schema.errors({"b": 1}, s))
        self.assertTrue(schema.errors({"a": "x", "b": True}, s))

    def test_thinking_is_ignored(self):
        self.assertEqual(text.final_answer("<think>maybe 5</think>The answer is 7"), "The answer is 7")


class TestEnglishOnly(unittest.TestCase):
    """Everything is English except the content of the Portuguese chat battery."""
    MARKERS = ("ção", "ções", "você", "não ", "também", " para o ", " uma ", "rodada", "modelo ", "episódio",
               "arquivo", "máquina", "preço", "resultado")

    def test_no_portuguese_outside_chat_pt(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        allowed = {"cases/chat_pt.jsonl", "tests/test_cases.py"}
        found = []
        for p in root.rglob("*"):
            rel = p.relative_to(root).as_posix()
            if not p.is_file() or rel in allowed or ".git/" in rel or "__pycache__" in rel or "/runs/" in rel:
                continue
            body = p.read_text(encoding="utf-8", errors="ignore").lower()
            if rel == "aibench/text.py":  # the Portuguese stop-word list the language check needs
                body = body.split("pt_words", 1)[0]
            hits = [m for m in self.MARKERS if m in body]
            if hits:
                found.append(f"{rel}: {hits}")
        self.assertEqual(found, [])

    def test_chat_pt_prompts_are_portuguese(self):
        for c in cases.load({"chat_pt"}):
            self.assertTrue(text.is_portuguese(c["prompt"]), c["id"])
        json.dumps(ALL)  # the loaded cases are plain JSON


if __name__ == "__main__":
    unittest.main()
