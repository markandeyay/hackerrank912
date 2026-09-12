# Reserve hypotheses for `amount_safe_to_pay` (25 solved samples)

Harness: `code/notes/experiments/reserve_hypotheses.py` (`dump` | `grid` | `top`). It subclasses `StateBuilder`,
re-implements `_build_debit_series` with pluggable estimator / rounding / scheduling hooks and post-processes the
state (salary shift, payday handling). The engine files were not modified. Evidence = cached LLM extraction (`--llm`).

Metrics (all 25 samples; 21 uncapped ones for the relative error):

* `w2%` = samples whose amount is within 2 % of the reference (scorer tolerance).
* `meanRel` / `medRel` / `bias` = |ours − ref| / ref of the *reserve* (balance − min − amount), mean / median / signed mean.
* `normAbs` = Σ |gap| / currency scale (IDR 10⁴, INR 10², ZAR 10, EUR/USD 1) — a currency-normalised absolute error.
* `cols` = non-amount columns matched by the full planner (5 columns × 25 = 125; engine today = 114).

## 0. Facts established first

1. **Explanation text**: in all 25 samples the "leaves at least / keeps the {CUR} {X}" figure is exactly
   `minimum_balance_to_keep`. No hidden round reserve figure there.
2. **Reserve structure**: reference reserve − (known pending/scheduled debits + constant-amount recurring items before
   the trough) is always round to the currency's nominal unit: IDR multiples of 100 (7,803,300; 894,900; 9,676,700;
   9,332,800; 5,654,400), INR multiples of 10 (22,120; 345,190; 43,240; 29,580; 18,430; 14,730), EUR/USD integers
   (148; 544; 233; 488; 86; 235; 457; 2,165). So the organizers use hidden round *nominal* amounts for the variable
   categories (utilities, groceries, transport, dining, shopping, healthcare, entertainment); the historical rows are
   nominal × noise (observed range ≈ −26 % … +30 % around the mean for 25-row series, i.e. roughly symmetric, sd ≈ 12–14 %).
   The mean is therefore the right estimator; rounding the mean to the unit changes nothing measurable.
3. **Generator regularity**: every recurring series has *exactly* constant gaps (5/7/10/14/21 days or same DOM) and every
   salary lands on the 15th with settlement lag 0. So no "mean gap vs median gap" or settlement-lag effect exists.
4. The per-sample variable residual ratio (reference ÷ our mean-based variable total) is 0.82–1.40: far beyond amount
   noise (with 3–5 series the noise is ~±5 %). The large residuals are **structural (occurrence counting)**, not amounts:
   02 (+1.1 M), 04 (+2.2 M), 18 (+84), 20 (+3.6 k), 21 (+130 at the April trough), 23 (+941), 06 (−52).

## 1. Grid results (harness `grid`; baseline = engine rule: mean, cadence, DOM, salary netted first)

| hypothesis | w2% | meanRel | medRel | bias | normAbs |
|---|---|---|---|---|---|
| **BASELINE mean / cadence / salary-first** | **11/25** | **4.75 %** | 3.67 % | −3.06 % | 1087 |
| est = median | 8 | 5.00 % | 4.31 % | −2.98 % | 1115 |
| est = trimmed mean | 11 | 4.79 % | 3.40 % | −3.04 % | 1090 |
| est = mid-range (min+max)/2 | 11 | 4.80 % | 4.62 % | −3.24 % | 1151 |
| est = first observed / mode | 7 | 5.61 % | 3.31 % | −2.41 % | 1057 |
| est = last-3 mean | 9 | 5.43 % | 2.94 % | −3.67 % | 1583 |
| est = last observed | 9 | 5.98 % | 5.12 % | −3.33 % | 1495 |
| est = p75 (variable only, mean for constants) | 6 | 6.25 % | 4.77 % | +2.44 % | 1224 |
| est = mean + std | 5 | 7.22 % | 5.47 % | +3.77 % | 1488 |
| est = max (variable only) | 5 | 10.88 % | 6.80 % | +8.50 % | 2343 |
| mean × 1.05 (variable only) | 8 | 4.76 % | 4.10 % | −0.20 % | 924 |
| mean × 1.10 / 1.15 / 1.20 | 5 / 5 / 4 | 6.3 / 8.1 / 10.8 % | | | |
| round mean to 1×unit (IDR 10⁴, INR 100, ZAR 10, EUR 1) nearest | 11 | 4.71 % | 3.70 % | −3.05 % | 1083 |
| round to 5×unit nearest | 11 | 4.74 % | 3.42 % | −3.03 % | 1042 |
| round to 3 significant figures nearest | 11 | 4.73 % | 3.68 % | −3.07 % | 1083 |
| round to 2 sig. figs nearest / up | 11 / 8 | 4.91 / 6.61 % | | | |
| round to 1 sig. fig | ≤ 9 | ≥ 12 % | | | |
| round to absolute 10 / 50 / 100 / 500 / 1000 (nearest) | 11 / 10 / 9 / 9 / 8 | 5.4 / 8.7 / 11.5 / 26 / 40 % | | | |
| rounding UP (any unit) | ≤ 10 | ≥ 6.9 % | | +0.6 … +29 % | |
| last full calendar month sum, monthly on DOM | 3 | 23.2 % | 29.5 % | −23 % | 4086 |
| all series monthly (every 30 d from last, or DOM) | 4 | 26.4 % | 30.2 % | −26 % | 6555 |
| periodic_max_per_cycle = 1 / 2 | 9 / 11 | 7.17 / 6.78 % | | −6.8 / −5.1 % | |
| periodic_skip_request_date = False | 9 | 6.56 % | 5.01 % | −0.29 % | 1237 |
| include image-sourced rows in the mean | 11 | 4.83 % | 3.67 % | −2.98 % | 1112 |
| debit_first = True (all payday debits before salary) | 11 | 6.14 % | 4.35 % | +2.71 % | 1288 |
| salary lands one / two days late | 11 / 11 | 6.14 / 6.64 % | | | |
| monthly series at last + 30 days instead of DOM | 9 | 12.3 % | 5.47 % | −11 % | 1831 |
| est = mid + debit_first (best of the "rounding/estimator" combos) | 12 | 6.19 % | 4.62 % | +2.52 % | 1344 |
| **variable-series occurrences on payday applied before salary** | 12 | 3.98 % | 1.64 % | +0.38 % | 740 |
| **periodic (5–21 d) variable occurrences on payday before salary** | 12 | **3.49 %** | 1.64 % | −1.00 % | 781 |
| **periodic variable occurrences on payday AND payday+1 before salary** | **13** | 3.55 % | **1.45 %** | +0.06 % | **721** |

Every estimator other than the mean, every rounding variant, the last-month-sum rule, the monthly-everything rule,
`periodic_max_per_cycle`, `periodic_skip_request_date=False`, `debit_first` and salary shifts are **worse than or equal
to the baseline** on every metric. The only hypotheses that beat it are the payday-handling ones, and they are not clean
(see §3).

## 2. Per-sample table — baseline vs. the three best payday rules (reserve rel. error; `cols` = non-amount columns matched /5)

| req | ref reserve | baseline | A: var on payday first | B: periodic var on payday first | C: periodic var on payday & +1 first |
|---|---|---|---|---|---|
| 01 | cap | exact 5/5 | exact | exact | exact |
| 02 | 13,996,350 | −7.9 % | **+1.4 %** | −7.9 % | −7.9 % |
| 03 | 2,268,600 | −4.4 % | −4.4 % | −4.4 % | −4.4 % |
| 04 | 13,118,550 | −16.8 % | −5.4 % | −5.4 % | **+0.9 %** |
| 05 | 32,638.10 | −1.3 % | −1.3 % | −1.3 % | −1.3 % |
| 06 | 539.10 | +9.7 % (1/5) | +16.2 % (0/5) | +9.7 % | +9.7 % (0/5) |
| 07 | 38,775 | +2.4 % | +2.4 % | +2.4 % | +2.4 % |
| 08 | 452 | −0.1 % | −0.1 % | −0.1 % | −0.1 % |
| 09 | cap | exact | exact | exact | exact |
| 10 | 512,055 | −5.0 % | −5.0 % | −5.0 % | −5.0 % |
| 11 | 16,880,550 | +1.1 % (3/5) | +1.1 % (3/5) | +1.1 % (3/5) | +1.4 % (4/5) |
| 12 | cap | exact | exact | exact | exact |
| 13 | 1,056.12 | −5.4 % | −1.2 % | −1.2 % | −1.2 % |
| 14 | 1,134 | −1.6 % | −1.6 % | −1.6 % | −1.6 % |
| 15 | 487 | +3.7 % | +3.7 % | +3.7 % | +3.7 % |
| 16 | cap | exact | exact | exact | exact |
| 17 | 140,430 | +0.6 % (4/5) | +0.6 % | +0.6 % | +0.6 % |
| 18 | 624 | −13.5 % | **+0.3 %** | **+0.3 %** | **+0.3 %** |
| 19 | 77,925 | −1.5 % (4/5) | −1.5 % | −1.5 % | −1.5 % |
| 20 | 32,709.05 | −10.9 % | −10.9 % | −10.9 % | −10.9 % |
| 21 | 568 | −5.5 % (2/5) | −5.5 % (2/5) | −5.5 % (2/5) | **−0.9 % (5/5)** |
| 22 | 157 | −1.5 % | +11.8 % | −1.5 % | −1.5 % |
| 23 | 15,805.90 | −6.0 % | **−0.3 %** | **−0.3 %** | **−0.3 %** |
| 24 | 20,625 | −0.6 % | −0.6 % | −0.6 % | **+10.5 %** |
| 25 | 7,258,950 | +0.2 % | **+8.4 %** | **+8.4 %** | **+8.4 %** |
| within 2 % | 11 | 12 | 12 | 13 |
| mean rel (21) | 4.75 % | 3.98 % | 3.49 % | 3.55 % |
| cols /125 | 114 | 113 | 114 | 117 |

## 3. What the payday evidence actually says (and why no clean rule emerges)

Items whose next occurrence falls on the payday (all paydays are the 15th) or the day after:

| sample | item on payday / +1 | counted by the reference? |
|---|---|---|
| 02 | entertainment, monthly variable, 15th | yes (otherwise the four variable series would need +16.5 %) |
| 04 | groceries 7-day 15th + transport 7-day 16th | yes, both (+0.9 % with both; −5.4 % with groceries only) |
| 18 | dining 14-day 15th | yes (+0.3 %) |
| 23 | transport 14-day 15th / family_support constant 15th | transport yes (−0.3 %), family_support no |
| 21 | groceries 10-day + transport 21-day 16th | yes (−0.9 %) |
| 13 | (84-day trough) | payday rule moves −5.4 % → −1.2 % |
| 06 | entertainment monthly variable 15th | no (reference is already 9.7 % *below* ours) |
| 22 | entertainment monthly variable 15th | no (+11.8 % if counted) |
| 25 | transport 5-day 15th | no (+8.4 % if counted) |
| 24 | groceries 10-day 16th, transport 5-day + dining 7-day 17th | no (+10.5 % if the 16th is counted) |
| 19 | family_support constant 15th | no |
| 15 | delivery_membership constant 15th | no |

Constant subscriptions/transfers on payday are never counted (3/3). Variable items on payday are counted in 4 samples
and not counted in 3–4 others; nothing in the profiles, flexibility flags, messages, request types, desired dates,
cadence or category separates the two groups (checked). request_20 (−10.9 %) and request_06 (+9.7 %) have no payday item
at all and remain unexplained; request_03 (−4.4 %), request_10 (−5.0 %) are probably amount noise on many-occurrence windows.

## 4. Recommendation

* **Keep the current rule** (mean, observed cadence, DOM for monthly, salary netted on payday). Nothing in the
  estimator / rounding / scheduling / ordering space beats it; several are far worse (max, p75, rounding up, monthly-everything,
  last-month sum). Bias −3 % means we slightly *under*-reserve on average; ×1.05 removes the bias but drops within-2 % to 8/25.
* The only measurable improvement is rule **C** ("periodic variable occurrences on payday and payday+1 are applied before
  the salary"): within-2 % 11 → 13, mean reserve error 4.75 % → 3.55 %, non-amount columns 114 → 117 (request_21 becomes
  fully correct: status/method/changes; request_11 earliest date fixed). Cost: request_24 (−0.6 % → +10.5 %) and
  request_25 (+0.2 % → +8.4 %) break, and nothing in the data explains why 24/25 differ from 04/21, so this is a fit to
  the samples, not a discovered rule. Adopt it only if the evaluation weights the amount column with a tolerance and the
  team accepts the risk; otherwise document it as an open item.
* Rule **B** (payday only, periodic only) is the "safe" variant: same 114 columns, mean error 3.49 %, breaks only request_25.
