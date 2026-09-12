"""Independent cross-column invariant audit of output.csv (stricter than code/validate.py).

Run:  .venv/Scripts/python code/notes/improve/audit_invariants.py [output.csv]
Prints a table of invariant -> violation count, then every violation, then warnings
(intentional-policy cases) and the amount_safe_to_pay == 0 roster.
Exit code 1 when any violation is found.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "code"))
from data import Dataset, parse_date  # noqa: E402

COLUMNS = ["request_id", "amount_safe_to_pay", "affordability_status", "recommended_payment_method",
           "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed", "decision_explanation"]
HORIZON = 84  # engine horizon (code/state.py HORIZON_DAYS)
EPS = 0.005  # 2-decimal tolerance
AMOUNT_RE = re.compile(r"^\d+(\.\d{2})?$")
SAFE_RE = re.compile(r"^\d+(\.\d{1,2})?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

INVARIANTS = [
    "header/column order",
    "one row per request / no duplicates",
    "amount_safe_to_pay range/format",
    "payment_plan parse/format",
    "earliest_date window",
    "affordable_now",
    "affordable_later",
    "affordable_with_plan",
    "not_affordable",
    "method in user's accepted methods",
    "full_payment plan",
    "partial_payment",
    "installments match option",
    "installments <= max_installment_months",
    "spending changes",
    "decision_explanation",
    "amount_safe_to_pay vs headroom",
]

violations: dict[str, list[str]] = defaultdict(list)
warnings: dict[str, list[str]] = defaultdict(list)


def V(inv: str, rid: str, msg: str) -> None:
    violations[inv].append(f"{rid}: {msg}")


def W(inv: str, rid: str, msg: str) -> None:
    warnings[inv].append(f"{rid}: {msg}")


def fmt_amount(x: float) -> str:
    """Amount formatting used by the engine: integer when whole, else up to 2 decimals."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def parse_plan(s: str):
    if s == "none":
        return []
    out = []
    for part in s.split("|"):
        if ":" not in part:
            return None
        d, a = part.split(":", 1)
        if not DATE_RE.match(d):
            return None
        dd = parse_date(d)
        out.append((dd, a))
    return out


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "output.csv"
    ds = Dataset()
    reqs = {r.request_id: r for r in ds.load_requests("requests.csv")}

    with open(target, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw_rows = list(reader)
    if header != COLUMNS:
        V("header/column order", "-", f"header is {header}")
    rows = [dict(zip(COLUMNS, r)) for r in raw_rows]
    for r, raw in zip(rows, raw_rows):
        if len(raw) != len(COLUMNS):
            V("header/column order", r.get("request_id", "?"), f"row has {len(raw)} fields")

    ids = [r["request_id"] for r in rows]
    for rid, n in Counter(ids).items():
        if n > 1:
            V("one row per request / no duplicates", rid, f"appears {n} times")
    for rid in ids:
        if rid not in reqs:
            V("one row per request / no duplicates", rid, "not in requests.csv")
    for rid in sorted(set(reqs) - set(ids)):
        V("one row per request / no duplicates", rid, "missing from output.csv")

    zero_rows = []
    for row in rows:
        rid = row["request_id"]
        if rid not in reqs:
            continue
        req = reqs[rid]
        prof = ds.profiles[req.user_id]
        status, method = row["affordability_status"], row["recommended_payment_method"]
        safe_s = row["amount_safe_to_pay"]
        changes_s = row["spending_changes_needed"]
        edate_s = row["earliest_date_for_full_payment"]
        edate = parse_date(edate_s) if DATE_RE.match(edate_s or "") else None
        try:
            safe = float(safe_s)
        except ValueError:
            V("amount_safe_to_pay range/format", rid, f"non-numeric {safe_s!r}")
            continue
        RA = req.requested_amount
        RD = req.request_date
        DCD = req.desired_completion_date

        # ---- range / formatting ----
        if not (0 <= safe <= RA + EPS):
            V("amount_safe_to_pay range/format", rid, f"safe={safe_s} outside [0, {RA}]")
        if not SAFE_RE.match(safe_s):
            V("amount_safe_to_pay range/format", rid, f"safe={safe_s!r} has >2 decimals or bad format")

        plan = parse_plan(row["payment_plan"])
        if plan is None:
            V("payment_plan parse/format", rid, f"unparsable {row['payment_plan']!r}")
            plan = []
        for _, a in plan:
            if not AMOUNT_RE.match(a):
                V("payment_plan parse/format", rid, f"amount {a!r} must have 0 or exactly 2 decimals")
        pdates = [d for d, _ in plan]
        if pdates != sorted(pdates):
            V("payment_plan parse/format", rid, "plan not chronological")
        pamts = []
        for _, a in plan:
            try:
                pamts.append(float(a))
            except ValueError:
                pamts.append(float("nan"))

        # ---- earliest date ----
        if edate_s and edate is None:
            V("earliest_date window", rid, f"bad date {edate_s!r}")
        if edate is not None:
            if not (RD <= edate <= RD + timedelta(days=HORIZON)):
                V("earliest_date window", rid, f"earliest={edate} outside {RD}..{RD + timedelta(days=HORIZON)}")
            if status != "affordable_now" and edate <= RD:
                # Statement: earliest_date measures capacity independently of preferences and may equal
                # request_date when the user does not consider full_payment. Only a violation otherwise.
                if "full_payment" in prof.methods:
                    V("earliest_date window", rid, f"status={status} but earliest={edate} <= request_date {RD} and user accepts full_payment")
                else:
                    W("earliest_date == request_date while status != affordable_now (user rejects full_payment; statement-sanctioned)", rid,
                      f"status={status} method={method} methods={prof.methods}")

        # ---- status-specific ----
        if status == "affordable_now":
            if method != "full_payment":
                V("affordable_now", rid, f"method={method}")
            # organizer sample formats decimals as exactly 2 places (2026-01-03:620.40) and whole amounts bare
            if len(plan) != 1 or plan[0][0] != RD or abs(pamts[0] - RA) > EPS:
                V("affordable_now", rid, f"plan={row['payment_plan']!r} expected {RD}:{fmt_amount(RA)}")
            if edate != RD:
                V("affordable_now", rid, f"earliest={edate_s!r} != request_date {RD}")
            if changes_s != "none":
                V("affordable_now", rid, f"changes={changes_s!r}")
            if abs(safe - RA) > EPS:
                V("affordable_now", rid, f"safe={safe_s} != requested {RA}")
        elif status == "affordable_later":
            if method != "wait":
                V("affordable_later", rid, f"method={method}")
            if edate is None:
                V("affordable_later", rid, "earliest_date empty")
            elif edate <= RD:
                V("affordable_later", rid, f"earliest={edate} not > request_date {RD}")
            ok_plan = len(plan) == 1 and edate is not None and plan[0][0] == edate and abs(pamts[0] - RA) <= EPS
            if not ok_plan:
                V("affordable_later", rid, f"plan={row['payment_plan']!r} expected single {edate_s}:{fmt_amount(RA)}")
            if changes_s != "none":
                V("affordable_later", rid, f"changes={changes_s!r}")
            if edate is not None and edate > DCD:
                W("affordable_later: earliest after desired_completion_date (intentional engine policy)", rid,
                  f"earliest={edate} > desired={DCD} (request_date={RD}, safe={safe_s}, requested={fmt_amount(RA)}, "
                  f"methods={prof.methods}, partial_allowed={req.allows_partial_payment}, max_m={prof.max_installment_months})")
        elif status == "affordable_with_plan":
            has_changes = changes_s != "none"
            if method == "full_payment":
                if not has_changes:
                    V("affordable_with_plan", rid, "full_payment without spending changes")
            elif method not in ("partial_payment", "installments"):
                V("affordable_with_plan", rid, f"method={method}")
            if plan:
                last = max(pdates)
                if last > DCD:
                    V("affordable_with_plan", rid, f"last payment {last} > desired_completion_date {DCD} (method={method})")
            else:
                V("affordable_with_plan", rid, "plan is none")
        elif status == "not_affordable":
            if method != "not_recommended":
                V("not_affordable", rid, f"method={method}")
            if row["payment_plan"] != "none":
                V("not_affordable", rid, f"plan={row['payment_plan']!r}")
            if changes_s != "none":
                V("not_affordable", rid, f"changes={changes_s!r}")
        else:
            V("affordable_now", rid, f"unknown status {status!r}")

        # ---- method-specific ----
        if method in ("full_payment", "partial_payment", "installments"):
            if method not in prof.methods:
                V("method in user's accepted methods", rid, f"{method} not in {prof.methods}")
        elif method == "wait":
            if "full_payment" not in prof.methods:
                V("method in user's accepted methods", rid, f"wait but full_payment not in {prof.methods}")
        elif method != "not_recommended":
            V("method in user's accepted methods", rid, f"unknown method {method!r}")

        if method == "partial_payment":
            if status != "affordable_with_plan":
                V("partial_payment", rid, f"status={status}")
            if len(plan) != 2:
                V("partial_payment", rid, f"{len(plan)} payments")
            else:
                (d1, _), (d2, _) = plan
                a1, a2 = pamts
                if d1 != RD:
                    V("partial_payment", rid, f"first date {d1} != request_date {RD}")
                if abs(a1 - safe) > EPS:
                    V("partial_payment", rid, f"first amount {a1} != safe {safe}")
                if edate is None or d2 != edate:
                    V("partial_payment", rid, f"second date {d2} != earliest {edate_s}")
                if abs(a1 + a2 - RA) > EPS:
                    V("partial_payment", rid, f"{a1}+{a2}={a1 + a2} != requested {RA}")
                if abs(a2 - (RA - safe)) > EPS:
                    V("partial_payment", rid, f"second amount {a2} != requested-safe {RA - safe}")
            if not req.allows_partial_payment:
                V("partial_payment", rid, "request does not allow partial payment")
            if not (EPS < safe < RA - EPS):
                V("partial_payment", rid, f"safe={safe} not strictly between 0 and {RA}")
            if edate is not None and edate > DCD:
                V("partial_payment", rid, f"earliest {edate} > desired {DCD}")
        elif method == "installments":
            if status != "affordable_with_plan":
                V("installments match option", rid, f"status={status}")
            opts = [o for o in ds.options_by_request.get(rid, []) if o.payment_method == "installments"]
            matched = None
            for o in opts:
                sched = o.schedule()
                if len(sched) != len(plan) or len(sched) != o.number_of_payments:
                    continue
                if all(sd == pd_ and abs(sa - pa) <= EPS for (sd, sa), (pd_, pa) in zip(sched, zip(pdates, pamts))):
                    matched = o
                    break
            if matched is None:
                V("installments match option", rid,
                  f"plan={row['payment_plan']!r} matches none of {[o.payment_option_id for o in opts]}")
            else:
                if prof.max_installment_months is None:
                    V("installments <= max_installment_months", rid,
                      f"{matched.payment_option_id} n={matched.number_of_payments} but max_installment_months blank")
                elif matched.number_of_payments > prof.max_installment_months:
                    V("installments <= max_installment_months", rid,
                      f"{matched.payment_option_id} n={matched.number_of_payments} > max {prof.max_installment_months}")
        elif method == "full_payment":
            if status not in ("affordable_now", "affordable_with_plan"):
                V("full_payment plan", rid, f"status={status}")
            if len(plan) != 1 or plan[0][0] != RD or abs(pamts[0] - RA) > EPS:
                V("full_payment plan", rid, f"plan={row['payment_plan']!r} expected {RD}:{fmt_amount(RA)}")
        elif method == "wait":
            if status != "affordable_later":
                V("affordable_later", rid, f"wait with status={status}")
        elif method == "not_recommended":
            if status != "not_affordable":
                V("not_affordable", rid, f"not_recommended with status={status}")

        # ---- spending changes ----
        if changes_s != "none":
            parts = changes_s.split("|")
            if len(parts) > 3:
                V("spending changes", rid, f"{len(parts)} entries > 3")
            if status != "affordable_with_plan":
                V("spending changes", rid, f"changes with status={status}")
            kinds: dict[str, set] = defaultdict(set)
            for p in parts:
                bits = p.split(":")
                if bits[0] == "stop" and len(bits) == 2:
                    kind, eid, new_amt = "stop", bits[1], None
                elif bits[0] == "reduce_to" and len(bits) == 3:
                    kind, eid = "reduce_to", bits[1]
                    try:
                        new_amt = float(bits[2])
                    except ValueError:
                        V("spending changes", rid, f"bad amount in {p!r}")
                        continue
                else:
                    V("spending changes", rid, f"malformed {p!r}")
                    continue
                kinds[eid].add(kind)
                ev = ds.events.get(eid)
                if ev is None:
                    V("spending changes", rid, f"{p}: unknown event")
                    continue
                if ev.user_id != req.user_id:
                    V("spending changes", rid, f"{p}: event belongs to {ev.user_id}, request user {req.user_id}")
                if ev.direction != "debit":
                    V("spending changes", rid, f"{p}: event is a {ev.direction}")
                if ev.category in prof.protect:
                    V("spending changes", rid, f"{p}: category {ev.category} protected")
                if kind == "stop":
                    if ev.flexibility not in ("stoppable", "reducible_or_stoppable"):
                        V("spending changes", rid, f"{p}: flexibility={ev.flexibility} not stoppable")
                    if ev.category not in prof.stop:
                        V("spending changes", rid, f"{p}: category {ev.category} not in willing_to_stop {prof.stop}")
                else:
                    if ev.flexibility not in ("reducible", "reducible_or_stoppable"):
                        V("spending changes", rid, f"{p}: flexibility={ev.flexibility} not reducible")
                    if ev.category not in prof.reduce:
                        V("spending changes", rid, f"{p}: category {ev.category} not in willing_to_reduce {prof.reduce}")
                    if ev.minimum_allowed_amount is None:
                        V("spending changes", rid, f"{p}: event has no minimum_allowed_amount")
                    elif abs(new_amt - ev.minimum_allowed_amount) > EPS:
                        V("spending changes", rid, f"{p}: new_amount {new_amt} != minimum_allowed_amount {ev.minimum_allowed_amount}")
            for eid, ks in kinds.items():
                if len(ks) > 1:
                    V("spending changes", rid, f"stop and reduce_to both on {eid}")

        # ---- explanation ----
        expl = row["decision_explanation"].strip()
        if not expl:
            V("decision_explanation", rid, "empty")
        elif prof.home_currency not in expl:
            V("decision_explanation", rid, f"does not mention currency {prof.home_currency}: {expl[:80]!r}")

        # ---- zero roster / headroom ----
        headroom = prof.current_available_balance - prof.minimum_balance_to_keep
        if safe == 0:
            nxt = None
            for e in ds.events_by_user[req.user_id]:
                if e.direction == "credit" and e.event_type in ("income", "salary") and e.settlement_date and e.settlement_date > RD:
                    if nxt is None or e.settlement_date < nxt:
                        nxt = e.settlement_date
            zero_rows.append((rid, req.user_id, headroom, RA, RD, status, method, nxt))
        elif headroom <= 0:
            V("amount_safe_to_pay vs headroom", rid, f"headroom {headroom:.2f} <= 0 but safe={safe_s}")

    # ---- report ----
    allkeys = INVARIANTS + sorted(set(violations) - set(INVARIANTS))
    print("INVARIANT VIOLATION TABLE")
    for k in allkeys:
        print(f"  {k:55s} {len(violations.get(k, [])):3d}")
    total = sum(len(v) for v in violations.values())
    print(f"  {'TOTAL':55s} {total:3d}")
    print("\nVIOLATIONS")
    for k in allkeys:
        for line in violations.get(k, []):
            print(f"  [{k}] {line}")
    print("\nWARNINGS (intentional engine policy, not counted as violations)")
    for k, lines in warnings.items():
        print(f"  {k}: {len(lines)}")
        for line in lines:
            print(f"    {line}")
    print("\nAMOUNT_SAFE_TO_PAY == 0 ROSTER")
    for rid, uid, hr, ra, rd, st, me, nxt in zero_rows:
        print(f"  {rid} {uid} headroom(balance-min)={hr:.2f} requested={fmt_amount(ra)} request_date={rd} "
              f"status={st} method={me} next_income_settlement_after_request(from events)={nxt}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
