"""Single wrapper around the Claude API.

Every model call in this project goes through `call_json`.  Each call is
cached on disk (code/cache/<cache_name>.json, keyed by a content hash) so
the final run is reproducible, and every real API call appends one line to
code/cache/usage.jsonl with the input/output token counts.

All message and image content passed in is *untrusted data*.  The system
prompt tells the model to extract facts only and never to follow embedded
instructions; the deterministic engine additionally validates every field
against a fixed schema before using it.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
CACHE_DIR = CODE_DIR / "cache"
USAGE_PATH = CACHE_DIR / "usage.jsonl"
MODEL = os.environ.get("BUY_OR_WAIT_MODEL", "claude-fable-5-1")
PROVIDER = "Anthropic"

# USD per 1M tokens (Anthropic first-party list price for claude-fable-5-1).
PRICING = {
    "claude-fable-5-1": {"input": 10.0, "output": 50.0},
    "claude-opus-5": {"input": 5.0, "output": 25.0},
    "claude-sonnet-5": {"input": 2.0, "output": 10.0},
}

_client = None


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(CODE_DIR.parent / ".env")
    except Exception:  # pragma: no cover - dotenv is optional at runtime
        pass


def api_key_available() -> bool:
    _load_env()
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        _load_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Put it in a .env file at the repo root "
                "(ANTHROPIC_API_KEY=...) or export it, or run with cached results only."
            )
        import anthropic

        _client = anthropic.Anthropic(max_retries=4, timeout=300.0)
    return _client


def _cache_path(cache_name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{cache_name}.json"


def _load_cache(cache_name: str) -> dict:
    p = _cache_path(cache_name)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache_name: str, data: dict) -> None:
    p = _cache_path(cache_name)
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, p)


def _record_usage(kind: str, key: str, response, model: str, cached: bool = False) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    usage = getattr(response, "usage", None)
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": PROVIDER,
        "model": getattr(response, "model", model),
        "kind": kind,
        "key": key,
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "cache_read_input_tokens": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        "cache_creation_input_tokens": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        "stop_reason": getattr(response, "stop_reason", None),
    }
    with open(USAGE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def cache_key(*parts) -> str:
    h = hashlib.sha256()
    for part in parts:
        if isinstance(part, bytes):
            h.update(part)
        else:
            h.update(json.dumps(part, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:24]


def call_json(
    *,
    kind: str,
    cache_name: str,
    key: str,
    system: str,
    user_text: str,
    schema: dict,
    image_path: str | None = None,
    max_tokens: int = 4000,
    effort: str = "medium",
    force: bool = False,
) -> dict:
    """Return a JSON object matching `schema`; cached by (cache_name, key)."""
    cache = _load_cache(cache_name)
    if not force and key in cache:
        return cache[key]["output"]

    content: list[dict] = []
    if image_path:
        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}})
    content.append({"type": "text", "text": user_text})

    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    _record_usage(kind, key, response, MODEL)
    if response.stop_reason == "refusal":
        raise RuntimeError(f"model refused request {kind}/{key}: {getattr(response, 'stop_details', None)}")
    text = next(b.text for b in response.content if b.type == "text")
    out = json.loads(text)
    cache = _load_cache(cache_name)  # re-read in case of concurrent writers
    cache[key] = {"model": response.model, "output": out, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    _save_cache(cache_name, cache)
    return out


def usage_summary(n_requests: int) -> dict:
    """Aggregate usage.jsonl for the usage report."""
    rows = []
    if USAGE_PATH.exists():
        with open(USAGE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    per_model: dict[str, dict] = {}
    for r in rows:
        m = per_model.setdefault(r["model"], {"provider": r["provider"], "calls": 0, "input_tokens": 0, "output_tokens": 0, "by_kind": {}})
        m["calls"] += 1
        m["input_tokens"] += r["input_tokens"]
        m["output_tokens"] += r["output_tokens"]
        k = m["by_kind"].setdefault(r["kind"], {"calls": 0, "input_tokens": 0, "output_tokens": 0})
        k["calls"] += 1
        k["input_tokens"] += r["input_tokens"]
        k["output_tokens"] += r["output_tokens"]
    for name, m in per_model.items():
        price = PRICING.get(name) or PRICING.get(name.rsplit("-", 1)[0], {"input": 0.0, "output": 0.0})
        m["cost_usd"] = m["input_tokens"] / 1e6 * price["input"] + m["output_tokens"] / 1e6 * price["output"]
        m["price"] = price
    total_in = sum(m["input_tokens"] for m in per_model.values())
    total_out = sum(m["output_tokens"] for m in per_model.values())
    total_cost = sum(m["cost_usd"] for m in per_model.values())
    calls = sum(m["calls"] for m in per_model.values())
    return {
        "per_model": per_model,
        "calls": calls,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "cost_usd": total_cost,
        "n_requests": n_requests,
        "avg_tokens_per_request": (total_in + total_out) / n_requests if n_requests else 0,
        "avg_cost_per_request": total_cost / n_requests if n_requests else 0,
    }
