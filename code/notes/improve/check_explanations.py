"""Check every decision_explanation in output.csv against its row, the dataset and the
sample style (dataset/sample_requests.csv).  Read-only; prints defects and a summary.

Run:  .venv/Scripts/python code/notes/improve/check_explanations.py [--csv output.csv] [--json out.json] [--show-polished]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DS = ROOT / "dataset"

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
CUR_AMT_RE = re.compile(r"\b([A-Z]{3}) (\d(?:[\d,]*\d)?(?:\.\d+)?)")
DATE_RE = re.compile(r"\b(\d{1,2}) (" + MONTHS + r") (\d{4})\b")
NUM_RE = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")


def fmt_amount(x: float) -> str:
    x = round(x + 1e-9, 2)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}"


def money(cur: str, x: float) -> str:
    s = fmt_amount(x)
    if "." in s:
        whole, frac = s.split(".")
        return f"{cur} {int(whole):,}.{frac}"
    return f"{cur} {int(s):,}"


def longdate(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def cache_key(*parts) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(json.dumps(part, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:24]


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_plan(s: str) -> list[tuple[date, float]]:
    if not s or s == "none":
        return []
    out = []
    for part in s.split("|"):
        d, a = part.split(":")
        out.append((date.fromisoformat(d), float(a)))
    return out


def parse_changes(s: str) -> list[tuple[str, str, float | None]]:
    if not s or s == "none":
        return []
    out = []
    for part in s.split("|"):
        bits = part.split(":")
        if bits[0] == "stop":
            out.append(("stop", bits[1], None))
        else:
            out.append(("reduce_to", bits[1], float(bits[2])))
    return out


def build_template(row, req, prof, opts, events) -> tuple[str, dict]:
    """Reconstruct explain.template_explanation from the output row + dataset (no engine)."""
    cur = prof["home_currency"]
    mn = money(cur, float(prof["minimum_balance_to_keep"]))
    amt = money(cur, float(req["requested_amount"]))
    m = row["recommended_payment_method"]
    plan = parse_plan(row["payment_plan"])
    changes = parse_changes(row["spending_changes_needed"])
    desired = date.fromisoformat(req["desired_completion_date"])
    safe = float(row["amount_safe_to_pay"])
    info = {"cur": cur, "plan": plan, "changes": changes, "desired": desired, "safe": safe}

    def parts_of(changes):
        ps = []
        for act, eid, new in changes:
            desc = events[eid]["description"].lower()
            ps.append(f"stop the {desc}" if act == "stop" else f"reduce the {desc} to {money(cur, new)}")
        return ps

    if m == "full_payment" and not changes:
        return f"Pay {amt} today. This leaves at least {mn} available over the next 90 days.", info
    if m == "full_payment":
        parts = parts_of(changes)
        lead = " and ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + " and " + parts[-1]
        lead = lead[0].upper() + lead[1:]
        return f"{lead}, then pay {amt} today. This leaves at least {mn} available.", info
    if m == "installments":
        o = None
        for cand in opts:
            if cand["payment_method"] != "installments":
                continue
            if (
                plan
                and int(cand["number_of_payments"]) == len(plan)
                and date.fromisoformat(cand["first_payment_date"]) == plan[0][0]
                and abs(float(cand["payment_amount"]) - plan[0][1]) < 0.011
            ):
                o = cand
                break
        info["option"] = o
        if o is None:
            return "<<no matching installment option>>", info
        n = int(o["number_of_payments"])
        pa = money(cur, float(o["payment_amount"]))
        fd = longdate(date.fromisoformat(o["first_payment_date"]))
        if changes:
            lead = " and ".join(parts_of(changes))
            return lead[0].upper() + lead[1:] + f", then use {n} installments of {pa}, starting {fd}. This keeps the {mn} minimum protected.", info
        return f"Use {n} installments of {pa}, starting {fd}. This leaves at least {mn} available.", info
    if m == "partial_payment":
        (d1, a1), (d2, a2) = plan
        return f"Pay {money(cur, a1)} today and the remaining {money(cur, a2)} on {longdate(d2)}. This completes the full request and keeps the {mn} minimum protected.", info
    if m == "wait":
        d = plan[0][0]
        if d <= desired:
            return f"Pay {amt} in full on {longdate(d)}. Paying earlier would take the balance below the {mn} minimum.", info
        return f"Wait until {longdate(d)}, then pay {amt} in full. This is after the {longdate(desired)} target, but paying sooner would put the {mn} minimum at risk.", info
    # not_recommended
    methods = prof["payment_methods_user_will_consider"].split("|")
    if safe > 0 and req["allows_partial_payment"].strip().lower() == "true" and "partial_payment" in methods:
        return f"Do not proceed with the {amt} request. Although {money(cur, safe)} is available today, the full amount cannot be completed safely within 90 days.", info
    return f"Do not make this payment by {longdate(desired)}. None of the available options keeps the {mn} minimum protected.", info


D = r"\d{1,2} [A-Z][a-z]+ \d{4}"
A = r"[A-Z]{3} [\d,.]+"
# Sentence patterns per (method, has_changes), loosely following the samples.
PATTERNS = {
    ("full_payment", False): [re.compile(rf"^Pay {A} today[.,]")],
    ("full_payment", True): [re.compile(rf"^(Stop|Reduce) the .+?, then pay {A} today")],
    ("installments", False): [re.compile(rf"^Use \d+ installments of {A}, starting {D}")],
    ("installments", True): [re.compile(rf"^(Stop|Reduce) the .+?, then use \d+ installments of {A}, starting {D}")],
    ("partial_payment", False): [re.compile(rf"^Pay {A} today and the remaining {A} on {D}")],
    ("wait", False): [re.compile(rf"^Pay {A} in full on {D}"), re.compile(rf"^Wait until {D}, then pay {A} in full")],
    ("not_recommended", False): [
        re.compile(rf"^Do not make this payment by {D}\. None of the available options keeps the {A} minimum protected\.$"),
        re.compile(rf"^Do not proceed with the {A} request\. Although {A} is available today, the full amount cannot be completed safely within 90 days\.$"),
    ],
}


def check_row(row, req, prof, opts, events, cache) -> tuple[list[str], dict]:
    text = row["decision_explanation"]
    defects: list[str] = []
    template, info = build_template(row, req, prof, opts, events)
    cur, plan, changes, desired, safe = info["cur"], info["plan"], info["changes"], info["desired"], info["safe"]
    m = row["recommended_payment_method"]
    requested = float(req["requested_amount"])
    mn = float(prof["minimum_balance_to_keep"])

    polished = text != template
    in_cache = cache_key(row["request_id"], template) in cache
    meta = {"polished": polished, "template": template, "draft_in_cache": in_cache}
    if not in_cache:
        defects.append("reconstructed template not found in explanations cache (reconstruction differs from engine draft?)")

    # --- amounts
    allowed = {"requested": requested, "min_balance": mn, "safe": safe}
    if m == "partial_payment" and len(plan) == 2:
        allowed["remaining"] = plan[1][1]
    if m == "installments" and info.get("option"):
        allowed["installment"] = float(info["option"]["payment_amount"])
    for act, eid, new in changes:
        if act == "reduce_to":
            allowed[f"reduce_{eid}"] = new
    allowed_fmt = {money(cur, v): k for k, v in allowed.items()}
    if m == "full_payment":
        must = {money(cur, requested), money(cur, mn)}
    elif m == "installments" and info.get("option"):
        must = {money(cur, float(info["option"]["payment_amount"])), money(cur, mn)}
    elif m == "partial_payment":
        must = {money(cur, plan[0][1]), money(cur, plan[1][1]), money(cur, mn)}
    elif m == "wait":
        must = {money(cur, requested), money(cur, mn)}
    else:
        must = {money(cur, mn)} if "Do not make" in template else {money(cur, requested), money(cur, safe)}
    for act, eid, new in changes:
        if act == "reduce_to":
            must.add(money(cur, new))

    found_amts = []
    for c, num in CUR_AMT_RE.findall(text):
        s = f"{c} {num}"
        found_amts.append(s)
        if c != cur:
            defects.append(f"foreign currency code in text: {s} (home {cur})")
        if s not in allowed_fmt:
            try:
                v = float(num.replace(",", ""))
            except ValueError:
                v = None
            near = [k for k, val in allowed.items() if v is not None and abs(val - v) < 0.011]
            if near:
                defects.append(f"amount {s} mis-formatted (should be {money(cur, allowed[near[0]])})")
            else:
                defects.append(f"amount {s} not in allowed set {sorted(allowed_fmt)}")
    for s in must - set(found_amts):
        defects.append(f"missing required amount {s}")
    if cur not in text:
        defects.append("currency code not mentioned")

    # --- dates
    allowed_dates = {longdate(d) for d, _ in plan} | {longdate(desired)}
    if row["earliest_date_for_full_payment"]:
        allowed_dates.add(longdate(date.fromisoformat(row["earliest_date_for_full_payment"])))
    for d, mon, y in DATE_RE.findall(text):
        s = f"{d} {mon} {y}"
        if d.startswith("0"):
            defects.append(f"date with leading zero: {s}")
        if s not in allowed_dates:
            defects.append(f"date {s} not in allowed set {sorted(allowed_dates)}")
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", text):
        defects.append("ISO date in text")
    if m == "installments" and plan and longdate(plan[0][0]) not in text:
        defects.append(f"installment start date {longdate(plan[0][0])} not mentioned")
    if m == "partial_payment" and longdate(plan[1][0]) not in text:
        defects.append(f"second partial payment date {longdate(plan[1][0])} not mentioned")
    if m == "wait" and longdate(plan[0][0]) not in text:
        defects.append(f"wait payment date {longdate(plan[0][0])} not mentioned")
    if m == "wait" and plan[0][0] > desired and longdate(desired) not in text:
        defects.append(f"wait date is after desired {longdate(desired)} but target date not mentioned")

    # --- bare numbers (anything not inside a currency amount or a long date)
    stripped = DATE_RE.sub(" ", CUR_AMT_RE.sub(" ", text))
    for mo in NUM_RE.finditer(stripped):
        num = mo.group(0)
        after = stripped[mo.end():mo.end() + 14].strip()
        ok = False
        if num == "90" and after.startswith("days"):
            ok = True
        if m == "installments" and after.startswith("installment") and info.get("option") and int(info["option"]["number_of_payments"]) == int(num.replace(",", "")):
            ok = True
        if not ok:
            defects.append(f"bare number '{num}' followed by '{after}'")
    if m == "installments" and info.get("option"):
        n = int(info["option"]["number_of_payments"])
        if not re.search(rf"\b{n} installments\b", text):
            defects.append(f"installment count {n} not stated as '{n} installments'")
        if len(plan) != n:
            defects.append(f"payment_plan has {len(plan)} entries but option has {n}")

    # --- patterns
    pats = PATTERNS.get((m, bool(changes))) or PATTERNS[(m, False)]
    if not any(p.search(text) for p in pats):
        defects.append("sentence pattern does not match sample pattern for this method")
    if m == "wait" and plan and plan[0][0] > desired and not text.startswith("Wait until"):
        defects.append("wait past desired date should use 'Wait until D, then pay X in full' pattern")
    if m == "wait" and plan and plan[0][0] <= desired and text.startswith("Wait until"):
        defects.append("wait on/before desired date should use 'Pay X in full on D' pattern")

    # --- spending changes
    for act, eid, new in changes:
        desc = events[eid]["description"].lower()
        if desc not in text.lower():
            defects.append(f"change {act}:{eid} description '{desc}' not named")
        elif act == "stop" and not re.search(rf"stop(ping)? the {re.escape(desc)}", text, re.I):
            defects.append(f"stop change not phrased 'stop the {desc}'")
        elif act == "reduce_to" and not re.search(rf"reduc(e|ing) the {re.escape(desc)} to {re.escape(money(cur, new))}", text, re.I):
            defects.append(f"reduce change not phrased 'reduce the {desc} to {money(cur, new)}'")
    if changes and re.search(r"over the next 90 days", text):
        defects.append("'over the next 90 days' claim used although plan has spending changes")
    if not changes and re.search(r"\b(stop|reduce)\b", text, re.I):
        defects.append("mentions stop/reduce but no spending changes")

    # --- hygiene
    if re.search(r"[*_`#\[\]]", text):
        defects.append("markdown characters")
    if '"' in text or "'" in text or "’" in text or "“" in text:
        defects.append("quote character in text")
    if "  " in text:
        defects.append("double space")
    if len(text) > 300:
        defects.append(f"length {len(text)} > 300")
    if not text.endswith("."):
        defects.append("does not end with a period")
    if text != text.strip():
        defects.append("leading/trailing whitespace")
    if "\n" in text:
        defects.append("newline in text")
    sentences = [s for s in re.split(r"(?<=\.)\s+", text) if s]
    if len(sentences) > 3:
        defects.append(f"{len(sentences)} sentences (samples use 1-2)")
    if not text[0].isupper():
        defects.append("does not start with a capital letter")
    return defects, meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "output.csv"))
    ap.add_argument("--json", default=None, help="write per-row results here")
    ap.add_argument("--show-polished", action="store_true", help="print template vs polished text for every changed row")
    args = ap.parse_args()

    out_rows = read_csv(Path(args.csv))
    reqs = {r["request_id"]: r for r in read_csv(DS / "requests.csv")}
    profs = {r["user_id"]: r for r in read_csv(DS / "financial_profiles.csv")}
    events = {r["event_id"]: r for r in read_csv(DS / "financial_events.csv")}
    opts = defaultdict(list)
    for r in read_csv(DS / "request_payment_options.csv"):
        opts[r["request_id"]].append(r)
    cache_p = ROOT / "code" / "cache" / "explanations.json"
    cache = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}

    results = {}
    n_def = 0
    n_pol = 0
    kinds = Counter()
    for row in out_rows:
        rid = row["request_id"]
        req = reqs[rid]
        prof = profs[req["user_id"]]
        defects, meta = check_row(row, req, prof, opts[rid], events, cache)
        results[rid] = {"defects": defects, **meta, "text": row["decision_explanation"], "method": row["recommended_payment_method"], "changes": row["spending_changes_needed"]}
        n_pol += meta["polished"]
        if defects:
            n_def += 1
            tag = row["recommended_payment_method"] + (" +changes" if row["spending_changes_needed"] != "none" else "") + (" polished" if meta["polished"] else "")
            print(f"{rid} [{tag}]")
            print(f"   text:     {row['decision_explanation']}")
            if meta["polished"]:
                print(f"   template: {meta['template']}")
            for d in defects:
                print(f"   - {d}")
                kinds[re.split(r"[:']", d)[0][:60]] += 1
        if args.show_polished and meta["polished"] and not defects:
            print(f"{rid} [{row['recommended_payment_method']} polished, ok]\n   text:     {row['decision_explanation']}\n   template: {meta['template']}")
    print()
    print(f"rows={len(out_rows)} rows_with_defects={n_def} polished_rows={n_pol} template_rows={len(out_rows) - n_pol}")
    by_method = Counter((r["method"], r["polished"]) for r in results.values())
    for (mth, pol), c in sorted(by_method.items()):
        print(f"  {mth:18s} polished={pol!s:5s} {c}")
    print("defect kinds:")
    for k, c in kinds.most_common():
        print(f"  {c:3d}  {k}")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
