"""Minimal OpenAI-compatible client (llama-server, Ollama, OpenRouter). Standard library only.

API keys come from environment variables and are never written to disk or printed.
"""
import http.client
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


def _http_error(e, limit=300):
    """"HTTP <code>: <the API's message>", cut to `limit` characters: OpenRouter says why routing failed (e.g. which
    filter removed the pinned provider) in the JSON body, which a bare status code would lose."""
    try:
        body = json.loads(e.read() or b"{}")
        err = body.get("error") if isinstance(body, dict) else None
        detail = err.get("message", "") if isinstance(err, dict) else str(err or "")
    except (ValueError, OSError, AttributeError):
        detail = ""
    text = f"HTTP {e.code}: {' '.join(detail.split())}" if detail else f"HTTP {e.code}"
    return text if len(text) <= limit else text[:limit - 1] + "…"


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


def models_info(ids, url=OPENROUTER, key=None, timeout=30):
    """Price (USD per 1M input / output tokens) and accepted parameters of each id, read from OpenRouter's /models
    list (no cost). OpenRouter's list is public, but a proxy in front of it may want the key (`key`): without it
    such a proxy answers 401. Missing ids map to {"error": ...}; a failed read raises ClientError."""
    headers = {"User-Agent": "ai-bench/0.2"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        req = urllib.request.Request(url.rstrip("/") + "/models", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r).get("data", [])
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
        raise ClientError(f"could not read the model list: {type(e).__name__}") from None
    by_id = {m.get("id"): m for m in data}
    out = {}
    for i in ids:
        m = by_id.get(i)
        if not m:
            out[i] = {"error": "not in the OpenRouter model list"}
            continue
        price = m.get("pricing") or {}

        def per_million(k):
            try:
                return round(float(price[k]) * 1e6, 6)
            except (KeyError, TypeError, ValueError):
                return None
        out[i] = {"usd_per_1m_input": per_million("prompt"), "usd_per_1m_output": per_million("completion"),
                  "supported_parameters": sorted(m.get("supported_parameters") or [])}
    return out


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


def _read_stream(r, start):
    """Accumulates an OpenAI-style server-sent event stream. Returns (message, finish, usage, ttft_s): ttft_s is the
    time from the request to the first chunk with text, reasoning or a tool call."""
    text, reasoning, calls, finish, usage, ttft, extra = [], [], {}, "", {}, None, {}
    for raw in r:
        line = raw.decode("utf-8", "replace").strip() if isinstance(raw, bytes) else raw.strip()
        if not line.startswith("data:"):
            continue  # blank keep-alives and ": comment" lines (OpenRouter sends ": OPENROUTER PROCESSING")
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if chunk.get("usage"):
            usage = chunk["usage"]
        if chunk.get("timings"):
            extra["timings"] = chunk["timings"]
        if chunk.get("provider"):
            extra["provider"] = chunk["provider"]  # OpenRouter: the provider that answered
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            got = False
            if delta.get("content"):
                text.append(delta["content"])
                got = True
            r_part = delta.get("reasoning_content") or delta.get("reasoning")
            if r_part:
                reasoning.append(r_part)
                got = True
            for tc in delta.get("tool_calls") or []:
                slot = calls.setdefault(tc.get("index", len(calls)), {"function": {"name": "", "arguments": ""}})
                fn = tc.get("function") or {}
                slot["function"]["name"] += fn.get("name") or ""
                slot["function"]["arguments"] += fn.get("arguments") or ""
                got = True
            if got and ttft is None:
                ttft = time.monotonic() - start
            if choice.get("finish_reason"):
                finish = choice["finish_reason"]
    message = {"content": "".join(text), "reasoning_content": "".join(reasoning),
               "tool_calls": [calls[i] for i in sorted(calls)]}
    return message, finish, usage, ttft, extra


def chat(url, model, messages, key=None, max_tokens=8192, temperature=None, tools=None, timeout=900, attempts=3,
         extra=None, sampling=None, stream=False):
    """One chat call. Returns text, reasoning, tool calls, tokens, cost (when the provider reports it), time and
    time to first token (`ttft_s`: measured when streaming; otherwise llama-server's prompt time, when reported).
    `sampling`: temperature, top_p, top_k, min_p, presence_penalty, seed... (SAMPLING_KEYS), sent as given."""
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    body.update(sampling_body(sampling))
    if temperature is not None:
        body["temperature"] = temperature
    if tools:
        body["tools"] = tools
    if url.startswith(OPENROUTER):
        body["usage"] = {"include": True}
    if stream:
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
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
                if stream and "text/event-stream" in (r.headers.get("Content-Type") or ""):
                    msg, finish, usage, ttft, more = _read_stream(r, start)
                    resp = {"choices": [{"message": msg, "finish_reason": finish}], "usage": usage, **more}
                else:
                    resp, ttft = json.load(r), None
            break
        except urllib.error.HTTPError as e:
            last = _http_error(e)
            if e.code < 500 and e.code != 429:
                raise ClientError(last) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
            last = f"connection: {type(e).__name__}"
        time.sleep(2 * (i + 1))
    else:
        raise ClientError(last or "no response")
    elapsed = time.monotonic() - start
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    usage = resp.get("usage") or {}
    out = usage.get("completion_tokens")
    if ttft is None and (resp.get("timings") or {}).get("prompt_ms") is not None:
        ttft = resp["timings"]["prompt_ms"] / 1000  # llama-server without streaming: prompt processing time
    gen = elapsed - ttft if ttft is not None else None
    return {"text": msg.get("content") or "", "reasoning": msg.get("reasoning_content") or msg.get("reasoning") or "",
            "tool_calls": _tool_calls(msg), "finish": choice.get("finish_reason", ""),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": out, "cost_usd": usage.get("cost"),
            "time_s": round(elapsed, 3), "tok_s": round(out / elapsed, 2) if out and elapsed > 0 else None,
            "ttft_s": None if ttft is None else round(ttft, 3),
            "gen_tok_s": round(out / gen, 2) if out and gen and gen > 0 else None,
            "provider": resp.get("provider") or ""}
