# Trace: request_17 (user_17, INR) — why the reference says earliest = 2026-03-15

Scripts: `trace_request_17.py` (decomposition), `estimator_sweep_17.py` (cross-sample check). Engine untouched.

## 1. State (engine, `--llm`, 84-day horizon 03-01..05-24)
* balance 550,379.58, min 166,100, headroom 384,279.58; requested 274,600; salary 206,000 scheduled 03-15 (recurs 04-15, 05-15).
* Fixed monthly: rent 49,600 (2nd), education 13,660 (8th), debt 30,200 (11th), music 2,055 (11th), delivery 1,675 (13th) = 97,190; utilities mean 9,538.75 (6th).
* Weekly (last+7): groceries 9,096.70 (03-06, 03-13, 03-20, 03-27, 04-03, 04-10 …), transport 5,278.04 (03-07, 03-14, 03-21, 03-28, 04-04, 04-11 …); 14-day dining 5,777.68 (03-08, 03-22, 04-05 …). Image row event_1545 (41,272, 02-27) excluded from the mean.
* No pending rows, no messages; option_47 = 3 x 95,194.67 from 03-01 (eligible, max 3).

## 2. Daily series, both scenarios
| date | no payment | with 274,600 on 03-15 |
|---|---|---|
| 03-01 | 550,379.58 | same |
| 03-14 (trough before payday) | 409,123.68 | same |
| 03-15 (+206,000) | 615,123.68 | 340,523.68 |
| 04-13 (trough before 2nd payday) | 439,340.63 | **164,740.63 < 166,100 by 1,359.37** |
| 04-15 (+206,000) | 645,340.63 | 370,740.63 (safe from here on; 05-13 trough 194,957.58) |

Pre-payday reserve ours = 550,379.58 − 409,123.68 = 141,255.90 → safe 243,023.68. Reference reserve 140,430 → safe 243,849.58 (Δ 825.90, 0.59 %).

Items between 03-15 and 04-13 (ours): fixed 97,190 + utilities 9,538.75 + 4 groceries 36,386.79 + 4 transport 21,112.16 + 2 dining 11,555.36 = 175,783.05. Room after salary and payment = 340,523.68 − 166,100 = 174,423.68 → shortfall 1,359.37.

## 3. Decomposing 140,430
140,430 − 97,190 fixed = 43,240 = U + 2G + 2T + D (utilities, groceries, transport, dining), i.e. the same 1/2/2/1 occurrences the engine places (03-06, 03-06/03-13, 03-07/03-14, 03-08). Other counts are implausible: 1 grocery needs U ≈ 12,580, 3 groceries U < 0 at midrange values; only (2,2,1) gives U ≈ 9,144, inside the utilities history 8,487–10,247. Our variable total is 44,065.90 (ratio 0.981).

Post window in the reference = 97,190 + U + 4G + 4T + 2D = 97,190 + 43,240 + (43,240 − U) = 183,670 − U, room = 409,949.58 + 206,000 − 274,600 − 166,100 = 175,249.58 → passes iff U ≥ 8,420. Every one of 295,264 grid decompositions (nominals within ±30 % of the history range, ±20 % for utilities) passes, margin 110 … 2,120; e.g. U 9,350 / G 9,240 / T 4,950 / D 5,510 → +930. So the reference needs **no fewer occurrences and no different rule** — 4 groceries, 4 transport, 2 dining between the paydays is exactly what it uses.

## 4. The single explanation
**Amount noise, doubled by cadence.** Our historical means overshoot the hidden nominals by 826 INR over one half-month (2G+2T+D+U); in the payday-to-payday window the weekly/14-day items occur twice as often, so the gap becomes ≈ 2 × 826 − (our U − ref U) ≈ 1,500, more than the 1,359 shortfall. Means vs midrange per item: groceries 9,097 vs 9,070, transport 5,278 vs 5,162, dining 5,778 vs 5,632, utilities 9,539 vs 9,367. The structure (last+7 anchoring, skip-on-request-date, salary-first netting, 84-day horizon, image row excluded) is already consistent with the reference.

## 5. Cross-sample consistency (current engine, `--llm`)
gap %-of-reserve (positive = reference reserves more than we do): +7.9, +4.4, +16.8, +1.3, −9.7, −2.4, +0.1, +5.0, −1.1, +5.4, +1.6, −3.7, **−0.6 (17)**, +13.5, +1.4, +10.9, +5.5, +1.5, +6.0, +0.6, −0.2. The reference reserves MORE than the mean forecast in 15 of 21 uncapped samples; request_17 is one of six where we over-reserve, so lowering the estimator globally is not supported:
* mean: earliest 22/25, overall 118/150.
* median: fixes 17 and 11 (earliest 24/25) but status 22, method 23, plan 22, changes 21 → 116/150.
* midrange: fixes 17, breaks 11 (earliest → 05-15), 116/150. trimmed-20 %: 114/150.

Conclusion: keep the mean; request_17's earliest date is an irreducible ±1 % near-miss (shortfall 0.77 % of the window's spend). The recommended plan (installments option_47) and status are unaffected; only `earliest_date_for_full_payment` and 0.3 % of `amount_safe_to_pay` differ.
