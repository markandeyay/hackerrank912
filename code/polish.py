"""Optional third model job: polish the template explanation.

The template already contains every fact; the model only rewrites it into one
or two natural sentences.  Every number and date in the template must survive
the rewrite, otherwise the template text is kept.  Results are cached.
"""
from __future__ import annotations

import re

from explain import longdate, money
from llm import cache_key, call_json
from planner import Decision

SCHEMA = {
    "type": "object",
    "properties": {"explanation": {"type": "string"}},
    "required": ["explanation"],
    "additionalProperties": False,
}

SYSTEM = (
    "You edit one-line financial recommendations for a personal finance app. Rewrite the draft into one or two short, "
    "plain sentences (max 60 words) that keep EVERY amount, currency code, date and event name exactly as written and add "
    "no new facts, numbers or advice. Keep the currency code before each amount and the thousands separators. "
    "Do not use markdown."
)

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> list[str]:
    return sorted(NUM_RE.findall(text))


def polish_explanation(dec: Decision, draft: str) -> str:
    req, st, plan = dec.request, dec.state, dec.plan
    facts = {
        "request_id": req.request_id,
        "request_type": req.request_type,
        "requested": money(st.home, req.requested_amount),
        "deadline": longdate(req.desired_completion_date),
        "method": plan.method,
        "status": plan.status,
        "amount_safe_today": money(st.home, dec.safe_amount),
        "earliest_full_payment": longdate(dec.earliest) if dec.earliest else "none within the forecast",
        "minimum_balance": money(st.home, st.min_balance),
    }
    user_text = "Draft:\n" + draft + "\n\nContext (for tone only, do not add these numbers unless they are already in the draft):\n" + "\n".join(f"- {k}: {v}" for k, v in facts.items())
    key = cache_key(req.request_id, draft)
    try:
        res = call_json(kind="explanation_polish", cache_name="explanations", key=key, system=SYSTEM, user_text=user_text, schema=SCHEMA, effort="low", max_tokens=400)
    except Exception as exc:  # noqa: BLE001 - never let polishing break the run
        print(f"polish failed for {req.request_id}: {exc}")
        return draft
    text = (res.get("explanation") or "").strip().replace("\n", " ")
    if not text or len(text) > 400 or _numbers(text) != _numbers(draft):
        return draft
    return text
