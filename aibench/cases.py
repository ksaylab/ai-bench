"""Use-case batteries and automatic checkers. Every case is synthetic and ships with a good and a bad example
answer; the tests make sure the checker accepts the first and rejects the second.

Batteries (one JSONL file per use case in cases/): coding, rag, agent, chat_pt.

Checker kinds:
- regex: every `ok` pattern matches and no `forbidden` one does (normalized text: lowercase, no accents)
- lines: exactly `n` non-empty lines, each matching `line`, plus `ok`/`forbidden` on the whole text
- summary: `ok`/`forbidden` plus `max_words` and/or `max_sentences`
- code: the Python code in the answer passes `tests` (isolated subprocess, empty environment, timeout: it is model code)
- rag: `ok`/`forbidden`, every passage in `cite` is cited as [n], `cite_only` forbids other citations,
  `no_citations` forbids any citation (for questions the document does not answer)
- tool_call: exactly one call to `expected.name`, arguments valid against the tool schema and equal to
  `expected.arguments` (lists compared as sets, strings case-insensitive)
- no_tool: no tool call at all, plus `ok`/`forbidden` on the text
- json_schema: the first JSON object in the answer is valid against `schema` and matches `expected`
Any case may set `portuguese: true`: the answer must be in Portuguese.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from aibench import schema
from aibench.text import final_answer, is_portuguese, normalize, sentences, words

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases"
USE_CASES = ["coding", "rag", "agent", "chat_pt"]
KINDS = {"regex", "lines", "summary", "code", "rag", "tool_call", "no_tool", "json_schema"}
PASS_MARK = "__CASE_PASSED__"


BATTERY_FILES = {"agent": ["agent_tools.json"], "rag": ["rag_documents.json"]}


def battery_hash(use_case, context_words=3000, folder=CASES):
    """Version of one use case's battery: the first 12 hex digits of a SHA-256 over its files (and, for RAG, the size
    of the generated documents). Runs and anchors are only compared on the same version."""
    h = hashlib.sha256()
    for name in [f"{use_case}.jsonl"] + BATTERY_FILES.get(use_case, []):
        h.update(name.encode() + b"\0" + (Path(folder) / name).read_bytes() + b"\0")
    if use_case == "rag":
        h.update(f"context_words={context_words}".encode())
    return h.hexdigest()[:12]


def tools_registry():
    return json.loads((CASES / "agent_tools.json").read_text(encoding="utf-8"))


def documents():
    return json.loads((CASES / "rag_documents.json").read_text(encoding="utf-8"))


def load(use_cases=None, context_words=3000, folder=CASES):
    """All cases of the selected use cases, with prompts, tools and generated documents filled in."""
    use_cases = use_cases or USE_CASES
    unknown = set(use_cases) - set(USE_CASES)
    if unknown:
        raise ValueError(f"unknown use case(s): {', '.join(sorted(unknown))} (use {', '.join(USE_CASES)})")
    reg, docs, out = None, None, []
    for uc in use_cases:
        for n, line in enumerate((Path(folder) / f"{uc}.jsonl").read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            c = json.loads(line)
            c["use_case"] = uc
            if c["kind"] not in KINDS:
                raise ValueError(f"{uc}.jsonl:{n}: unknown kind {c['kind']!r}")
            if "tools" in c:
                reg = reg or tools_registry()
                c["tool_specs"] = [{"type": "function", "function": reg[t]} for t in c["tools"]]
            if "document" in c:
                docs = docs or documents()
                c = build_rag(c, docs, context_words)
            out.append(c)
    ids = [c["id"] for c in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    return out


# ---------- RAG documents (fixed handbook, or a long generated one) ----------

SUBJECTS = ["The support team", "The data team", "The board", "Procurement", "Infrastructure", "The research group",
            "The coordination office", "The quality committee", "The sales team", "Finance"]
VERBS = ["reviewed", "approved", "postponed", "documented", "measured", "compared", "planned", "tested", "archived",
         "published"]
OBJECTS = ["the quarterly report", "the backup policy", "the equipment inventory", "the vacation plan",
           "the satisfaction survey", "the project schedule", "the onboarding manual", "the supplier list",
           "the annual budget", "the training plan"]
TAILS = ["with no relevant changes.", "after two meetings.", "with small wording changes.", "and booked a new review.",
         "as agreed.", "with help from consultants.", "and emailed a summary.", "the following week.",
         "ahead of the deadline.", "with one caveat."]
RAG_RULES = ("Answer using only the passages below. Cite the passage numbers you used in square brackets, like [2]. "
             "If the passages do not contain the answer, say that it is not in the document.")


def _lcg(seed):
    x = seed
    while True:
        x = (1103515245 * x + 12345) % 2**31
        yield x


def filler_passages(n_words, seed):
    g, out, total = _lcg(seed), [], 0
    while total < n_words:
        p = " ".join(f"{SUBJECTS[next(g) % 10]} {VERBS[next(g) % 10]} {OBJECTS[next(g) % 10]} {TAILS[next(g) % 10]}"
                     for _ in range(3))
        out.append(p)
        total += len(p.split())
    return out


def build_rag(c, docs, context_words):
    """Numbered passages plus the question. For a generated document, `facts` are inserted at fixed positions and
    `cite_facts` (indexes into `facts`) become the passage numbers to cite."""
    if c["document"] == "generated":
        passages = filler_passages(context_words, c["seed"])
        for i, fact in enumerate(c["facts"]):
            passages.insert(int(len(passages) * (i + 1) / (len(c["facts"]) + 1)), fact)
        positions = [passages.index(f) + 1 for f in c["facts"]]
        c = {**c, "cite": [positions[i] for i in c.get("cite_facts", [])], "context_words": context_words,
             "example_good": c["example_good"].format(*positions), "example_bad": c["example_bad"].format(*positions)}
    else:
        passages = docs[c["document"]]
    body = "\n".join(f"[{i}] {p}" for i, p in enumerate(passages, 1))
    return {**c, "prompt": f"{RAG_RULES}\n\n{body}\n\nQuestion: {c['question']}"}


# ---------- checkers ----------

def _regex(c, text):
    t = normalize(text)
    for p in c.get("ok", []):
        if not re.search(p, t, re.M):
            return False, f"missing: {p}"
    for p in c.get("forbidden", []):
        if re.search(p, t, re.M):
            return False, f"forbidden: {p}"
    return True, ""


def _lines(c, text):
    ls = [l for l in final_answer(text).splitlines() if l.strip()]
    if len(ls) != c["n"]:
        return False, f"{len(ls)} line(s), expected {c['n']}"
    for l in ls:
        if "line" in c and not re.search(c["line"], normalize(l)):
            return False, f"line does not match: {l[:40]}"
    return _regex(c, text)


def _summary(c, text):
    if "max_words" in c and len(words(text)) > c["max_words"]:
        return False, f"{len(words(text))} words, max {c['max_words']}"
    if "max_sentences" in c and len(sentences(text)) > c["max_sentences"]:
        return False, f"{len(sentences(text))} sentences, max {c['max_sentences']}"
    return _regex(c, text)


def citations(text):
    found = set()
    for group in CITATION.findall(final_answer(text)):
        found |= {int(x) for x in re.findall(r"\d+", group)}
    return found


CITATION = re.compile(r"\[\d+(?:\s*[,;]\s*\d+)*\]")


def _rag(c, text):
    ok, why = _regex(c, CITATION.sub(" ", text))  # a citation like [6] is not an answer of 6
    if not ok:
        return ok, why
    cited = citations(text)
    if c.get("no_citations") and cited:
        return False, f"cited {sorted(cited)} for an unanswerable question"
    if missing := set(c.get("cite", [])) - cited:
        return False, f"missing citation {sorted(missing)}"
    if c.get("cite_only") and (extra := cited - set(c.get("cite", []))):
        return False, f"extra citation {sorted(extra)}"
    return True, ""


def _same(a, b):
    if isinstance(b, list):
        return isinstance(a, list) and sorted(map(_norm_value, a)) == sorted(map(_norm_value, b))
    return _norm_value(a) == _norm_value(b)


def _norm_value(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    return re.sub(r"\s+", " ", normalize(str(v)))


def _match_expected(obj, expected):
    for k, v in expected.items():
        if k not in obj:
            return f"missing {k}"
        if not _same(obj[k], v):
            return f"{k}: {obj[k]!r} != {v!r}"
    return ""


def _tool_call(c, answer):
    calls = answer.get("tool_calls") or []
    if len(calls) != 1:
        return False, f"{len(calls)} tool call(s), expected 1"
    call, exp = calls[0], c["expected"]
    if call["name"] != exp["name"]:
        return False, f"called {call['name']}, expected {exp['name']}"
    args = call["arguments"]
    if not isinstance(args, dict):
        return False, "arguments are not a JSON object"
    params = next(t["function"]["parameters"] for t in c["tool_specs"] if t["function"]["name"] == exp["name"])
    if errs := schema.errors(args, params):
        return False, "schema: " + "; ".join(errs[:2])
    if diff := _match_expected(args, exp["arguments"]):
        return False, diff
    return True, ""


def first_json(text):
    t = final_answer(text)
    start = t.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(t)):
            depth += {"{": 1, "}": -1}.get(t[i], 0)
            if depth == 0:
                try:
                    obj = json.loads(t[start:i + 1])
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass
                break
        start = t.find("{", start + 1)
    return None


def _json_schema(c, text):
    obj = first_json(text)
    if obj is None:
        return False, "no JSON object"
    if errs := schema.errors(obj, c["schema"]):
        return False, "schema: " + "; ".join(errs[:2])
    if diff := _match_expected(obj, c.get("expected", {})):
        return False, diff
    return True, ""


def extract_code(text):
    t = final_answer(text)
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", t, re.S)
    return max(blocks, key=len) if blocks else t


def _code(c, text, timeout=10):
    with tempfile.TemporaryDirectory(prefix="aibench-") as d:
        Path(d, "answer.py").write_text(extract_code(text), encoding="utf-8")
        Path(d, "check.py").write_text(
            "import runpy\nglobals().update(runpy.run_path('answer.py', run_name='answer'))\n"
            f"{c['tests']}\nprint({PASS_MARK!r})\n", encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-I", "check.py"], cwd=d, capture_output=True, text=True,
                               timeout=timeout, env={"PATH": "/usr/bin:/bin"})
        except subprocess.TimeoutExpired:
            return False, "timeout"
    if PASS_MARK in r.stdout:
        return True, ""
    return False, ((r.stderr.strip().splitlines() or ["no output"])[-1])[:200]


def as_answer(x):
    """Normalizes an answer: a plain string, or {"text": ..., "tool_calls": [...]}, or a client.chat() result."""
    if isinstance(x, str):
        return {"text": x, "tool_calls": []}
    return {"text": x.get("text") or "", "tool_calls": x.get("tool_calls") or []}


def check(c, answer):
    """(passed, reason)."""
    a = as_answer(answer)
    text, kind = a["text"], c["kind"]
    if kind == "tool_call":
        return _tool_call(c, a)
    if kind == "no_tool" and a["tool_calls"]:
        return False, f"called {a['tool_calls'][0]['name']} but no tool was needed"
    if not final_answer(text):
        return False, "empty answer"
    if c.get("portuguese") and not is_portuguese(text):
        return False, "answer is not in Portuguese"
    if kind in ("regex", "no_tool"):
        return _regex(c, text)
    return {"lines": _lines, "summary": _summary, "rag": _rag, "json_schema": _json_schema, "code": _code}[kind](c, text)


def messages(c):
    m = [{"role": "system", "content": c["system"]}] if c.get("system") else []
    return m + [{"role": "user", "content": c["prompt"]}]
