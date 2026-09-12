"""Scratch: test alternative periodic-series projection rules against all samples.
Does not modify the engine; patches StateBuilder._build_debit_series at runtime.
Run: .venv/Scripts/python code/notes/experiments/variants_request_06.py
"""
from __future__ import annotations
import statistics, sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE / "evaluation"))
import state as S
from state import Series, add_months
from data import Dataset
from pipeline import run
import importlib.util as _iu; _sp=_iu.spec_from_file_location("evalmain", CODE / "evaluation" / "main.py"); evalmain=_iu.module_from_spec(_sp); _sp.loader.exec_module(evalmain); score, table = evalmain.score, evalmain.table

VARIANT = {"mode": "last"}  # last | request | skip_rq1 | request_incl


def patched(self, st, hist, linked_targets, adjs):
    rq, end, home = st.request_date, st.horizon_end, st.home
    groups = defaultdict(list)
    for e in hist:
        if e.event_type in S.NON_RECURRING_TYPES or e.category in S.NON_RECURRING_CATEGORIES:
            continue
        if e.linked_event_id or e.event_id in linked_targets:
            continue
        sd = e.settlement_date or e.event_date
        if self.opt.get("exclude_image_rows_from_mean") and e.amount_source != "csv":
            continue
        groups[e.category].append((sd, self.to_home(self.amount_of(e), e.currency, home, sd), e))
    rent_pct = 0.0
    for a in adjs:
        if a["adjustment_type"] == "expense_increase_percent" and a.get("percent"):
            rent_pct = max(rent_pct, float(a["percent"]))
    for cat, rows in groups.items():
        rows.sort(key=lambda r: r[0])
        if len(rows) < 3:
            continue
        dates = [r[0] for r in rows]; amts = [r[1] for r in rows]
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        per = statistics.median(gaps)
        if per > 45:
            continue
        amount = statistics.mean(amts)
        if cat == "rent" and rent_pct:
            amount *= 1 + rent_pct / 100.0
        latest = rows[-1][2]
        proj = []
        if per >= 28:
            cadence, step = "monthly", 30
            t = add_months(dates[-1], 1)
            while t < rq:
                t = add_months(t, 1)
            while t <= end:
                proj.append(t); t = add_months(t, 1)
        else:
            cadence, step = "periodic", max(1, int(round(per)))
            mode = VARIANT["mode"]
            if mode == "last":
                t = dates[-1] + timedelta(days=step)
                while t <= rq:
                    t += timedelta(days=step)
            elif mode == "skip_rq1":
                t = dates[-1] + timedelta(days=step)
                while t <= rq + timedelta(days=1):
                    t += timedelta(days=step)
            elif mode == "request":
                t = rq + timedelta(days=step)
            elif mode == "request_incl":  # anchor at rq, include rq itself
                t = rq
            while t <= end:
                proj.append(t); t += timedelta(days=step)
        st.series.append(Series(cat, latest.description, amount, cadence, step, proj, latest.flexibility, latest.event_id, latest.minimum_allowed_amount, len(rows)))


S.StateBuilder._build_debit_series = patched

if __name__ == "__main__":
    ds = Dataset()
    reqs = ds.load_requests("sample_requests.csv")
    modes = sys.argv[1:] or ["last", "request", "skip_rq1"]
    for m in modes:
        VARIANT["mode"] = m
        print(f"\n===== periodic projection mode = {m} =====")
        res = run(reqs, ds, use_llm=True)
        table(res, ds)
        for k, v in score(res).items():
            print(f"{k:36s} {v}")
