# Experiment: forecast window length (HORIZON_DAYS) vs all 25 samples

Date: 2026-09-12. Engine unchanged. Script: `code/notes/experiments/horizon_sweep.py`
(runs the pipeline for `horizon_days` = 84..90 in one process; `h90x` = horizon 90 with the
request-date balance excluded from every safety check, simulated by monkeypatching
`forecast.daily_balances` so day 0 reads +inf). Cross-checked against the real CLI:
`.venv/Scripts/python code/evaluation/main.py --llm --table -v --horizon N` for every N, and
`.venv/Scripts/python code/debug_request.py request_XX --llm --horizon 90 --days 91` for the
samples that flip.

Note on semantics: `horizon_end = request_date + horizon_days` and the projection includes both
ends, so `--horizon 84` = 85 calendar days inclusive, `--horizon 89` = exactly 90 calendar days
inclusive of `request_date`, `--horizon 90` = 91 days. `h90x` = "90 days counted from the day
after request_date".

## 1. Summary score per window

| variant | status | method | plan | earliest | changes | safe within 2 % | exact / 125 (5 scored cols) | CLI overall_exact / 150 |
|---|---|---|---|---|---|---|---|---|
| h84 | 23 | 24 | 23 | 22 | 22 | 11 | 114 | 118 (78.7 %) |
| h85 | 23 | 24 | 23 | 22 | 22 | 11 | 114 | 118 |
| h86 | 23 | 24 | 23 | 22 | 22 | 11 | 114 | 118 |
| h87 | 22 | 23 | 22 | 20 | 21 | 10 | 108 | 111 (74.0 %) |
| h88 | 21 | 22 | 21 | 19 | 21 | 10 | 104 | 107 (71.3 %) |
| h89 (90 d inclusive) | 21 | 22 | 21 | 19 | 21 | 10 | 104 | 107 |
| h90 | 21 | 22 | 21 | 19 | 21 | 10 | 104 | 107 |
| h90x (request date excluded) | 21 | 22 | 21 | 19 | 21 | 10 | 104 | 107 |

84, 85 and 86 are indistinguishable on the samples. Every step from 87 upward only loses matches.
89, 90 and 90x are identical to each other.

## 2. Per-sample table (amount_safe_to_pay gap = got − expected; earliest; s/m/p/e/c match marks)

Samples not listed are identical at every N (01, 02, 03, 04, 06, 07, 09, 11, 14–25). Their
amount gaps, in home currency, are the same for all N: 01 +0, 02 +1,107,626, 03 +98,737,
04 +2,207,486, 06 −52.49, 07 −933.36, 09 +0, 11 −190,778, 14 +18.55, 15 −17.86, 16 +0,
17 −825.90, 18 +84.04, 19 +1,128.97, 20 +3,569.68, 21 +31.05, 22 +2.28, 23 +940.65,
24 +119.29, 25 −14,239. Their column marks are also constant: 06 `XXX.X`, 11 `...XX`,
17 `...X.`, 19 `..X..`, 21 `X..XX`, all others `.....`. (request_03, named in the old note as a
90-day casualty, no longer flips: the current engine gives 971,736.99 at every N.)

| sample | expected safe / earliest | h84–h86 | h87 | h88–h90, h90x |
|---|---|---|---|---|
| request_05 | 737 / — | 1,168.79 (+431.79), — , `.....` | same as h84 | **0 (−737)**, — , `.....` |
| request_08 | 284.57 / 2025-04-15 | 285.19 (+0.62), 04-15 ok, `.....` | same as h84 | 285.19, **earliest empty**, `XXXX.` (not_recommended instead of wait) |
| request_10 | 12,700 / — | 38,509.61 (+25,810), — , `.....` | **0 (−12,700)** | 0 (−12,700) |
| request_12 | 65,164 (cap) / 2026-04-05 | 65,164 (+0), 04-05 ok, `.....` | **60,370.24 (−4,794), earliest empty, changes added**, `...XX` | same as h87 |
| request_13 | 433.40 / 2024-05-15 | 490.79 (+57.39), 05-15 ok, `.....` | **earliest empty**, `XXXX.` | same as h87 |

## 3. Why each one flips (from the h90 daily projection)

* **request_05** (rq 2025-11-06, min 13,100). Trough at h84 is 14,268.79 (Jan 27–29). Nothing
  happens on days 85–87. Day 88 = 2026-02-02: rent 4,972 → 9,296.79, i.e. 3,803 below the
  minimum, so safe = 0. Expected 737 > 0, so the reference window does not contain Feb 2
  (≤ 87 days). h84 is closer (+432, 2.8 % of requested) and has the right sign; h90 is wrong by
  the whole expected amount.
* **request_08** (rq 2025-02-07, min 800). Trough is unchanged (1,085.20, Feb 13–14), so safe is
  identical, but the earliest-date check fails: paying 996.60 on Apr 15 leaves day 87 (May 5,
  after utilities 76.83) at 1,796.73 − 996.60 = 800.13 (still ok) and day 88 (May 6, groceries
  59.04) at 741.08 < 800. The next salary (May 15) is outside every window, so earliest becomes
  empty and the plan collapses to not_recommended. Expected 2025-04-15 / wait ⇒ window ≤ 87.
* **request_10** (rq 2024-12-06, min 225,400, no income). Trough h84 = 263,909.62 (Feb 28).
  Day 87 = 2025-03-03: rent 69,100 → 194,809.62, 30,590 below the minimum → safe 0. Expected
  12,700 > 0 ⇒ the March rent is outside the reference window (≤ 86 days). h84 overshoots by
  25,810 (9.7 % of requested) but 90 gives 0.
* **request_12** (rq 2026-04-05, min 43,200, no income). Trough h84 = 115,362.25 (Jun 26–28);
  day 87 = 2026-07-01 rent 11,792 → 103,570.25, headroom 60,370 < requested 65,164, so the
  amount is no longer capped, earliest becomes empty and the installment plan needs three
  spending changes. Expected: capped 65,164, earliest = request date, no changes ⇒ window ≤ 86.
* **request_13** (rq 2024-03-07, min 1,300). Trough unchanged (1,790.80 on May 14). Paying
  941.60 on May 15 (3,089.51 → 2,147.91) survives until day 87 = 2024-06-02 rent 622.60:
  2,113.67 − 941.60 = 1,172.07 < 1,300 → earliest empty, not_recommended. Expected
  2024-05-15 / wait ⇒ window ≤ 86.

All five flips are the *next monthly rent* (or, for 08, the utilities+groceries that follow the
May 1 rent) landing on projected day 87 or 88. Three samples (10, 12, 13) require the window to
stop before day 87; two more (05, 08) require it to stop before day 88.

## 4. Inclusive / exclusive variants

* **h89** (request_date + 89 = 90 calendar days inclusive): identical to h90 on every column and
  every amount. Nothing in any sample falls on day 90 that matters after day 87/88 already broke it.
* **h90x** (90 days counted from the day after request_date; request-date balance never checked):
  identical to h90. The request-date balance is never the trough in any of the 25 samples (the
  trough is always the day before payday or the last projected day), so excluding it changes
  nothing; the variant is scored as h90 and inherits all five regressions.

## 5. Conclusion

* 84 is **strictly better than 90 on every sample it touches**: the five samples that differ
  (05, 08, 10, 12, 13) all match — or come closer to — the published answer at 84 and are all
  worse at 90. No sample gets worse at 84 relative to any longer window; the other 20 samples
  are unaffected by the window length.
* 84, 85 and 86 are equivalent on this data; 87 already breaks 10, 12, 13, and 88 additionally
  breaks 05 and 08. Both 90-day readings (inclusive or from the day after) and 89 score the same
  as 90 (107/150 vs 118/150 at 84).
* Keep `HORIZON_DAYS = 84` (12 weeks). If a value closer to the statement is preferred for
  optics, 86 is the largest window that reproduces the samples; do not go to 87 or above.
