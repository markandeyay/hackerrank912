# 1 — Residual back-solve of the reference reserve (improve3 / subagent 1)

Scripts (engine untouched; all under `code/notes/improve3/`):

* `1_residual_backsolve.py [table|hyp|exact|detail|all]` — builds the engine state for the 25 samples (`use_llm=True`, cached
  evidence), reconstructs the reference's implied reserve on the binding day, subtracts every certain item, and scores the
  hypotheses (a)–(f). Dumps `1_residual_backsolve.json`. Outputs: `1_hyp.out`, `1_exact.out`.
* `1_probe.py` — per-series estimator vs the implied nominal range, structural-sample dates, wider count search, horizon test
  (`1_probe.out`).
* `1_probe2.py` — scan of the binding day T, certain-item listing of the structural samples, monthly-rate test (`1_probe2.out`).

## 0. Formula and binding day

Per sample, home currency:

```
head      = current_available_balance − minimum_balance_to_keep
ref_res   = head − expected amount_safe_to_pay                (reference reserve; 21 uncapped samples)
T         = engine trough = first argmin of daily_balances(st)
credits   = projected salary / income / known credits with request_date ≤ date ≤ T
R         = ref_res + credits                                  = every debit the reference counted in [request_date, T]
certain   = pending / scheduled / retry / image-amount debits in [rq, T]
          + constant-amount series (rent, subscriptions, debt, insurance, education, gym, memberships, family support) × occ
          + leaked series (k × minimum_allowed_amount) × occ
residual  = R − certain                                        = reference's Σ occ × hidden nominal of the fixed categories
engine block = Σ occ × engine amount (clamped, grid-snapped mean) over the same series and the same occurrence counts
```

Binding day: the engine's trough is payday − 1 in 17 samples, the horizon end in the three no-income samples (05, 10, 12) and
2024-05-14 (second pay cycle) in 13. The alternative T′ = first payday − 1 differs from T only in 01, 04, 06, 07, 08, 13, 16, 24 and,
except for 13 and 16, the residual is identical at T and T′ (no flow in between). A full scan of T over the 84-day window
(`1_probe2.py`) shows that the engine's T is the **unique** day on which the residual is band-feasible (see §2) for 14 samples,
one of 2–3 equivalent days for 07/08/24, the day before the engine's T for 15 (the reference does not count the transport
occurrence on payday − 1), and **no day at all** for 04, 05, 06, 10 — those four differ from us in occurrence counts on every
possible binding day.

## 1. Residual table

Residual = reference's fixed-category block; "engine" = our block for the same series and counts. Counts in parentheses are the
engine's occurrences up to T. Capped samples (01, 09, 12, 16) give only an upper bound on the reserve and are excluded below.

| req | cur | balance | minimum | salary / first payday | expected | engine | ref reserve | certain | residual | engine block | resid − eng | rel | T | unknown series (occ) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 02 | IDR | 60,383,889 | 29,158,400 | 42,750,000 / 08-15 | 17,229,139 | 17,226,039 | 13,996,350 | 6,193,050 | 7,803,300 | 7,806,400 | −3,100 | −0.04 % | 2025-08-14 | utilities(1) healthcare(1) groceries(1) transport(1) dining(1) |
| 03 | IDR | 5,810,300 | 2,668,700 | 4,365,000 / 09-15 | 873,000 | 884,100 | 2,268,600 | 1,539,000 | 729,600 | 718,500 | +11,100 | +1.54 % | 2019-09-14 | utilities(1) groceries(1) transport(1) dining(1) |
| 04 | IDR | 52,206,950 | 30,686,600 | 38,190,000 / 06-15 | 8,401,800 | 10,629,300 | 13,118,550 | 4,826,950 | 8,291,600 | 6,064,100 | +2,227,500 | +36.7 % | 2024-06-13 | utilities(1) groceries(1) transport(1) dining(1) |
| 05 | ZAR | 46,475.10 | 13,100 | none | 737 | 1,226 | 32,638.10 | 16,916.90 | 15,721.20 | 15,232.20 | +489.00 | +3.21 % | 2026-01-27 (end) | utilities(3) healthcare(3) groceries(12) transport(6) |
| 06 | EUR | 1,942.40 | 800 | 1,037.52 / 01-15 | 603.30 | 554.30 | 539.10 | 304.10 | 235.00 | 284.00 | −49.00 | −17.3 % | 2026-01-13 | utilities(1) shopping(1) groceries(1) transport(2) dining(2) |
| 07 | INR | 218,946 | 93,000 | 149,000 / 09-23 | 87,171 | 86,491 | 38,775 | 22,325 | 16,450 | 17,130 | −680 | −3.97 % | 2024-09-20 | utilities(1) groceries(1) transport(1) |
| 08 | EUR | 1,536.57 | 800 | 1,422.85 / 02-15 | 284.57 | 284.57 | 452.00 | 353.00 | 99.00 | 99.00 | 0 | 0 | 2025-02-13 | groceries(1) transport(1) |
| 10 | INR | 750,155 | 225,400 | none | 12,700 | 39,170 | 512,055 | 232,955 | 279,100 | 252,630 | +26,470 | +10.5 % | 2025-02-28 (end) | utilities(3) groceries(12) transport(12) |
| 11 | IDR | 63,531,795 | 34,140,600 | 23,256,000 / 05-15 | 12,510,645 | 12,338,045 | 16,880,550 | 8,879,650 | 8,000,900 | 8,173,500 | −172,600 | −2.11 % | 2025-05-14 | utilities(1) healthcare(1) groceries(1) transport(1) |
| 13 | EUR | 2,789.52 | 1,300 | 1,343.54 / 03-15 | 433.40 | 470.40 | 1,056.12 | 1,578.20 | 2,165.00 | 2,128.00 | +37.00 | +1.74 % | 2024-05-14 | utilities(2) entertainment(3) groceries(10) transport(9) dining(5) |
| 14 | EUR | 3,931.74 | 2,200 | 2,717 / 08-15 | 597.74 | 613.74 | 1,134.00 | 717.00 | 417.00 | 401.00 | +16.00 | +3.99 % | 2025-08-14 | utilities(1) healthcare(1) groceries(1) transport(1) |
| 15 | EUR | 1,770.05 | 1,200 | 1,661 / 01-15 | 83.05 | 58.05 | 487.00 | 298.00 | 189.00 | 214.00 | −25.00 | −11.7 % | 2026-01-14 | utilities(1) groceries(1) transport(2) |
| 17 | INR | 550,380 | 166,100 | 206,000 / 03-15 | 243,850 | 242,920 | 140,430 | 103,060 | 37,370 | 38,300 | −930 | −2.43 % | 2026-03-14 | utilities(1) groceries(2) transport(2) |
| 18 | EUR | 2,486.00 | 1,400 | 2,310 / 07-15 | 462.00 | 462.00 | 624.00 | 223.00 | 401.00 | 401.00 | 0 | 0 | 2026-07-14 | utilities(1) healthcare(1) groceries(1) transport(1) |
| 19 | INR | 199,545 | 92,800 | 131,000 / 09-15 | 28,820 | 29,700 | 77,925 | 54,425 | 23,500 | 22,620 | +880 | +3.89 % | 2024-09-14 | utilities(1) healthcare(1) groceries(1) transport(1) |
| 20 | INR | 102,609 | 64,500 | 108,000 / 02-15 | 5,400 | 5,340 | 32,709.05 | 20,059.05 | 12,650 | 12,710 | −60 | −0.47 % | 2026-02-14 | healthcare(1) groceries(1) transport(1) |
| 21 | USD | 3,911.35 | 1,800 | 2,256 / 04-15 | 1,543.35 | 1,548.35 | 568.00 | 317.00 | 251.00 | 246.00 | +5.00 | +2.03 % | 2026-04-14 | utilities(1) groceries(1) transport(1) |
| 22 | EUR | 1,132.46 | 500 | 616 / 12-15 | 475.46 | 476.46 | 157.00 | 71.00 | 86.00 | 85.00 | +1.00 | +1.18 % | 2024-12-14 | utilities(1) groceries(1) transport(1) dining(1) |
| 23 | ZAR | 51,957.90 | 27,000 | 45,760 / 05-15 | 9,152 | 9,248.40 | 15,805.90 | 8,972.70 | 6,833.20 | 6,736.80 | +96.40 | +1.43 % | 2025-05-14 | utilities(1) healthcare(1) groceries(1) transport(1) |
| 24 | INR | 85,045 | 51,000 | 61,000 / 01-15 | 13,420 | 13,540 | 20,625 | 7,685 | 12,940 | 12,820 | +120 | +0.94 % | 2026-01-13 | utilities(1) shopping(1) entertainment(1) groceries(1) transport(2) |
| 25 | IDR | 32,063,050 | 23,379,100 | 28,499,994 / 03-15 | 1,425,000 | 1,416,600 | 7,258,950 | 1,604,550 | 5,654,400 | 5,662,800 | −8,400 | −0.15 % | 2024-03-14 | utilities(1) shopping(1) entertainment(1) groceries(1) transport(1) dining(1) |

Every one of the 21 residuals sits exactly on the item grid (IDR 100, INR 10, ZAR 0.2, EUR/USD 1) — the certain block is exact
and the residual is a sum of grid nominals. Our block is within 1 % in 6/21, within 2 % in 11/21; the sign is mixed (+ in 12,
− in 8), mean signed error +2.3 % dominated by 04; excluding 04/05/06/10/15 the mean signed error is +0.4 %, i.e. no bias.

## 2. What the residual can and cannot be (band + grid constraint)

Under the verified noise model (`observed = nominal × U(1−a, 1+a)`, a = 0.28 / 0.12, nominal on the grid) every hidden nominal
must lie in `[max/(1+a), min/(1−a)]`, so the residual must lie in `[Σ occ·L, Σ occ·U]` and be reachable as an integer
combination of grid points. A DP (`exact` mode) counts the exact solutions and, for the samples where the count is small, pins
each nominal to a range.

| | samples |
|---|---|
| residual inside the band interval under our counts | **16/21** (02 03 07 08 11 13 14 17 18 19 20 21 22 23 24 25) |
| with an exact grid solution under our counts | **15/21** (13 is inside but the 10×/9× lattice misses by one grid point) |
| outside on every binding day | 04 (+424 % of the way), 05 (+134 %), 06 (−310 %), 10 (+366 %), 15 (−62 %) |
| nominals pinned exactly (one solution) | 08: groceries 62, transport 37 (engine 62 / 37); 22: utilities 31, groceries **25**, transport 13, dining 17 (engine 31 / 24 / 13 / 17) |

So for 16 of 21 samples the reference is fully consistent with "hidden nominal × the engine's occurrence layout", and the
remaining block error is estimation noise on the nominal; for five it is not an amount problem at all.

## 3. Hypothesis scoreboard (block within 1 % of the residual, of the 21 uncapped samples)

| # | hypothesis | within 1 % | within 2 % | verdict |
|---|---|---|---|---|
| (a) | residual is a multiple of 100 / 500 / 1000 grid units | 0 / 0 / 0 exact (11 / 7 / 7 within 1 %, no better than chance for large IDR values) | | dead — 21/21 on the item grid only |
| (b) | nominal = fixed fraction of salary per category | leaked nominal/salary over all payroll users: CV 0.23 (dining), 0.33 (entertainment), 0.25 (shopping), 0.24 (streaming), 0.47 (gym); ranges 3× wide | | dead — budgets are not salary-scaled; the fixed block's residual/salary spans 0.07–0.34 |
| (c) | first observed amount | 0 | 1 | dead |
| (c) | last observed | 2 | 4 | dead |
| (c) | row ≈ 3 months / ≈ 1 month before request | 2 / 2 | 5 / 6 | dead |
| (d) | mean (engine before pass 2) | 4 | 8 | |
| (d) | mean → grid / → 10× grid / 2 sf / 3 sf | 4 / 4 / 3 / 4 | 8 / 8 / 7 / 7 | rounding the mean never helps |
| (d) | **engine: mean clamped into [L,U], snapped** | **6** | **11** | current |
| (d) | midrange (max+min)/2, plain or snapped | **7** | 11–12 | best point estimator, +1 sample |
| (d) | imid = (L+U)/2 | 5 | 12 | |
| (d) | median / last-3 mean / mean+½σ / L / U / max / min | 3 / 3 / 1 / 2 / 1 / 0 / 0 | ≤ 7 | dead |
| (e) | integer counts 0..3 per series, engine nominals, unconstrained | 18 "explained" | | degenerate (4–48 vectors fit by chance); see band-constrained version below |
| (e′) | counts ours ± 1 per periodic series, band + grid constraint | our counts exact in 15; **04 → (1,2,2,1)** groceries + transport twice, **05 → +1** groceries or transport, **06 → dining 2→1**, **13 → transport 9→10**, **15 → transport 2→1**; 10 needs +2 (utilities 4 or groceries 13–14) | | the only hypothesis that accounts for the five structural samples |
| (f) | engine block ± one occurrence of one series | +2 (05 +1 transport, 13 +1 entertainment) → 8 | | consistent with (e′) |
| (f) | sum of last / max / first amounts, same-window-last-month total, last-30-day total, last calendar month | 2 / 0 / 0 / 2 / 0 / 0 | | dead |
| (f) | k × monthly rate for the no-income samples | 05: 3 × (30 d/m) −1.9 %, 10: 3 × (31 d/m) −1.8 % — different k, different d/m | | not a rule |
| extra | mean of last 90 / 60 days; mean incl. image + linked rows; engine × 1.01 / 1.02; mean × (1 + a/n) | 3 / 1 / 4 / 5 / 5 / 5 | ≤ 11 | nothing beats clamp+snap |

**No hypothesis explains 20 of 25.** The best amount hypothesis (midrange) explains 7/21 (+4 capped = 11/25); the engine's
clamp+snap 6/21. The structural half of the error is occurrence counts, not amounts (§4).

## 4. Per-series evidence (where the sum pins the nominals)

29 series have an implied range narrower than 6 % of the amount (`1_probe.py`). Estimator inside that range
(within half a grid step):

| estimator | hits / 29 |
|---|---|
| midrange | **25** |
| engine (clamp + snap) | 22 |
| imid | 22 |
| mean | 14 |
| median | 9 |
| last observed | 2 |

Where the engine misses and the midrange hits: 17 utilities [9,150–9,450] (engine 9,540, mid 9,367), 17 groceries [8,940–9,090]
(engine 9,100, mid 9,070), 17 transport [5,020–5,170] (engine 5,280, mid 5,162), 14 utilities [154–160] (engine 148, mid 149 —
both miss; only the last row 153.7 is close), 19 healthcare [9,020–9,470] (engine 8,810; only imid 9,030 hits), 22 groceries = 25
(engine 24, mean 23.95, mid 24.08 — every estimator misses; a −1.3 σ draw of 26 rows). Sample 07's groceries must be ≤ 6,860 while
every estimator says 7,020–7,280, i.e. 07 (−4 %) is either an unlucky nominal or a count difference the ±1 search did not cover
(its T-scan is feasible on 09-20..09-22).

The midrange is the efficient estimator for uniform noise (variance ∝ 1/n² vs 1/n for the mean), which is why it wins on the
long groceries/transport series. It was re-scored end-to-end in `improve2/1_noise_band.md` (w1 14, w2 16, but it flips
request_11's plan → 118 columns) — the per-series evidence here says it is right more often, the end-to-end cost is the
knife-edge in request_11, not the estimator.

## 5. The structural five (dates from `1_probe.out`)

| req | reference vs engine | dates |
|---|---|---|
| 04 | groceries 2 (not 1), transport 2 (not 1) | request 06-04, payday 06-15; engine groceries 06-08 (next 06-15), transport 06-09 (next 06-16). The reference counts 06-15 (payday) and 06-16 (payday + 1) yet still lands the salary on 06-15 (earliest date 06-15). No binding day with our credits is feasible. |
| 06 | dining 1 (not 2) | request 01-03, payday 01-15; engine dining 01-04 (request + 1) and 01-11; the reference drops 01-04. |
| 15 | transport 1 (not 2) | request 01-06, payday 01-15; engine transport 01-07 and 01-14 (payday − 1); the reference's feasible binding day is 01-13, i.e. it drops the 01-14 occurrence. |
| 05 | one more weekly / fortnightly occurrence | no income, trough = horizon end 01-27; engine groceries ×12 (7-day, last 01-27), transport ×6 (14-day, last 01-21). A 90-day horizon gives 13/7 but also pulls the 02-02 rent into the window, which the reference did not count (residual would drop to 10,749). |
| 10 | +2 occurrences (utilities 4 or groceries 13–14) | no income, trough = horizon end 02-28; engine utilities ×3 (12-07, 01-07, 02-07), groceries ×12, transport ×12. Same horizon contradiction as 05 (rent 03-03 not counted, but a 4th utilities on 03-07 or a 13th grocery on 03-06 would be). |
| 13 | transport 10 (not 9) | second pay cycle; engine transport 03-13 … 05-08, next 05-15 = payday; the reference counts one more (on payday?). |

Three of the five (04 payday/payday + 1 counted, 13 payday counted, 15 payday − 1 not counted, 06 request + 1 not counted) are
about which periodic occurrence adjacent to a payday or to the request date is counted, and they point in opposite directions
(04/13 count more around payday, 15/06 count fewer). The no-income pair (05, 10) both need roughly a 90-day count of the
periodic series while excluding the monthly rent that a 90-day window would include — consistent with a reference that
projects each series for ~3 months (13 weekly, 6–7 fortnightly, 3–4 monthly occurrences) rather than by a hard calendar
window, but two samples cannot fix that.

## 6. Bottom line

* The residual is exactly a sum of grid nominals in 21/21 samples; under our occurrence layout it is band-feasible in 16/21
  and exactly solvable in 15/21, so for those the remaining error (0–4 %) is estimation noise on 5–26 uniform draws, not a
  hidden rule. Nothing in the amount space (coarse rounding, salary fractions, first/last/dated rows, rounded means, windowed
  means, monthly rates) beats the engine's clamp+snap by more than one sample; the midrange is the best point estimator
  (7/21 block within 1 %; 25/29 pinned series vs 22/29) and the only amount change worth re-testing end-to-end.
* The other five samples (04, 05, 06, 10, 15 — plus 13 by one lattice step) are occurrence-count differences of exactly one
  (04: two) periodic occurrence adjacent to a payday, the request date, or the horizon end; no single amount hypothesis can
  reach 20/25 because five residuals lie outside the feasible band on every binding day.
