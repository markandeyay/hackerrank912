"""Assemble 3_sensitivity.md from flip_summary.json / sweep_results.json plus the hand-written recommendations."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
S = {x["rid"]: x for x in json.load(open(OUT / "flip_summary.json"))}
SW = json.load(open(OUT / "sweep_results.json"))
THR = json.load(open(OUT / "thresholds_real.json"))

# rid -> (binding check described, margin currency, margin % of block, recommended value, justification)
# Margins quoted are at baseline (scale 1.0): positive = passes by that much, negative = misses by that much.
REC = {
    "request_49": ("earliest-date check on 2024-04-15 passes by IDR 742,693 (1.76%)", "keep installments, earliest 2024-05-15", "pass margin inside the band; later date is the safer capacity claim"),
    "request_53": ("no-change installments miss by USD 51.70 (1.81%); 1-change plan passes by 71.30 (2.49%)", "changes stop:event_4925|reduce_to:event_4992:44.50", "baseline change set is unsafe at 1.03; the 1.03 set avoids a plan that could miss"),
    "request_55": ("2-change plan passes by INR 4,267 (1.61%); earliest 07-15 misses by 5,274 (1.99%)", "earliest 2026-08-15 (keep); changes stop:event_5102|stop:event_5101|reduce_to:event_5167:2750", "earlier date unresolved -> later; base change set unsafe at 1.03 -> 1.03 set"),
    "request_59": ("no-change installments pass by INR 3,482 (1.40%)", "changes stop:event_5471", "no-change plan unsafe at 1.03 (misses by 3,970)"),
    "request_60": ("earliest 2026-01-15 misses by USD 0.20 (0.02%)", "keep wait, earliest 2026-02-15", "coin toss at 20 cents; rule says later date"),
    "request_68": ("1-change plan passes by USD 8.56 (0.33%); no-change misses by 21.44 (0.83%)", "changes stop:event_6330|reduce_to:event_6331:24.80, earliest 2025-04-23", "1.03 outcome: base set unsafe at 1.03 and earliest 03-23 passes by only 62 (2.4%)"),
    "request_77": ("full today with stop passes by INR 100.50 (0.08%); no-change full misses by 604.50 (0.47%)", "affordable_later / wait, plan 2025-11-15:60700, earliest 2025-11-15, changes none", "now vs later unresolved -> later; the stop-based full payment fails at 1.03 and the engine itself picks wait there"),
    "request_89": ("plan with first two changes misses by IDR 229,878 (1.14%)", "keep 3 changes", "third change only unnecessary at 0.97; keep the safer full set"),
    "request_92": ("no-change full today misses by ZAR 204.83 (0.38%)", "keep affordable_with_plan / full_payment with stop:event_8621|reduce_to:event_8620:558.80", "affordable_now only at 0.97; 2-change plan still safe at 1.03 (margin 504.67 - 96 > 0)"),
    "request_96": ("1-change plan passes by INR 142.50 (0.14%); earliest 02-15 passes by 1,425 (1.42%)", "changes stop:event_8914|reduce_to:event_8980:1610, earliest 2026-03-15", "1.03 outcome on both counts"),
    "request_97": ("plan with first change only misses by ZAR 72.71 (0.32%)", "keep 2 changes", "second change dropped only at 0.97"),
    "request_99": ("plan with first reduce only misses by ZAR 82.62 (0.14%)", "keep 2 changes", "second change dropped only at 0.97"),
    "request_100": ("2-change plan passes by ZAR 1,154 (2.14%); earliest 07-15 passes by 398 (0.74%)", "not_affordable / not_recommended, plan none, earliest 2024-08-15, changes none", "at 1.03 no change set rescues the installments and the user takes no full payment; safer = do not proceed (flag: harsh call at 2.1%)"),
    "request_101": ("1-change full today passes by INR 668.50 (0.27%); no-change misses by 1,316.50 (0.54%)", "changes stop:event_9378|reduce_to:event_9377:2660 (full_payment, earliest 2025-11-15)", "affordable_now only at 0.97; base set unsafe at 1.03"),
    "request_105": ("plan with first reduce only misses by INR 343.20 (0.21%)", "keep 2 reduces", "second change dropped only at 0.97"),
    "request_109": ("plan with first stop only misses by EUR 37.74 (1.10%)", "keep 2 stops", "second change dropped only at 0.97"),
    "request_113": ("earliest 2026-09-15 passes by INR 515.68 (0.30%)", "wait, earliest 2026-10-15", "later date"),
    "request_118": ("1-reduce plan passes by EUR 23.30 (2.42%); no-change misses by 9.70 (1.01%); earliest 01-15 passes by 19.81 (2.06%)", "changes reduce_to:event_10912:11|reduce_to:event_10914:14, earliest 2025-02-15", "1.03 outcome"),
    "request_119": ("1-reduce plan passes by INR 1,861 (1.06%); earliest 06-15 passes by 2,891 (1.65%)", "changes reduce_to:event_11057:2370|reduce_to:event_11016:2655, earliest 2025-07-15", "1.03 outcome"),
    "request_124": ("1-stop plan passes by EUR 4.40 (0.26%); earliest 07-15 passes by 26.56 (1.60%)", "changes stop:event_11448|reduce_to:event_11480:38, earliest 2024-08-15", "1.03 outcome"),
    "request_125": ("plan with stop only misses by ZAR 15.63 (0.07%)", "keep 2 changes", "second change dropped only at 0.97"),
    "request_131": ("1-reduce installments pass by USD 0.54 (0.04%)", "not_affordable / not_recommended, plan none, earliest 2025-07-23, changes none", "54 cents of margin; at 1.03 no change set rescues the plan and full payment is not accepted"),
    "request_132": ("earliest 2026-01-15 passes by USD 2.49 (0.12%)", "wait, earliest 2026-02-15", "later date"),
    "request_136": ("full today with reduce passes by USD 9.08 (0.54%); no-change misses by 31.72 (1.88%)", "affordable_later / wait, plan 2024-06-15:560.40, earliest 2024-06-15, changes none", "engine picks wait at 1.03; wait keeps more above the minimum"),
    "request_139": ("earliest 2024-10-15 misses by USD 46.16 (2.10%)", "keep not_affordable, earliest 2024-11-15", "later date"),
    "request_145": ("plan with first two changes misses by INR 5,117 (1.59%)", "keep 3 changes", "third change dropped only at 0.97"),
    "request_147": ("1-stop plan passes by EUR 3.90 (0.28%); no-change misses by 5.10 (0.37%)", "changes stop:event_13520|stop:event_13521", "base set unsafe at 1.03"),
    "request_148": ("earliest 2024-07-15 misses by ZAR 150.12 (0.36%)", "keep earliest 2024-08-15", "later date"),
    "request_149": ("no-change installments pass by ZAR 45.99 (0.09%)", "changes stop:event_13702|reduce_to:event_13703:1013.76", "no-change plan unsafe at 1.03"),
    "request_150": ("3-change plan passes by EUR 23.70 (1.62%)", "not_affordable / not_recommended, plan none, earliest 2026-03-15, changes none", "at 1.03 the three permitted changes no longer suffice"),
    "request_163": ("no-change installments pass by IDR 455,864 (1.22%)", "changes stop:event_14953", "no-change plan unsafe at 1.03"),
    "request_176": ("trough above minimum by EUR 24.35 (2.6%) -> amount_safe_to_pay", "amount_safe_to_pay 0", "safe amount crosses zero at 1.03; pays less today"),
    "request_183": ("no-change installments pass by IDR 134,475 (0.43%)", "changes stop:event_16813|stop:event_16814", "no-change plan unsafe at 1.03"),
    "request_195": ("no-change installments pass by EUR 10.46 (0.62%)", "changes reduce_to:event_17955:12", "no-change plan unsafe at 1.03"),
    "request_217": ("no-change installments pass by ZAR 777.53 (1.64%)", "changes stop:event_19978", "no-change plan unsafe at 1.03"),
    "request_225": ("2-change plan passes by IDR 318,330 (0.95%)", "not_affordable / not_recommended, plan none, earliest 2026-09-15, changes none", "at 1.03 no change set rescues the plan"),
    "request_229": ("no-change installments pass by EUR 35.34 (2.31%)", "changes stop:event_21031", "no-change plan unsafe at 1.03"),
    "request_231": ("1-stop plan passes by ZAR 201.15 (0.28%); earliest 02-15 passes by 966 (1.35%)", "changes stop:event_21223|stop:event_21224, earliest 2026-03-15", "1.03 outcome"),
    "request_233": ("second partial payment on 2025-11-15 passes by IDR 111,800 (0.57%)", "partial 2025-11-07:3684137|2025-12-15:2556863, earliest 2025-12-15, amount_safe 3684137", "later date and the 1.03 split"),
    "request_266": ("no-change installments pass by EUR 24.93 (2.37%)", "not_affordable / not_recommended, plan none, earliest 2025-09-15, changes none", "no permitted change exists to rescue the plan at 1.03"),
    "request_267": ("no-change installments miss by EUR 6.41 (0.25%)", "keep stop:event_24573", "change dropped only at 0.97; still sufficient at 1.03"),
    "request_269": ("earliest 2025-11-15 misses by ZAR 511.30 (1.29%)", "keep wait, earliest 2025-12-15", "later date"),
    "request_274": ("1-stop plan passes by EUR 35.26 (0.87%); earliest 01-15 passes by 95.81 (2.35%)", "changes stop:event_25179|reduce_to:event_25180:25, earliest 2025-02-15", "1.03 outcome"),
}

PARTIAL = ["request_46", "request_56", "request_138", "request_168", "request_172", "request_210", "request_214", "request_224", "request_273"]

lines = []
A = lines.append
A("# Hidden-set boundary sensitivity (variable_scale 0.97 / 1.00 / 1.03)\n")
A("Scripts: `sensitivity_sweep.py` (runs, verification, threshold scan, per-flip debug dumps `debug_<request>_<scale>.txt`), "
  "`flip_summary.py` (binding margins, driving series), `build_report.py` (this file). Engine files were not touched; `output.csv` was not modified.\n")
A("## 1. Setup and verification\n")
A("* `run(reqs, ds, use_llm=True, options={'variable_scale': s})` on all 250 `requests.csv` rows, cached model evidence (no API calls).")
A("* Baseline (1.0) equals `output.csv` on all six decision columns for all 250 rows (0 mismatches).")
A("* `variable_scale` multiplies every non-constant recurring series (groceries, transport, dining, utilities, healthcare, entertainment, shopping...) by s; constant series, known flows and salaries are untouched.")
A("* Threshold scan: 80 runs at s = 1 +/- k x 0.25 % (k = 1..40); a request's threshold is the smallest |s - 1| at which any of status / method / earliest / changes / plan dates / amount_safe edge (0 or requested) differs from baseline. For partial-payment rows the split amounts move with every s, so only their dates count (the split change is reported separately).")
A("* 'Reserve' below = the variable block: sum over scaled series of forecast amount x projected occurrences in the 84-day window (per request). Margins are the currency distance of the binding balance check from `minimum_balance_to_keep`, positive = passes.\n")
c = SW["counts"]
A("## 2. Counts\n")
A("| measure | count |\n|---|---|")
A("| requests with any decision column changed at 0.97 | 36 (27 excluding partial-split-only) |")
A("| requests with any decision column changed at 1.03 | 39 (30 excluding partial-split-only) |")
A("| union at +/-3 % | 52 (43 real flips + 9 partial-split-only) |")
A("| **near-boundary: flips within +/-1 % of the variable block** | **19** (8 downward, 11 upward) |")
A("| **near-boundary: flips within +/-3 %** | **43** |")
A("| flips within +/-10 % | 86 |")
A(f"| (same counts with partial-split changes included) | {c['within_1pct']} / {c['within_3pct']} / {c['within_10pct']} |")
A("\nThe threshold in scale units is the margin expressed as a fraction of the variable spend reserved before the binding trough, which is the quantity the +/-3 % calibrated band is about; the currency margins and the % of the whole-window block are given per row below. 207 of 250 rows survive +/-3 % unchanged.\n")
A("## 3. Flip table (43 real flips)\n")
A("Baseline / 0.97 / 1.03 columns show `status/method; earliest; changes; amount_safe`. `(same)` = identical to baseline. Threshold = first scale at which the row changes.\n")
A("| request | thr | baseline | at 0.97 | at 1.03 | driving series and binding margin | recommended value | why |")
A("|---|---|---|---|---|---|---|---|")
for rid in sorted(S, key=lambda r: int(r.split("_")[1])):
    x = S[rid]
    chk, rec, why = REC[rid]
    A(f"| {rid} | {x['thr']} | {x['base']} | {x['s97']} | {x['s103']} | {x['driver']}; {chk} | {rec} | {why} |")
A("\nDriving series = the scaled series with the largest reserved total up to the binding trough date (format: category amount x occurrences before the trough, first date, step, flexibility). The 3 % move of that series alone (`d3%` in `flip_summary.txt`) is in every case the same order as the binding margin, which is why one series suffices to explain the flip.\n")
A("## 4. Partial-payment rows whose only change is the split\n")
A("`amount_safe_to_pay` (first payment) moves with s; dates, status and method do not. Rule from the task: take the 1.03 split (smaller first payment).\n")
A("| request | baseline plan | plan at 1.03 (recommended) |\n|---|---|---|")
for rid in PARTIAL:
    e = SW["flips"][rid]
    A(f"| {rid} | {e['baseline']['payment_plan']} | {e['scales']['1.03']['row']['payment_plan']} |")
A("\n## 5. Decision rule applied\n")
A("Statement conflict rule 4 (financially safer interpretation when the data cannot resolve it) with the task's concretisation: now vs later -> later; full vs installments -> the one keeping the trough higher; with-changes vs without -> changes only if the no-change version is unsafe at 1.03; earlier vs later earliest -> later; partial split -> the 1.03 split. All 43 real flips have a binding margin below 3 % of the reserve (by construction of the +/-3 % sweep), so the rule applies to every row. Nothing was applied to `output.csv`.\n")
A("Groups:\n")
A("* Keep baseline (13): 60, 89, 92, 97, 99, 105, 109, 125, 139, 145, 148, 267, 269 -- the flip is only downward (0.97): the earlier date or the smaller change set relies on lower spending.")
A("* Take the 1.03 outcome, same status/method (22): 49, 53, 55, 59, 68, 96, 101, 113, 118, 119, 124, 132, 147, 149, 163, 183, 195, 217, 229, 231, 233, 274 -- later earliest date and/or a larger change set that stays safe at 1.03.")
A("* Status/method changes (8): 77 -> wait; 136 -> wait; 100, 131, 150, 225, 266 -> not_affordable (at 1.03 no permitted change rescues the installments and the user does not accept a later full payment); 176 -> amount_safe 0.")
A("\nCaveats worth weighing before applying anything: the engine's baseline is the band-clamped mean, i.e. the best point estimate; the safer rule trades expected accuracy for downside protection. request_60 (20 cents), request_131 (54 cents) and request_233 (partial plan trough exactly at the minimum by construction) are genuine coin tosses. The five not_affordable recommendations and the eleven 'add a change' recommendations are the costly ones if the ground truth is generated from the nominal amounts the estimator already targets (see `notes/mismatches.md`: clamp_to_band made samples 08 and 18 exact).\n")
A("## 6. Files\n")
A("* `sweep_results.json` - all runs, thresholds, per-flip margins (raw)\n* `thresholds_real.json` - threshold per request, partial-split changes excluded\n* `flip_summary.json` / `flip_summary.txt` - binding margins and driving series per flip\n* `debug_<request>_<scale>.txt` - state, candidates and daily projection at 1.00 and at the flipping scale (equivalent of `debug_request.py --llm` with `options` passed to `StateBuilder`)\n")
(OUT / "3_sensitivity.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", OUT / "3_sensitivity.md", len(S), "flips", len(PARTIAL), "partial")
missing = set(S) - set(REC)
print("missing recs:", missing)
