"""Glue: dataset -> evidence -> state -> decision -> output rows."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

from data import Dataset, Request  # noqa: E402
from explain import template_explanation  # noqa: E402
from planner import Decision, decide  # noqa: E402
from state import HORIZON_DAYS, StateBuilder, fmt_amount  # noqa: E402

MANUAL_IMAGES = CODE_DIR / "notes" / "02_images_manual.json"


def fmt_safe(x: float) -> str:
    x = round(x + 1e-9, 2)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return repr(x)


def load_image_amounts(ds: Dataset, use_llm: bool, force: bool = False) -> dict[str, float]:
    """event_id -> amount for blank-amount events.  Model extraction (cached)
    when available; otherwise the manually transcribed fallback in notes/."""
    out: dict[str, float] = {}
    if use_llm:
        from evidence import image_amounts

        for image_id, res in image_amounts(ds, force=force).items():
            if res.get("event_id") and res.get("amount") is not None:
                out[res["event_id"]] = float(res["amount"])
        return out
    if MANUAL_IMAGES.exists():
        with open(MANUAL_IMAGES, "r", encoding="utf-8") as f:
            man = json.load(f)
        for v in man.values():
            if v.get("event_id") and v.get("amount") is not None:
                out[v["event_id"]] = float(v["amount"])
    return out


def load_adjustments(ds: Dataset, use_llm: bool, force: bool = False) -> dict[str, list[dict]]:
    """user_id -> unified adjustment records."""
    from messages_regex import normalize_model_adjustment, regex_adjustment

    by_user: dict[str, list[dict]] = {}
    model_res: dict[str, dict] = {}
    if use_llm:
        from evidence import message_adjustments

        model_res = message_adjustments(ds, force=force)
    for m in ds.messages:
        if m.message_id in model_res:
            rec = normalize_model_adjustment(m, model_res[m.message_id])
            rx = regex_adjustment(m)
            # the regex view is exact for the templated dataset; keep the model's
            # classification but fill fields it left empty
            for k in ("amount", "currency", "effective_date", "percent", "scope", "regular_salary_amount", "template_id"):
                if rec.get(k) in (None, "") and rx.get(k) not in (None, ""):
                    rec[k] = rx[k]
            if rec["adjustment_type"] != rx["adjustment_type"]:
                rec["regex_adjustment_type"] = rx["adjustment_type"]
        else:
            rec = regex_adjustment(m)
        by_user.setdefault(m.user_id, []).append(rec)
    return by_user


def decision_row(dec: Decision, explanation: str) -> dict:
    plan = dec.plan
    earliest = dec.earliest.isoformat() if dec.earliest else ""
    if plan.status == "affordable_now":
        earliest = dec.request.request_date.isoformat()
    return {
        "request_id": dec.request.request_id,
        "amount_safe_to_pay": fmt_safe(dec.safe_amount),
        "affordability_status": plan.status,
        "recommended_payment_method": plan.method,
        "payment_plan": plan.plan_string(),
        "earliest_date_for_full_payment": earliest,
        "spending_changes_needed": plan.changes_string(),
        "decision_explanation": explanation,
    }


def run(requests: list[Request], ds: Dataset, use_llm: bool, horizon_days: int = HORIZON_DAYS, polish: bool = False, options: dict | None = None) -> list[tuple[Decision, dict]]:
    images = load_image_amounts(ds, use_llm)
    adjs = load_adjustments(ds, use_llm)
    builder = StateBuilder(ds, images, adjs, horizon_days=horizon_days, options=options)
    out = []
    for req in requests:
        st = builder.build(req)
        dec = decide(st, ds.options_by_request.get(req.request_id, []))
        text = template_explanation(dec)
        if polish and use_llm:
            from polish import polish_explanation

            text = polish_explanation(dec, text)
        out.append((dec, decision_row(dec, text)))
    return out
