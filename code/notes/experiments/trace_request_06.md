# Trace: request_06 (user_06) — why the engine says `wait` and the reference says `full_payment` + `stop:event_476`

Scratch scripts (read-only against the engine): `variants_request_06.py` (patched periodic projection, scores all
samples), `phase_check.py` (per-sample periodic-series phase), `nominal_search_06.py` (integer-nominal decompositions).

## 1. State (engine, `--llm`)

* balance 1942.40, min 800, headroom 1142.40; request 620.40 by 2026-01-14; methods full|partial; no installments;
  protect rent|insurance|transport; stop streaming; reduce none.
* Known flows: salary 1037.52 on 2026-01-15 (message_04: temporary pay continues for the next payroll), then the
  regular 1441.00 on Feb 15 / Mar 15. Only non-settled row is event_557, a cancelled 66 EUR card authorization (ignored).
* Series (mean of history): rent 254.10 (3rd, monthly), utilities 55.70 (7th), insurance 26 (8th), streaming 19 (10th),
  cloud 5 (13th), shopping 41.00 (13th), entertainment 35.01 (15th), groceries 45.08 every 10 d (last 12-28 -> Jan 7),
  transport 26.98 every 5 d (last 12-29 -> Jan 3 skipped as request date, Jan 8, Jan 13), dining 45.88 every 7 d
  (last 12-28 -> Jan 4, Jan 11). History is perfectly regular (35/25/18 rows, no jitter).

## 2. Forecast

Trough = Jan 13 (day before payday), balance 1350.81. Engine reserve 1942.40 - 1350.81 = **591.59** =
rent 254.10 + dining 45.88 (Jan 4) + utilities 55.70 + groceries 45.08 + insurance 26 + transport 26.98 (Jan 8)
+ streaming 19 + dining 45.88 (Jan 11) + cloud 5 + shopping 41 + transport 26.98 (Jan 13).
safe = 1350.81 - 800 = 550.81. earliest = Jan 15 (2353.32 - 620.40 stays >= 800 through Mar 28; the Feb 13 low is 851.51).
Salary regime is irrelevant to the trough (it precedes the first payday): the "reduced pay for all months" reading does
not move Jan 13, and the Feb/Mar salaries only matter for `earliest`, which already matches.

## 3. Plans

full today: gap 620.40 - 550.81 = 69.59; only candidate change is stop streaming (19 on Jan 10) -> trough 569.81 < 620.40 -> no
full candidate. Partial: request disallows it. Installments: max months blank. Wait: Jan 15 > desired Jan 14 -> ranked last
but the only candidate -> `wait` / affordable_later.

## 4. Which items make the reference's 539.10

539.10 - rent 254.10 = 285.00 exactly, so the rent on the request date is reserved and the remaining items are integer
nominals. Fixed subscriptions insurance 26 + streaming 19 + cloud 5 = 50 (streaming must be reserved, otherwise
`stop:event_476` would not close the 17.10 gap). Variable items sum to **235**; the engine's variable items sum to 287.50.
Well-supported nominals: groceries 45 (n=18), transport 27 (n=35), dining 46 (n=25). Feasible decompositions:

| items | utilities + shopping needed | engine means |
|---|---|---|
| **1 dining** + utilities + groceries + 2 transport + shopping | 235 - 46 - 45 - 54 = **90** | 96.70 (two n=5 series, -7 %) |
| 0 dining + entertainment (debit-first on payday) + ... | 101 | needs utilities 58 / shopping 43 and two rule changes |
| 2 dining, no utilities | shopping alone = 44 | no reason to drop utilities |

Reference = 254.10 + 26 + 19 + 5 + 45 + 27x2 + 46 + (utilities + shopping = 90) = 539.10. The engine counts the same
list with **one extra dining occurrence**; everything else is noise on two 5-row series.

## 5. The single differing rule

**The dining occurrence on request_date + 1 (Jan 4 = last row 12-28 + 7) is not counted by the reference; only one
weekly dining (Jan 11) falls before the Jan 15 payday.** Generalised: a short-cycle occurrence is skipped when it lands on
request_date **or the day after** (engine only skips request_date itself). Evidence across the samples (phase_check.py):
occurrences at rq+2 (request_20, _24 groceries) and rq+3 (request_21, _24, _25) are counted by the reference; rq+0 is
skipped (request_15, _22, _23, _25); rq+1 occurs only here and in request_15 (transport Jan 7).

Consistency: `variants_request_06.py skip_rq1` changes only request_06 (safe 550.81 -> 596.69, reserve 545.71 vs 539.10,
-1.2 %) and request_15 (65.19 -> 96.95; reserve error -17.9 -> +13.9, both within noise; request_15 nominals
utilities 87 + groceries 60 + dining 41 + transport 32 x k give 474 (k=1) / 506 (k=2) vs 487, mildly favouring k=1).
Every other sample row is identical (total |gap| 3,652,890 -> 3,652,841; within-2 % count 11 -> 12).
The alternative "anchor periodic series at request_date + step" is refuted (11 samples get 10-35 % worse); a
per-cycle cap of one weekly occurrence would break request_17 and request_24.

## 6. Caveat: the rule alone does not flip the decision

With the Jan 4 dining dropped the engine reserve is 545.71 -> safe 596.69, gap 23.71 > streaming 19, so `wait` still wins.
The reference's outcome needs reserve <= 541.40 (gap <= 19), i.e. utilities + shopping <= 92.4 where the engine's means give
96.70 (the reference's hidden nominals give 90). This 0.8 % margin is inside the irreducible variable-expense noise, so
request_06 reproduces the reference's method/changes only if the estimator for the two 5-row series lands ~4.3 EUR lower
(e.g. median utilities 56.71 does not help; the last values 51.86 + 39.88 = 91.74 would). Expected honest result after the
rule change: amount_safe_to_pay 596.69 (vs 603.30, -1.1 %), status/method/plan/changes still mismatched.
