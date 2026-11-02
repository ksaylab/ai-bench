"""Optional judge (0 to 5) for cases with a `rubric`. The automatic checker is still the verdict; the judge's
score goes to its own column. The judge can never be one of the compared models."""
import json
import re

from aibench import client

SYSTEM = ("You grade answers from language models. You get the question, a rubric and the answer. Give an integer "
          "score from 0 to 5 following the rubric. Reply only with JSON: {\"score\": <0 to 5>, \"reason\": \"one sentence\"}.")


def grade(url, key, model, case, answer):
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"## Question\n\n{case['prompt']}\n\n## Rubric\n\n{case['rubric']}\n\n"
                                        f"## Answer\n\n{answer}"}]
    r = client.chat(url, model, msgs, key=key, max_tokens=2048, temperature=0)
    m = re.search(r"\{.*\}", r["text"], re.S)
    try:
        score = int(json.loads(m.group(0))["score"]) if m else None
    except (ValueError, KeyError, TypeError):
        score = None
    return score, r.get("cost_usd")
