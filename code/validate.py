"""Deterministic validation of output.csv against the problem-statement contract.

Run:  python code/validate.py [path/to/output.csv]
Exit code 0 when every row passes, 1 otherwise.  Also importable:
`validate_rows(rows, dataset) -> list[str]` returns the problems found.
"""
from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import REPO_ROOT, Dataset, parse_date  # noqa: E402

COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]
STATUSES = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
METHODS = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}
EPS = 0.011


def _num(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_plan(plan: str) -> list[tuple[date, float]] | None:
    if plan == "none":
        return []
    out = []
    for part in plan.split("|"):
        if ":" not in part:
            return None
        d, a = part.split(":", 1)
        dd, aa = parse_date(d) if len(d) == 10 else None, _num(a)
        if dd is None or aa is None:
            return None
        out.append((dd, aa))
    return out


def validate_rows(rows: list[dict], ds: Dataset, requests_file: str = "requests.csv") -> list[str]:
    problems: list[str] = []
    reqs = {r.request_id: r for r in ds.load_requests(requests_file)}
    seen = set()
    for i, row in enumerate(rows, start=2):
        rid = row.get("request_id", "")
        tag = f"row {i} ({rid})"
        if rid not in reqs:
            problems.append(f"{tag}: unknown request_id")
            continue
        if rid in seen:
            problems.append(f"{tag}: duplicate request_id")
        seen.add(rid)
        req = reqs[rid]
        prof = ds.profiles[req.user_id]

        safe = _num(row["amount_safe_to_pay"])
        if safe is None:
            problems.append(f"{tag}: amount_safe_to_pay not numeric")
            continue
        if not (-EPS <= safe <= req.requested_amount + EPS):
            problems.append(f"{tag}: amount_safe_to_pay {safe} outside [0, {req.requested_amount}]")

        status = row["affordability_status"]
        method = row["recommended_payment_method"]
        if status not in STATUSES:
            problems.append(f"{tag}: bad status {status!r}")
        if method not in METHODS:
            problems.append(f"{tag}: bad method {method!r}")

        plan = parse_plan(row["payment_plan"])
        if plan is None:
            problems.append(f"{tag}: unparsable payment_plan {row['payment_plan']!r}")
            plan = []
        dates = [d for d, _ in plan]
        if dates != sorted(dates):
            problems.append(f"{tag}: payment_plan not chronological")

        earliest = row["earliest_date_for_full_payment"].strip()
        edate = parse_date(earliest) if earliest else None
        if earliest and edate is None:
            problems.append(f"{tag}: bad earliest_date {earliest!r}")
        if status == "affordable_now" and edate != req.request_date:
            problems.append(f"{tag}: affordable_now requires earliest_date == request_date")
        if status == "affordable_now" and safe + EPS < req.requested_amount:
            problems.append(f"{tag}: affordable_now but amount_safe_to_pay < requested_amount")

        # method / status / plan consistency
        if method in ("full_payment", "partial_payment", "installments") and method not in prof.methods:
            problems.append(f"{tag}: method {method} not in user's accepted methods {prof.methods}")
        if method == "wait" and "full_payment" not in prof.methods:
            problems.append(f"{tag}: wait requires the user to accept full_payment")
        if method == "full_payment":
            has_changes = row["spending_changes_needed"].strip() != "none"
            if status == "affordable_with_plan" and not has_changes:
                problems.append(f"{tag}: full_payment with affordable_with_plan requires spending changes")
            elif status not in ("affordable_now", "affordable_with_plan"):
                problems.append(f"{tag}: full_payment must be affordable_now or affordable_with_plan")
            if len(plan) != 1 or plan[0][0] != req.request_date or abs(plan[0][1] - req.requested_amount) > EPS:
                problems.append(f"{tag}: full_payment plan must be request_date:requested_amount")
        elif method == "partial_payment":
            if status != "affordable_with_plan":
                problems.append(f"{tag}: partial_payment must be affordable_with_plan")
            if not req.allows_partial_payment:
                problems.append(f"{tag}: request does not allow partial payment")
            if not (EPS < safe < req.requested_amount - EPS):
                problems.append(f"{tag}: partial_payment needs 0 < safe < requested")
            if len(plan) != 2:
                problems.append(f"{tag}: partial_payment needs exactly two payments")
            else:
                (d1, a1), (d2, a2) = plan
                if d1 != req.request_date or abs(a1 - safe) > EPS:
                    problems.append(f"{tag}: first partial payment must be request_date:amount_safe_to_pay")
                if edate is None or d2 != edate:
                    problems.append(f"{tag}: second partial payment must be on earliest_date_for_full_payment")
                if abs(a2 - (req.requested_amount - safe)) > EPS or abs(a1 + a2 - req.requested_amount) > EPS:
                    problems.append(f"{tag}: partial payments must add up to requested_amount")
                if edate is not None and edate > req.desired_completion_date:
                    problems.append(f"{tag}: second partial payment after desired_completion_date")
        elif method == "installments":
            if status != "affordable_with_plan":
                problems.append(f"{tag}: installments must be affordable_with_plan")
            opts = [o for o in ds.options_by_request.get(rid, []) if o.payment_method == "installments"]
            matched = None
            for o in opts:
                sched = o.schedule()
                if len(sched) == len(plan) and all(sd == pd and abs(sa - pa) <= EPS for (sd, sa), (pd, pa) in zip(sched, plan)):
                    matched = o
                    break
            if matched is None:
                problems.append(f"{tag}: installment plan does not match any supplied option")
            elif prof.max_installment_months is not None:
                # supplied options are monthly cadences (28/30/31 days): one payment == one month
                if matched.number_of_payments > prof.max_installment_months:
                    problems.append(f"{tag}: {matched.number_of_payments} installments exceed max {prof.max_installment_months} months")
            elif prof.max_installment_months is None:
                problems.append(f"{tag}: user will not consider installments (blank max_installment_months)")
        elif method == "wait":
            if status != "affordable_later":
                problems.append(f"{tag}: wait must be affordable_later")
            if edate is None:
                problems.append(f"{tag}: wait needs an earliest_date_for_full_payment")
            if plan and not (len(plan) == 1 and plan[0][0] == edate and abs(plan[0][1] - req.requested_amount) <= EPS):
                problems.append(f"{tag}: wait plan should be none or the single full payment on the earliest date")
        elif method == "not_recommended":
            if status != "not_affordable":
                problems.append(f"{tag}: not_recommended must be not_affordable")
            if plan:
                problems.append(f"{tag}: not_recommended plan must be none")

        # spending changes
        sc = row["spending_changes_needed"].strip()
        if sc != "none":
            parts = sc.split("|")
            if len(parts) > 3:
                problems.append(f"{tag}: more than three spending changes")
            touched: dict[str, str] = {}
            for p in parts:
                bits = p.split(":")
                if bits[0] == "stop" and len(bits) == 2:
                    eid, kind, new_amt = bits[1], "stop", None
                elif bits[0] == "reduce_to" and len(bits) == 3:
                    eid, kind, new_amt = bits[1], "reduce_to", _num(bits[2])
                    if new_amt is None:
                        problems.append(f"{tag}: bad reduce_to amount in {p!r}")
                else:
                    problems.append(f"{tag}: bad spending change {p!r}")
                    continue
                if eid in touched and touched[eid] != kind:
                    problems.append(f"{tag}: stop and reduce_to on the same event {eid}")
                touched[eid] = kind
                ev = ds.events.get(eid)
                if ev is None or ev.user_id != req.user_id:
                    problems.append(f"{tag}: spending change references unknown/foreign event {eid}")
                    continue
                if ev.flexibility not in ("stoppable", "reducible", "reducible_or_stoppable") or ev.direction != "debit":
                    problems.append(f"{tag}: spending change on non-flexible event {eid}")
                if kind == "stop" and ev.flexibility not in ("stoppable", "reducible_or_stoppable"):
                    problems.append(f"{tag}: event {eid} is not stoppable")
                if kind == "reduce_to" and ev.flexibility not in ("reducible", "reducible_or_stoppable"):
                    problems.append(f"{tag}: event {eid} is not reducible")
                if kind == "reduce_to" and ev.minimum_allowed_amount is not None and new_amt is not None and new_amt + EPS < ev.minimum_allowed_amount:
                    problems.append(f"{tag}: reduce_to below minimum_allowed_amount for {eid}")
                if ev.category in prof.protect:
                    problems.append(f"{tag}: spending change on protected category {ev.category}")
                if kind == "stop" and ev.category not in prof.stop:
                    problems.append(f"{tag}: user not willing to stop category {ev.category}")
                if kind == "reduce_to" and ev.category not in prof.reduce:
                    problems.append(f"{tag}: user not willing to reduce category {ev.category}")
            if status != "affordable_with_plan":
                problems.append(f"{tag}: spending changes only allowed with affordable_with_plan")
        if not row["decision_explanation"].strip():
            problems.append(f"{tag}: empty decision_explanation")

    missing = set(reqs) - seen
    if missing:
        problems.append(f"missing {len(missing)} request ids: {sorted(missing)[:5]}...")
    return problems


def validate_file(path: Path, requests_file: str = "requests.csv") -> list[str]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            return [f"header mismatch: {reader.fieldnames}"]
        rows = list(reader)
    ds = Dataset()
    return validate_rows(rows, ds, requests_file)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "output.csv"
    reqfile = sys.argv[2] if len(sys.argv) > 2 else "requests.csv"
    probs = validate_file(target, reqfile)
    if probs:
        print(f"{len(probs)} problem(s) in {target}:")
        for p in probs:
            print(" -", p)
        sys.exit(1)
    print(f"{target}: all rows valid")
