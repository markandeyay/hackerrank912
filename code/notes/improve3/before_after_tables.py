import sys
from pathlib import Path
CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR)); sys.path.insert(0, str(CODE_DIR / "notes" / "improve3"))
from data import Dataset
from pipeline import load_adjustments, load_image_amounts
from occurrence_counts import COLS, score, r_skip_rq_plus, r_payday_window, chain
ds = Dataset(); reqs = ds.load_requests("sample_requests.csv")
images, adjs = load_image_amounts(ds, True), load_adjustments(ds, True)
variants = [("baseline", None), ("A1 skip rq+1", r_skip_rq_plus(1)), ("E8 weekly on payday/+1 before salary", r_payday_window(2, min_gap=7, max_gap=7)), ("A1+E8", chain(r_skip_rq_plus(1), r_payday_window(2, min_gap=7, max_gap=7)))]
res = {n: score(ds, images, adjs, reqs, r) for n, r in variants}
print("| sample | want | " + " | ".join(n for n, _ in variants) + " | cols (base / A1+E8) |")
print("|---|---|" + "---|" * len(variants) + "---|")
tot = {n: [0, 0, 0] for n, _ in variants}
for req in reqs:
    exp = req.expected; want = float(exp["amount_safe_to_pay"])
    prof = ds.profiles[req.user_id]; head = prof.current_available_balance - prof.minimum_balance_to_keep
    cells = []
    for n, _ in variants:
        row = res[n][req.request_id]; got = float(row["amount_safe_to_pay"])
        res_err = 100 * (want - got) / (head - want) if head - want > 0 else 0.0
        w2 = abs(got - want) <= 0.02 * max(1.0, want)
        nm = sum(1 for c in COLS[1:] if row[c] == exp[c])
        tot[n][0] += nm; tot[n][1] += w2; tot[n][2] += (row["amount_safe_to_pay"] == exp["amount_safe_to_pay"])
        cells.append(f"{got:,.2f} ({res_err:+.2f}%){' *' if w2 else ''}")
    b = sum(1 for c in COLS[1:] if res["baseline"][req.request_id][c] == exp[c]); a = sum(1 for c in COLS[1:] if res["A1+E8"][req.request_id][c] == exp[c])
    print(f"| {req.request_id} | {want:,.2f} | " + " | ".join(cells) + f" | {b}/5 / {a}/5 |")
print("| **non-amount cells / within 2 % / exact amounts** | | " + " | ".join(f"{tot[n][0]}/125 / {tot[n][1]}/25 / {tot[n][2]}/25" for n, _ in variants) + " | |")
