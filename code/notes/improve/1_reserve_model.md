# 1 — Reserve model via `minimum_allowed_amount` (subagent 1)

Scripts (all under `code/notes/improve/`, engine untouched):

* `1_min_ratio_analysis.py` — task 1: ratio `amount / minimum_allowed_amount` per category and per (user, category) series.
* `1_noise_shape.py`, `1_band.py` — noise histogram of the leaked categories; per-category noise half-band.
* `1_reserve_leak.py [grid|table|resid|kcheck]` — `StateBuilder` subclass with pluggable per-series amounts; full re-score
  (planner + explanation, cached LLM evidence) of the 25 samples. `resid` prints the task-3 residual targets.

## 1. Is the nominal leaked through `minimum_allowed_amount`? — Yes

* 2,907 settled debit rows carry `minimum_allowed_amount` (flexibility `reducible` / `reducible_or_stoppable`), in five
  categories only: dining, entertainment, shopping, gym, streaming. **Within every (user, category) series the minimum is a
  single constant** (nmin = 1 for all 250+ series).
* Ratio `amount / minimum_allowed_amount` (all rows):

  | category | n | min | p10 | median | mean | p90 | max |
  |---|---|---|---|---|---|---|---|
  | dining | 1925 | 1.441 | 1.556 | 2.003 | 2.002 | 2.445 | 2.560 |
  | entertainment | 220 | 1.762 | 1.800 | 2.006 | 2.001 | 2.202 | 2.237 |
  | shopping | 360 | 2.200 | 2.267 | 2.507 | 2.501 | 2.740 | 2.799 |
  | gym / streaming (constant) | 70 / 332 | 2.000 | | 2.000 | | | 2.000 |

  The noise `amount / (k × min)` is **flat (uniform)**: dining on [0.72, 1.28] (histogram of 0.04 bins: 69,136,126,131,132,159,
  147,126,150,138,139,115,151,144,62), entertainment and shopping on [0.88, 1.12]. So
  `observed = nominal × U(1−a, 1+a)` with `min = nominal × f`, **f = 0.5 for dining / entertainment / gym / streaming and
  f = 0.4 for shopping** (k = 2.0 / 2.5, the dataset median rounded to 0.5). The multiplier is category-constant, not user-specific
  (every shopping series has ratios in 2.2–2.8, every dining series in 1.44–2.56).
* Series mean vs 2×min: dining `mean/(2min)` over 153 variable series ranges 0.867–1.128 (median 0.998); entertainment 0.933–1.077;
  shopping `mean/(2.5min)` 0.939–1.072 after rescaling. The mean is centred on the nominal with exactly the spread expected from
  n = 5–13 uniform draws; the nominal is recoverable exactly.
* The recovered nominals show the generator's rounding grid: EUR/USD integers (49, 44, 87, 82, 124, 127), INR multiples of 10
  (5670, 5870, 3610, 1790, 6080, 2170, 4390, 8820), IDR multiples of 100 (165,300; 1,341,400; 1,385,100; 1,510,500; 1,331,900),
  ZAR multiples of 0.2 (979, 402.60, 1278.20, 2145, 1271.60).
* Confirmation on the samples: after subtracting `k × min` for the leaked series (and the exactly known items) from the reference
  reserve, the remaining target for the fixed variable series is round in the unit in every sample (99, 251, 86, 401, 417, 189, 235,
  2165 EUR/USD; 16,450 / 279,100 / 37,370 / 23,500 / 12,650 / 12,940 INR; 7,803,300 / 729,600 / 8,291,600 / 8,000,900 / 5,654,400 IDR).
  Subtracting the historical mean instead leaves cents. The leak is exact.
* Coverage: 245 of the 1,263 variable series in the 250 evaluation requests are leaked (194 of 250 requests have at least one).
  Dining / entertainment / shopping are only flexible for ~half of the users; for the other half they carry no minimum and stay
  "fixed variable".

## 2. Re-score with nominal = k × min for leaked series (mean elsewhere)

Full planner re-score, all 25 samples (`1_reserve_leak.py table`). Reserve rel. error = (ours − ref)/ref of the reserve.

| req | ref reserve | BASELINE (engine) | leak + mean | leak + imid | leak + imid round 5u |
|---|---|---|---|---|---|
| 01 | cap | exact 5/5 | exact | exact | exact |
| 02 | 13,996,350 | −0.17 % | −0.17 % | +0.75 % | +0.75 % |
| 03 | 2,268,600 | −0.34 % | −0.49 % | −0.21 % | −0.20 % |
| 04 | 13,118,550 | −16.83 % | −16.83 % | −17.42 % | −17.42 % |
| 05 | 32,638.10 | −1.32 % | −1.28 % | −2.43 % | −2.44 % |
| 06 | 539.10 | +9.74 % (1/5) | +9.74 % (1/5) | +9.08 % (1/5) | +8.81 % (1/5) |
| 07 | 38,775 | +2.41 % | +1.74 % | +1.80 % | +1.81 % |
| 08 | 452 | −0.14 % | −0.55 % | +0.12 % | +0.12 % |
| 09 | cap | exact | exact | exact | exact |
| 10 | 512,055 | −5.04 % | −5.21 % | −4.88 % | −4.79 % |
| 11 | 16,880,550 | +1.13 % (3/5) | +1.02 % (3/5) | +0.60 % (**0/5**) | +0.60 % (0/5) |
| 12 | cap | exact | exact | exact | exact |
| 13 | 1,056.12 | −5.43 % | −5.43 % | −4.24 % | −2.63 % |
| 14 | 1,134 | −1.64 % | −1.85 % | −1.13 % | −1.50 % |
| 15 | 487 | +3.67 % | +4.32 % | +5.86 % | +6.00 % |
| 16 | cap | exact | exact | exact | exact |
| 17 | 140,430 | +0.59 % (4/5) | +0.65 % (4/5) | +0.51 % (4/5) | +0.45 % (4/5) |
| 18 | 624 | +0.25 % | +0.47 % | +0.79 % | +0.34 % |
| 19 | 77,925 | −1.45 % (4/5) | −1.13 % (4/5) | −0.77 % (4/5) | −0.77 % (4/5) |
| 20 | 32,709.05 | −0.45 % | **+0.19 % (w2)** | +0.49 % | +0.61 % |
| 21 | 568 | −0.90 % | −0.88 % | −0.06 % | −0.18 % |
| 22 | 157 | −1.45 % | −1.45 % | −0.79 % | −0.40 % |
| 23 | 15,805.90 | −0.33 % | −0.61 % | −0.51 % | −0.53 % |
| 24 | 20,625 | −0.58 % | −0.89 % | +0.61 % | +0.53 % |
| 25 | 7,258,950 | +0.20 % | +0.20 % | −0.20 % | −0.19 % |
| within 1 % / 2 % | 14 / **16** | 12 / **17** | 15 / 16 | 16 / 16 |
| mean / median rel (21) | 2.57 / 1.13 % | 2.62 / 1.02 % | 2.54 / 0.77 % | 2.43 / 0.61 % |
| total abs gap (raw) | 2,473,609 | 2,459,466 | 2,539,148 | 2,538,195 |
| normAbs | 738 | 753 | 754 | 733 |
| non-amount cols /125 | **117** | **117** | 114 | 114 |

(within-2 % is the scorer's rule `|got − want| ≤ 0.02·want` on the amount; request_20 is the sample that crosses it.)

`leak + mean` changes no non-amount column (117/125; request_19's partial split moves from 29,948.97/9,711.03 to 29,702.83/9,957.17 vs
the reference 28,820/10,840 — still a mismatch). It gains one within-2 % sample (20), loses two within-1 % (08, 24 stay within 2 %),
and the aggregate error is flat (total gap −0.6 %, normAbs +2 %). Reason: the leaked series are exact now, but they were only
~3–5 % off before and contribute a small share of each reserve; the total is dominated by the fixed-variable block and by the
structural samples (04, 06, 10, 13, 15). Where errors used to cancel (08: dining +1.84 vs groceries/transport −2.47) the exact
value now exposes the fixed-block error.

## 3. Fixed-variable categories: mean vs midrange vs round numbers

Noise model from the leaked categories carries over: per-series `(max−min)/(max+min)` maxes at 0.2789 (groceries), 0.2787
(transport), 0.1195 (utilities), 0.1145 (healthcare) — exactly the 0.28 / 0.12 half-bands of the leaked dining / entertainment.
So `observed = nominal × U(1−a, 1+a)`, a = 0.28 for groceries/transport/dining and 0.12 for utilities/healthcare/entertainment/shopping.
Under uniform noise the efficient estimators are the midrange and, better, the **feasible-interval midpoint**
`imid = (max/(1+a) + min/(1−a)) / 2` (every nominal must satisfy `max/(1+a) ≤ nominal ≤ min/(1−a)`).

Residual target per sample (`resid`): reference reserve − known debits before the trough + credits − constant series − leaked series
= what the fixed-variable series must sum to. Fit of the estimators to that target (21 uncapped samples):

| estimator for the fixed block | block within 1 % / 2 % (of 21) | mean abs error, 13 structurally clean samples | normAbs clean / all |
|---|---|---|---|
| mean (engine) | 4 / 8 | 1.58 % | 113.5 / 753 |
| midrange | 7 / 11 | 1.08 % | 97.2 / 785 |
| imid | 5 / 12 | 1.10 % | 92.5 / 753 |
| imid rounded to unit | 3 / 12 | 1.16 % | 98.8 / 761 |

(the 8 "structural" samples — 04 −27 %, 06 +21 %, 15 +11 %, 10 −9 %, 07 +3–4 %, 14 −3–5 %, 19 −3 %, 05 −3–6 % — are occurrence-count
mismatches that no estimator touches.) Rounding: the nominal grid is one currency unit (IDR 100, INR 10, EUR/USD 1, ZAR 0.2);
rounding to 1 unit changes nothing measurable, 5 units is neutral (w1 15→16), 10/50 units are worse (w2 16→15, meanRel 5 %). A
band sensitivity of ±10 % moves w2 by ±2 with no consistent gain (x1.1: w2 18 / w1 12 / normAbs 713; x0.9: w2 16 / w1 13 / 793).
Restricting imid to the wide-band or the narrow-band categories only is no better than applying it to all.

So on the variable block the midpoint-type estimators are ~30 % more accurate than the mean (1.1 % vs 1.6 %), as the uniform
model predicts, but that is ≈ 0.5 % of a typical reserve and it does not move end-to-end within-2 % counts (16 → 16), while it
flips request_11 (reserve +1.13 % → +0.60 %) from full-with-changes to `wait`/`affordable_later`, losing 3 non-amount columns.
`no leak + imid` reaches w2 = 18 but with the same request_11 loss (114 cols) and higher total gap.

## 4. Recommendation

* **Adopt `nominal = k × minimum_allowed_amount` (k = 2.0 for dining/entertainment/gym/streaming, 2.5 for shopping; derive k as the
  dataset median of amount/min rounded to 0.5) for every variable series that carries a minimum, keep the mean elsewhere.** It is
  the generator's exact value (verified by the round residual targets), it preserves all 117 currently matching non-amount columns,
  and it is neutral-to-slightly-positive on the amount column (within-2 % 16 → 17, total gap −0.6 %). It also makes `reduce_to`
  savings exact (`nominal − min = min` for dining, `1.5 × min` for shopping). Expect a similar small effect on the 250 evaluation
  requests (194 have a leaked series).
* **Do not switch the fixed-variable estimator to midrange/imid now.** It is the theoretically right estimator for this uniform
  noise and is measurably better on the block (1.6 % → 1.1 %), but end-to-end it gains nothing within 2 % and breaks request_11's
  plan. Keep it as an option if the amount column is ever weighted with a tolerance and request_11's knife-edge is understood.
* Honest bottom line: the remaining amount error is structural (which occurrences the organizers count around paydays: 04, 06, 10,
  13, 15), not the amount estimator. Nothing in the estimator/rounding space beats the mean by more than one sample.
