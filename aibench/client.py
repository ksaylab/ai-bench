"""Minimal OpenAI-compatible client (llama-server, Ollama, OpenRouter). Standard library only.

API keys come from environment variables and are never written to disk or printed.
"""
import json
import os
import time
import urllib.error
import urllib.request

OPENROUTER = "https://openrouter.ai/api/v1"

# Known targets. url None = --url or AIBENCH_URL is required (the LAN address of a PC does not belong in a public
# repository). Default ports: llama-server 8080, Ollama 11434.
TARGETS = {
    "pc-rtx2060": {"url": None, "key_env": None,
                   "description": "PC with an RTX 2060 Super 8 GB, llama-server on the LAN or on the PC itself "
                                  "(set AIBENCH_URL, e.g. http://localhost:8080/v1 when running on the PC)"},
    "runpod": {"url": "http://localhost:8080/v1", "key_env": "AIBENCH_SERVER_KEY",
               "description": "RunPod pod running llama-server, through an ssh tunnel on local port 8080"},
    "openrouter": {"url": OPENROUTER, "key_env": "OPENROUTER_API_KEY",
                   "description": "cloud models (paid): calibration anchors and the optional judge only"},
}


# Sampling parameters accepted in a models.toml `[model.sampling]` table and sent as-is in the request body.
# llama-server and OpenRouter accept all of them (OpenRouter passes them to providers that support them).
SAMPLING_KEYS = ("temperature", "top_p", "top_k", "min_p", "presence_penalty", "frequency_penalty", "repeat_penalty",
                 "seed")


class ClientError(Exception):
    pass


def sampling_body(sampling):
    """The request-body part of a sampling table: only the known keys (`source`, `card`... are documentation)."""
    return {k: sampling[k] for k in SAMPLING_KEYS if k in (sampling or {})}


def resolve_target(target, url=None, env=os.environ):
    """(url, key) for a target. AIBENCH_URL only applies to local servers: it never redirects the OpenRouter key."""
    if target not in TARGETS:
        raise ClientError(f"unknown target {target!r} (use {', '.join(TARGETS)})")
    t = TARGETS[target]
    url = url or (None if target == "openrouter" else env.get("AIBENCH_URL")) or t["url"]
    if not url:
        raise ClientError(f"target {target} needs --url or the AIBENCH_URL environment variable")
    key = env.get(t["key_env"]) if t["key_env"] else None
    if target == "openrouter" and not key:
        raise ClientError("set OPENROUTER_API_KEY in the environment (never in the repository)")
    return url.rstrip("/"), key


def _tool_calls(message):
    calls = []
    for c in message.get("tool_calls") or []:
        fn = c.get("function") or {}
        args = fn.get("arguments", "")
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                pass  # kept as a string: the checker reports invalid JSON
        calls.append({"name": fn.get("name", ""), "arguments": args})
    return calls


def chat(url, model, messages, key=None, max_tokens=8192, temperature=None, tools=None, timeout=900, attempts=3,
         extra=None, sampling=None):
    """One chat call. Returns text, reasoning, tool calls, tokens, cost (when the provider reports it) and time.
    `sampling`: temperature, top_p, top_k, min_p, presence_penalty, seed... (SAMPLING_KEYS), sent as given."""
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    body.update(sampling_body(sampling))
    if temperature is not None:
        body["temperature"] = temperature
    if tools:
        body["tools"] = tools
    if url.startswith(OPENROUTER):
        body["usage"] = {"include": True}
    body.update(extra or {})
    headers = {"Content-Type": "application/json", "User-Agent": "ai-bench/0.2"}
    if key:
        headers["Authorization"] = "Bearer " + key
    data = json.dumps(body).encode()
    last = None
    for i in range(attempts):
        start = time.monotonic()
        try:
            req = urllib.request.Request(url + "/chat/completions", data, headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.load(r)
            break
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code < 500 and e.code != 429:
                raise ClientError(last) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = f"connection: {type(e).__name__}"
        time.sleep(2 * (i + 1))
    else:
        raise ClientError(last or "no response")
    elapsed = time.monotonic() - start
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    usage = resp.get("usage") or {}
    out = usage.get("completion_tokens")
    return {"text": msg.get("content") or "", "reasoning": msg.get("reasoning_content") or msg.get("reasoning") or "",
            "tool_calls": _tool_calls(msg), "finish": choice.get("finish_reason", ""),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": out, "cost_usd": usage.get("cost"),
            "time_s": round(elapsed, 3), "tok_s": round(out / elapsed, 2) if out and elapsed > 0 else None}
