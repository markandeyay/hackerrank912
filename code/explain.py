"""decision_explanation text in the style of sample_requests.csv."""
from __future__ import annotations

from datetime import date

from planner import Decision
from state import fmt_amount


def money(cur: str, x: float) -> str:
    s = fmt_amount(x)
    if "." in s:
        whole, frac = s.split(".")
        return f"{cur} {int(whole):,}.{frac}"
    return f"{cur} {int(s):,}"


def longdate(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def template_explanation(dec: Decision) -> str:
    req, st, plan = dec.request, dec.state, dec.plan
    cur = st.home
    mn = money(cur, st.min_balance)
    amt = money(cur, req.requested_amount)
    m = plan.method
    if m == "full_payment" and not plan.changes:
        return f"Pay {amt} today. This leaves at least {mn} available over the next 90 days."
    if m == "full_payment":
        parts = []
        for c in plan.changes:
            desc = c.series.description.lower()
            if c.action == "stop":
                parts.append(f"stop the {desc}")
            else:
                parts.append(f"reduce the {desc} to {money(cur, c.new_amount)}")
        lead = " and ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + " and " + parts[-1]
        lead = lead[0].upper() + lead[1:]
        return f"{lead}, then pay {amt} today. This leaves at least {mn} available."
    if m == "installments":
        o = plan.option
        s = f"Use {o.number_of_payments} installments of {money(cur, o.payment_amount)}, starting {longdate(o.first_payment_date)}. This leaves at least {mn} available."
        if plan.changes:
            parts = [f"stop the {c.series.description.lower()}" if c.action == "stop" else f"reduce the {c.series.description.lower()} to {money(cur, c.new_amount)}" for c in plan.changes]
            lead = " and ".join(parts)
            s = lead[0].upper() + lead[1:] + f", then use {o.number_of_payments} installments of {money(cur, o.payment_amount)}, starting {longdate(o.first_payment_date)}. This keeps the {mn} minimum protected."
        return s
    if m == "partial_payment":
        (d1, a1), (d2, a2) = plan.payments
        return f"Pay {money(cur, a1)} today and the remaining {money(cur, a2)} on {longdate(d2)}. This completes the full request and keeps the {mn} minimum protected."
    if m == "wait":
        d = plan.payments[0][0]
        if d <= req.desired_completion_date:
            return f"Pay {amt} in full on {longdate(d)}. Paying earlier would take the balance below the {mn} minimum."
        return f"Wait until {longdate(d)}, then pay {amt} in full. This is after the {longdate(req.desired_completion_date)} target, but paying sooner would put the {mn} minimum at risk."
    # not_recommended
    if dec.safe_amount > 0 and req.allows_partial_payment and "partial_payment" in st.profile.methods:
        return f"Do not proceed with the {amt} request. Although {money(cur, dec.safe_amount)} is available today, the full amount cannot be completed safely within 90 days."
    return f"Do not make this payment by {longdate(req.desired_completion_date)}. None of the available options keeps the {mn} minimum protected."
