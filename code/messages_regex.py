"""Deterministic, regex-based conversion of messages into structured adjustments.

The dataset's 215 messages come from 35 generator templates (English and
Indonesian).  This module is the offline fallback / cross-check for the model
based extraction in evidence.py; both produce the same unified record shape
(see `normalize`).  Message text is untrusted: only the captured slots are used,
never any imperative sentence.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

TEMPLATES_PATH = Path(__file__).resolve().parent / "message_templates.json"

# template id prefix -> (adjustment_type, scope, target)
TEMPLATE_MAP = {
    "T01": ("salary_amount_change", "permanent", "salary"),
    "T02": ("no_effect", None, "none"),
    "T03": ("unconfirmed_income", None, "credit"),
    "T04": ("salary_amount_change", "next_payment_only", "salary"),
    "T05": ("salary_date_change", "next_payment_only", "salary"),
    "T06": ("salary_amount_change", "next_payment_only", "salary"),
    "T07": ("salary_amount_change", "permanent", "salary"),
    "T08": ("income_ended", None, "salary"),
    "T09": ("salary_amount_change", "permanent", "salary"),
    "T10": ("salary_amount_change", "permanent", "salary"),  # first salary: series starts on date
    "T11": ("salary_amount_change", "permanent", "salary"),
    "T12": ("salary_amount_change", "permanent", "salary"),
    "T13": ("salary_amount_change", "next_payment_only", "salary"),  # foreign salary confirmed
    "T14": ("one_time_confirmed_income", None, "salary"),  # arrears + regular amount
    "T15": ("salary_amount_change", "permanent", "salary"),
    "T16": ("income_ended", None, "salary"),
    "T17": ("no_effect", None, "none"),
    "T18": ("pending_credit_not_available", None, "credit"),
    "T19": ("expense_increase_percent", "permanent", "rent"),
    "T20": ("one_time_confirmed_income", None, "credit"),
    "T21": ("no_effect", None, "none"),
    "T22": ("salary_amount_change", "next_payment_only", "salary"),
    "T23": ("internal_transfer_ignore", None, "none"),
    "T24": ("payment_delayed", None, "other_expense"),
    "T25": ("dispute_ignore", None, "none"),
    "T26": ("no_effect", None, "none"),
    "T27": ("pending_credit_not_available", None, "credit"),
    "T28": ("pending_credit_not_available", None, "credit"),
    "T29": ("no_effect", None, "none"),
    "T30": ("no_effect", None, "none"),
    "T31": ("no_effect", None, "none"),
    "T32": ("pending_credit_not_available", None, "credit"),
    "T33": ("no_effect", None, "none"),
    "T34": ("no_effect", None, "none"),
    "T35": ("scam_ignore", None, "none"),
}

MONTHS = {
    m: i
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], start=1
    )
}
MONTHS_ID = {
    m: i
    for i, m in enumerate(
        ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober", "november", "desember"], start=1
    )
}


def _long_date(s: str | None) -> str | None:
    if not s:
        return None
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s.strip())
    if not m:
        return None
    day, mon, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    mi = MONTHS.get(mon) or MONTHS_ID.get(mon)
    if not mi:
        return None
    return f"{year:04d}-{mi:02d}-{day:02d}"


_compiled = None


def _templates():
    global _compiled
    if _compiled is None:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _compiled = []
        for tid, t in raw.items():
            pats = [re.compile(p, re.S) for p in (t.get("pattern_en"), t.get("pattern_id")) if p]
            _compiled.append((tid, pats))
    return _compiled


def parse_message(text: str) -> dict | None:
    """Return {template_id, amount, amount2, currency, date, percent} or None."""
    for tid, pats in _templates():
        for p in pats:
            m = p.search(text)
            if m:
                g = m.groupdict()
                date = g.get("date")
                if not date and g.get("date_long"):
                    date = _long_date(g.get("date_long"))
                return {
                    "template_id": tid,
                    "amount": float(g["amount"]) if g.get("amount") else None,
                    "amount2": float(g["amount2"]) if g.get("amount2") else None,
                    "currency": g.get("currency") or g.get("currency2"),
                    "date": date,
                    "percent": float(g["percent"]) if g.get("percent") else None,
                }
    return None


def regex_adjustment(message) -> dict:
    """Unified adjustment record for one data.Message using the regex templates."""
    parsed = parse_message(message.message_text)
    rec = {
        "message_id": message.message_id,
        "user_id": message.user_id,
        "request_id": message.request_id,
        "related_event_id": message.related_event_id,
        "sent_at": message.sent_at.date().isoformat(),
        "source_type": message.source_type,
        "source": "regex",
        "template_id": None,
        "adjustment_type": "no_effect",
        "scope": None,
        "target": "none",
        "amount": None,
        "currency": None,
        "effective_date": None,
        "percent": None,
        "regular_salary_amount": None,
        "contains_instructions": False,
        "summary": "",
    }
    if parsed is None:
        rec["adjustment_type"] = "no_effect"
        rec["summary"] = "unrecognised message; no effect"
        return rec
    tid = parsed["template_id"]
    atype, scope, target = TEMPLATE_MAP[tid[:3]]
    rec.update(template_id=tid, adjustment_type=atype, scope=scope, target=target)
    rec["currency"] = parsed["currency"]
    rec["effective_date"] = parsed["date"]
    rec["percent"] = parsed["percent"]
    if tid.startswith("T14"):
        rec["amount"] = parsed["amount2"]
        rec["regular_salary_amount"] = parsed["amount"]
    else:
        rec["amount"] = parsed["amount"]
    if tid.startswith("T35"):
        rec["contains_instructions"] = True
    rec["summary"] = tid
    return rec


def normalize_model_adjustment(message, res: dict) -> dict:
    """Bring a model extraction (evidence.MESSAGE_SCHEMA) into the unified shape."""
    rec = regex_adjustment(message)  # start from the regex view for the metadata fields
    rec["source"] = "model"
    rec["adjustment_type"] = res.get("adjustment_type") or "no_effect"
    rec["scope"] = res.get("scope") if res.get("scope") in ("permanent", "next_payment_only") else None
    rec["target"] = res.get("target") or "none"
    rec["amount"] = res.get("amount")
    rec["currency"] = res.get("currency")
    rec["effective_date"] = res.get("effective_date")
    rec["percent"] = res.get("percent")
    rec["regular_salary_amount"] = res.get("regular_salary_amount")
    rec["contains_instructions"] = bool(res.get("contains_instructions"))
    rec["summary"] = res.get("summary") or ""
    return rec
