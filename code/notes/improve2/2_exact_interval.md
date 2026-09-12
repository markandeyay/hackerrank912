# Exact-interval projection (variant E / H) vs the current rule

Scripts (read-only against the engine, deterministic evidence path `use_llm=False`):
`code/notes/improve2/gap_stats.py` (task 1) and `code/notes/improve2/exact_interval_variants.py` (task 2).
Baseline re-checked first with `code/evaluation/main.py --table` (no `--llm`): 121/150, 17/25 within 2 %,
total |gap| 2,459,465.75 - identical to the documented state.

## 1. Gap statistics (all 275 users of `requests.csv` + `sample_requests.csv`)

Series grouped exactly as `StateBuilder._build_debit_series` does (settled debits per category, same exclusions,
>= 3 rows, median gap <= 45 d): **2,444 engine series** (1,644 monthly, 800 short-cycle).

| measure | engine per-category series | per-description series |
|---|---|---|
| series | 2,444 | 3,496 |
| short-cycle (median gap < 28 d) | 800 | 890 |
| short-cycle with *all gaps identical* | **800 / 800 (100 %)** | 50 / 890 (5.6 %) |
| short-cycle step distribution | 5 d: 46, 7 d: 269, 10 d: 131, 14 d: 206, 21 d: 148 | median gaps spread over 5..27 d; individual gaps 5..154 d |
| monthly series | 1,644 | 2,606 |
| monthly: same day-of-month every time | **1,644 / 1,644** | 1,644 / 2,606 |
| monthly: constant day gap | 0 / 1,644 (gaps 28/29/30/31 follow the calendar) | 31 / 2,606 |
| monthly series with DOM >= 29 | 0 | 300 (all irregular) |

* Every one of the 800 pooled short-cycle category series (groceries 275, transport 275, dining 250; each pools 5-8
  descriptions) has a **perfectly constant gap**. The individual gap counts are 5 d x 1,589, 7 d x 6,623, 10 d x 2,227,
  14 d x 2,472, 21 d x 1,184 - no other value occurs. So last gap = mode gap = median gap = the engine's `step`.
* Per description the same series look random (e.g. user_27 "Supermarket basket": gaps 7,7,14,14,21,28,63): the
  generator draws a description from the category pool at each occurrence. Per-description projection would be wrong;
  the engine's per-category pooling is the right grouping.
* Monthly series always keep the day of month (never DOM 29-31), so `add_months` is exactly right and "last + 30 days"
  is not (confirmed below by `E_mon`, and earlier by `monthly30` in `reserve_hypotheses.md`).

Consequence: the "exact interval" is already what the engine uses. The only degrees of freedom that remain are the
request-date skip and the bring-forward rule, which is what the variants below measure.

## 2. Variant comparison (25 samples)

Columns: exact matches per column (amount / status / method / plan / earliest / changes), overall exact of 150,
amount within 1 % and 2 %, sum of |got - want| over the 25 amounts.

| variant | amt st meth plan earl chg | overall | within 1 % | within 2 % | total abs error | lost vs current |
|---|---|---|---|---|---|---|
| **current** (median gap, skip request_date, bring-forward) | 4 24 24 23 23 23 | **121/150** | **12** | **17** | **2,459,466** | - |
| E_last (last gap; no skip, no bring-forward) | 4 23 24 23 22 22 | 118/150 | 7 | 9 | 4,670,368 | request_21: status, earliest, changes |
| E_mode (mode gap; no skip, no bring-forward) | identical to E_last on all six columns | | | | | |
| E_last_skip / E_mode_skip (+ request-date skip) | 4 23 24 23 22 22 | 118/150 | 9 | 11 | 3,638,808 | request_21: status, earliest, changes |
| E_last + skip + bring-forward | identical to current on all six columns | 121/150 | 12 | 17 | 2,459,466 | none |
| H (hybrid: exact for constant-gap, current for irregular) | identical to E_last (every series is constant-gap) | 118/150 | 7 | 9 | 4,670,368 | request_21 x3 |
| H_skip | identical to E_last_skip | 118/150 | 9 | 11 | 3,638,808 | request_21 x3 |
| E_mon (E_last + monthly at last + last gap) | 4 21 23 22 21 22 | 113/150 | 8 | 11 | 3,169,359 | 11 columns (06 earliest, 11 x3, 13 x4, 21 x3); gains 06 method/plan, 17 earliest |

Per-sample amount error (got - want; `/n` = non-amount columns matched of 5) for the samples the task names:

| sample | want | current | E (no skip/no bf) | E_skip | what E changes |
|---|---|---|---|---|---|
| request_02 | 17,229,139.20 | +23,807 /5 (+0.2 % res) | +1,107,626 /5 (+7.9 %) | same as E | dining 21 d: bring-forward removed, 0 occurrences before payday |
| request_03 | 873,000 | +11,094 /5 (+0.5 %) | +102,135 /5 (+4.5 %) | same | transport 21 d: bring-forward removed |
| request_04 | 8,401,800 | +2,207,587 /5 (+16.8 %) | **unchanged** | **unchanged** | groceries last 06-01 -> 06-08, 06-15; transport last 06-02 -> 06-09, 06-16: the exact interval gives exactly the dates the engine already projects |
| request_06 | 603.30 | -52.49 /1 (-9.7 %) | -79.47 /1 (-14.7 %) | **unchanged** -52.49 | dining last 12-28 + 7 = 01-04, 01-11: still two occurrences before 01-15; without the skip the 5-day transport lands on the request date (3rd occurrence) and makes it worse |
| request_18 | 462 | -2.96 /5 (-0.5 %) | +84.04 /5 (+13.5 %) | same | dining 14 d next = payday 07-15: bring-forward removed |
| request_20 | 5,400 | -62.05 /5 (-0.2 %) | +3,548 /5 (+10.9 %) | same | dining 21 d: bring-forward removed |
| request_21 | 1,543.35 | +4.99 /5 (+0.9 %) | +31.05 /2 (+5.5 %) | same | transport + dining next on 04-16 / 04-17: bring-forward removed; status `affordable_now` -> wrong, earliest and changes lost |
| request_23 | 9,152 | +96.35 /5 (+0.6 %) | -747.69 /5 (-4.7 %) | +984.78 (+6.2 %) | transport 14 d on payday: bring-forward removed; without the skip groceries also count on the request date |

Other samples touched by removing the skip (E vs E_skip): request_10 (-6 k better), 15 (-81 vs -21), 19 (-3,890 vs
+883), 22 (-10.86 vs +2.28), 25 (-1,048,917 vs -14,239) - the skip is confirmed by 15, 19, 22, 25.

## 3. What this says about request_04 and request_06

* **request_04**: the exact interval reproduces the engine's projection date for date (weekly groceries 06-08 and
  06-15, weekly transport 06-09 and 06-16). The reference's extra ~2.2 M IDR (one more grocery and one more
  transport occurrence) is not an interval effect; it is the payday-ordering question already documented in
  `reserve_hypotheses.md` section 3 (items on payday / payday + 1 counted before the salary), which breaks samples 24
  and 25 when generalised. No exact-interval variant moves this sample by a single rupiah.
* **request_06**: dining last settled 12-28, gap 7 -> 01-04 and 01-11 both precede the 01-15 payday under every
  interval rule (last, mode, median are all 7). The reference's single dining occurrence therefore cannot come from an
  interval choice; it remains the "skip request_date + 1" anomaly supported by this sample alone (`trace_request_06.md`).
  Dropping the request-date skip makes 06 worse (the 5-day transport lands on 01-03 = request_date).

## 4. Recommendation

**Keep the current rule.** The engine already projects every short-cycle series at its exact observed interval (all 800
series have a constant gap, so median = last = mode) and every monthly series on its exact day of month (1,644/1,644);
variant E and the hybrid H are therefore the current rule minus the request-date skip and minus the bring-forward, and
both pieces are individually confirmed by the samples:

* the bring-forward rule is worth 3 exact columns (request_21) and 6-8 samples within 2 % (02, 03, 18, 20, 21, 23);
* the request-date skip is worth 2 within-2 % samples and a 1.0 M reduction of total absolute error (15, 19, 22, 25).

Every E/H variant loses currently matching columns (request_21 x3), so none is adoptable under the "no lost column"
constraint; `E_last + skip + bring-forward` is byte-identical to the current output. The monthly "last + last gap"
variant is clearly worse (113/150). Neither request_04 nor request_06 is affected by any interval choice; they stay as
the open payday-ordering / request_date+1 outliers.
