# Occurrence-count study: what the reference counted before the binding day

Scripts (read-only against the engine, evidence path `--llm` cache, baseline re-checked at 123/150, 17/25 within 2 %):

* `code/notes/improve3/occurrence_counts.py counts` - implied-count solver per sample (part A);
  `... rules` - the rule scoreboard on all 25 samples with the full planner (part B).
* `code/notes/improve3/payday_hits.py` - every short-cycle occurrence on a payday / payday+1 / payday+2 in all 25 samples.
* `code/notes/improve3/before_after_tables.py` - the per-sample before/after table of section 5.

Method: for each sample the binding day is the engine's trough (the day before the first payday for 04, 06, 11, 15,
17, 19; the third pre-payday low 05-14 for 13; the horizon end for 10 and 05). Reference reserve = headroom - expected
amount. Known debits and constant-amount series are subtracted at their calendar count; the remaining "variable" total is
matched by integer counts of the variable series (short-cycle series: our count +-2, monthly variable series: +-1) at the
engine's current nominal amounts. Fits that change a monthly count are listed by the script but are implausible (a
monthly item cannot occur twice in a 10-day window), so the table below keeps the **short-cycle-only** fits.

## 1. Implied counts vs ours (short-cycle series only; residual as % of the reference reserve)

| sample | binding window | series (gap) | ours | dates ours | implied | dates the reference must have counted | residual |
|---|---|---|---|---|---|---|---|
| request_04 | 06-04..06-13 (payday 06-15) | groceries 7d / transport 7d / dining 14d | 1 / 1 / 1 | 06-08 / 06-09 / 06-10 | **2 / 2 / 1** | + groceries **06-15 (payday)**, + transport **06-16 (payday+1)** | ours -16.98 % -> **-0.64 %** |
| request_06 | 01-03..01-13 (payday 01-15) | groceries 10d / transport 5d / dining 7d | 1 / 2 / 2 | 01-07 / 01-08, 01-13 / 01-04, 01-11 | **1 / 2 / 1** | - dining **01-04 (request_date+1)** (or 01-11, same amount) | +9.09 % -> **+0.74 %** (alt. 2/2/0: +0.56 %) |
| request_10 | 12-06..02-28 (no income; horizon end) | groceries 7d / transport 7d / dining 14d | 12 / 12 / 6 | last 02-27 / 02-28 / 02-22 | **13 / 13 / 7** | + one of each **past the horizon end** (03-06 / 03-07 / 03-08) | -5.17 % -> **+0.17 %** (alt. 14/13/6: -0.21 %) |
| request_11 | 05-03..05-14 (payday 05-15) | groceries 10d / transport 14d / dining 21d | 1 / 1 / 1 | 05-08 / 05-11 / 05-14 | **1 / 1 / 1** | same as ours; the +1.02 % is nominal noise (no count fits better) | +1.02 % |
| request_13 | 03-07..05-14 (third pre-payday low) | groceries 7d / transport 7d / dining 14d | 10 / 9 / 5 | ... 05-14 / ... 05-08 / ... 05-09 | **10 / 10 / 5** | + transport **05-15 (third payday, = earliest date)** | -3.50 % -> **-0.85 %** |
| request_15 | 01-06..01-14 (payday 01-15) | groceries 7d / transport 7d / dining 14d | 1 / 2 / 1 | 01-13 / 01-07, 01-14 / 01-10 | **1 / 1 / 1** | - transport **01-07 (request_date+1)** | +5.13 % -> **-1.85 %** |
| request_17 | 03-01..03-14 (payday 03-15) | groceries 7d / transport 7d / dining 14d | 2 / 2 / 1 | 03-06, 03-13 / 03-07, 03-14 / 03-08 | **2 / 2 / 1** | same as ours; +0.66 % is nominal noise | +0.66 % |
| request_19 | 09-04..09-14 (payday 09-15) | groceries 7d / transport 14d | 1 / 1 | 09-11 / 09-12 | **1 / 1** | same as ours; -1.13 % is nominal noise (2 groceries would be +4.99 %) | -1.13 % |
| control request_05 | 11-06..01-27 (no income) | groceries 7d / transport 14d | 12 / 6 | last 01-27 / 01-21 | 12 / **7** or noise | + transport 02-04 past the horizon end (-0.23 %); groceries too would be +0.69 % -> the request_10 rule does **not** carry over | -1.50 % |
| control request_25 | 03-06..03-14 (payday 03-15) | groceries 10d / transport 5d / dining 7d | 1 / 1 / 1 | 03-09 / 03-10 / 03-13 | 1 / 1 / 1 | transport **03-15 (payday) is NOT counted** (+1 would be -8.0 %) | +0.12 % |

Between-payday windows (decide `earliest_date_for_full_payment`):

* **request_11**: paying on 06-15 passes at 07-14 by 751,545 in our layout; the reference's pre-trough reserve is 172,600
  *lower* than ours, so the reference must carry **>= 924,145 more debits in (05-14, 07-14]** than we do. One extra
  short-cycle occurrence of any series suffices (transport 1,088,000 / dining 1,331,900 / groceries 1,421,300); the
  candidates just outside the window are dining 21d **07-16 (third payday+1)** and groceries 10d **07-17 (payday+2)**.
  Our counts in the window: groceries 6, transport 4, dining 2, entertainment 2.
* **request_17**: paying on 03-15 must pass at 04-14; our window total (03-16..04-14: utilities 1, groceries 4,
  transport 4, dining 2 = 78,800 variable) exceeds the maximum the reference can have by **740.42 (0.42 % of the window)**
  after crediting our 930 pre-trough over-reserve. No short-cycle count change fits (the best, transport +1 & dining -1, is
  implausible); it is nominal noise, as `trace_request_17.md` concluded.

## 2. Payday evidence across all 25 samples (`payday_hits.py`)

Short-cycle occurrences on the first payday (+0) or the day after (+1), raw last+gap dates, and whether the reference
reserved them before the salary (from the reserve fit):

| sample | occurrence | reserved by the reference? |
|---|---|---|
| request_04 | groceries 7d 06-15 (+0), transport 7d 06-16 (+1) | **yes, both** (-0.64 % fit) |
| request_13 | transport 7d 05-15 (third payday, +0) | **yes** (-0.85 % fit) |
| request_21 | groceries 10d 04-16 (+1) | **no** (reserving it: -5.1 % and 4 columns lost) |
| request_24 | groceries 10d 01-16 (+1) | **no** (reserving it: -16.4 %) |
| request_25 | transport 5d 03-15 (+0) | **no** (reserving it: -8.0 %) |
| request_01, 09, 16 | 7d/10d/21d on +0/+1 | capped samples, no information |
| request_11 | dining 21d 07-16 (third payday +1) | **yes** is what the earliest date needs (section 1) |

So the only formulation consistent with the amounts is "**7-day** series on payday/payday+1 are charged before the salary,
5/10-day series are not" - a fit to two samples with no financial rationale (request_11's 21-day dining would also have to
be in). Occurrences on request_date+1 exist only in request_06 and request_15, and both samples say "not counted".
`event_date == settlement_date` on all 1,313 short-cycle rows of the 25 users (and on 23,451 of 23,480 settled debits),
so an event-date anchoring cannot explain any shift. desired_completion_date does not separate the cases either
(21: payday-1, but 24: payday+24, 25: payday+33).

## 3. Rule scoreboard (all 25 samples, full planner; columns = exact matches of amount, status, method, plan, earliest, changes)

| rule | amt st me pl ea ch | overall | within 2 % | gained | lost | amounts moved (error vs reference amount) |
|---|---|---|---|---|---|---|
| **baseline** | 6 24 24 23 23 23 | **123/150** | 17 | - | - | - |
| A1 skip the occurrence on request_date+1 | 6 24 24 23 23 23 | 123 | **18** | - | - | 06 -0.7 %, 15 +10.8 % (reserve +5.1 -> -1.85 %) |
| A2 skip rq+1 and re-anchor there | identical to A1 | 123 | 18 | - | - | same |
| A3 skip rq+2 | 6 24 24 23 23 23 | 123 | 15 | - | - | 20 +67 %, 24 +18 % (rq+2 IS counted) |
| B1 include the occurrence on request_date | 6 24 24 23 23 23 | 123 | 14 | - | - | 06, 10, 15, 19, 22, 23, 25 all worse |
| C1 count = ceil(days_to_payday / gap) | 5 21 21 20 22 20 | 109 | 9 | 11 earliest | 06 earl, 07 chg, 08 x5, 11 x3, 21 x4, 22 chg | 15 samples worse |
| C2 ceil((days+1)/gap) | 5 20 20 19 22 19 | 105 | 7 | 11 earliest | 19 cells | |
| C3 floor(days/gap) | 4 22 24 23 22 22 | 117 | 7 | - | 08 amt, 11 st, 18 amt, 21 x3 | 17 samples worse |
| C4 floor(days/gap), at least 1 | identical to A1 | 123 | 18 | - | - | 06, 15 |
| C5 floor((days+1)/gap), >= 1 | 6 24 24 23 23 23 | 123 | 17 | - | - | 06, 15, 25 -42 % |
| C6 round(days/gap), >= 1 | 6 24 24 23 23 23 | 123 | 16 | - | - | 04 -1.0 %, 14, 15, 19, 24, 25 worse |
| C7 ceil per pay cycle (every cycle) | 4 17 17 15 17 21 | 91 | 8 | 11 earliest | 31 cells | |
| C8 round per pay cycle, >= 1 | 6 24 24 23 23 23 | 123 | 16 | - | - | 04 -1.0 %, 13 +32 %, 14, 15, 19, 24, 25 worse |
| D1 at most 1 occurrence per cycle | 6 22 23 20 18 23 | 112 | 15 | 06 method+plan, 17 earliest | 06 earl, 08 x2, 11 x3, 13 x4, 18 x2, 22, 24 | |
| D2 at most 2 per cycle | 6 22 22 21 23 23 | 117 | 17 | 17 earliest | 11 x3, 13 x4 | 13 +117 % |
| E1 payday occurrence before the salary | 6 24 24 23 23 23 | 123 | 16 | - | - | 04 +8.7 %, 13 -2.1 %, 25 -42 % |
| E2 payday..payday+1 before the salary | 6 23 23 22 23 22 | 119 | 15 | 11 earliest | 06 earl, 21 x4 | 04 -1.0 %, 13, 21 -5.1 %, 24 -16 %, 25 -42 % |
| E3 E2 incl. monthly series | 6 22 21 21 22 20 | 112 | 11 | 11 earliest | 12 cells | |
| E4 / E5 E1 / E2 on the first payday only | 123 / 119 | 16 / 15 | - | - / 21 x4 | 04, 25 / 04, 21, 24, 25 |
| E6 E1 for gap >= 7 | 6 24 24 23 23 23 | 123 | 17 | - | - | 04 +8.7 %, 13 -2.1 % |
| E7 E2 for gap >= 7 | 6 23 23 22 23 22 | 119 | 16 | 11 earliest | 06 earl (10d groceries 02-16), 21 x4 (10d groceries 04-16) | 04 -1.0 %, 13, 21, 24 |
| **E8 E2 for gap == 7 only** | 6 24 24 23 23 23 | 123 | **18** | - | - | 04 -1.0 % (reserve +0.64 %), 13 -2.1 % (reserve +0.85 %) |
| E9 / E10 E8 / E1 on the first payday only, gap 7 | 123 / 123 | 18 / 17 | - | - | 04 only |
| F1 monthly series counted once before payday | identical to baseline (no sample has a double day-of-month hit) | 123 | 17 | - | - | - |
| G1-G3 calendar-month copy of the whole history | 1 10-11 ... | 63-65 | 1 | - | 50+ cells | every sample |
| G4 / G5 last-30-days copy forward (with / without bring-forward) | 5 23 23 22 20 19 | 112 / 111 | 12 / 6 | 11 earliest | 06 earl, 07 x2, 08 x5, 12, 17, 22 x2 | 04 unchanged (+16.8 %) |
| H1 reserve through desired_completion_date | 3 19 19 18 22 23 | 104 | 5 | - | 02 x3, 07 x3, 08, 11 x3, 16 x5, 18, 22 x3 | |
| I1 / I2 one extra occurrence at the horizon end (all / no-income samples) | 118 / 122 | 17 / 17 | - | 08 x4 + 12 chg / 12 chg | 05 -87 %, 10 +7.0 % (reserve +0.17 %) |
| J0 A1 + E9 | 6 24 24 23 23 23 | 123 | **19** | - | - | 04 -1.0 %, 06 -0.7 %, 15 +10.8 % |
| J1 A1 + E2 | 6 23 23 22 24 22 | 120 | 16 | 11 earliest | 21 x4 | |
| J2 A1 + E1 | 123 | 17 | - | - | 04, 06, 13, 15, 25 |
| J3 A1 + I2 | 122 | 18 | - | 12 chg | 05, 06, 10, 15 |
| J4-J7 other combinations | 91-119 | | | | see the `rules` output of the script | |

## 4. Answer to the question

**No single scheduling rule fixes two of the eight misses without breaking an exact sample.** The eight misses need
three *different* and mutually incompatible interventions:

1. **request_06 and request_15** want the occurrence on **request_date+1** dropped (A1). It is the only rule with no
   counter-example in the samples (rq+1 occurs nowhere else; rq+2 is counted in 20 and 24, rq+0 is skipped in 15/19/22/23/25),
   but it fixes no column: request_06 still needs its reserve 4 EUR lower (utilities + shopping nominals) to turn `wait`
   into `full_payment` + `stop:event_476`, exactly as `trace_request_06.md` predicted.
2. **request_04 and request_13** want a **7-day occurrence on the payday (and payday+1 for 04) charged before the
   salary**, which 21, 24 (10-day, payday+1) and 25 (5-day, payday) explicitly refuse. The gap-7 restriction (E8) is the
   only consistent phrasing and is a two-sample fit.
3. **request_11** wants one more short-cycle occurrence between the second and third payday (the 21-day dining on
   07-16 = payday+1 fits) - i.e. rule 2 without the gap restriction, which is what breaks 06 and 21.
4. **request_10** wants one extra occurrence of every short-cycle series at the horizon end; request_05 (also no
   income) refuses two of them, and I2 breaks request_12's spending changes.
5. **request_17 and request_19** have the same counts as the reference in every window (0.42 % and 1.13 % nominal noise).

**Best partial rule and its cost**: A1 (skip request_date+1): 123/150 unchanged, within-2 % 17 -> 18, total |gap| down
by 49 EUR + 34 EUR, no cell lost, supported by two samples and contradicted by none. Adding E8 (weekly series on
payday/payday+1 before the salary) gives 19/25 within 2 % (J0), still 123/150 and no cell lost, but E8 is a post-hoc
category-specific exception (5-day and 10-day series behave the opposite way in 21, 24, 25) and should not ship.

## 5. Before/after table (A1, E8, A1+E8; value = amount, in brackets the reserve error, `*` = within 2 %)

| sample | want | baseline | A1 skip rq+1 | E8 weekly on payday/+1 | A1+E8 | non-amount cols |
|---|---|---|---|---|---|---|
| request_01 | 25,256.00 | 25,256.00 (+0.00%) * | same | same | same | 5/5 |
| request_02 | 17,229,139.20 | 17,226,039.20 (+0.02%) * | same | same | same | 5/5 |
| request_03 | 873,000.00 | 884,100.00 (-0.49%) * | same | same | same | 5/5 |
| request_04 | 8,401,800.00 | 10,629,300.00 (-16.98%) | same | **8,317,200.00 (+0.64%) \*** | 8,317,200.00 (+0.64%) * | 5/5 |
| request_05 | 737.00 | 1,226.00 (-1.50%) | same | same | same | 5/5 |
| request_06 | 603.30 | 554.30 (+9.09%) | **599.30 (+0.74%) \*** | 554.30 (+9.09%) | 599.30 (+0.74%) * | 1/5 |
| request_07 | 87,170.56 | 86,490.56 (+1.75%) * | same | same | same | 5/5 |
| request_08 | 284.57 | 284.57 (+0.00%) * | same | same | same | 5/5 |
| request_09 | 166.61 | 166.61 (+0.00%) * | same | same | same | 5/5 |
| request_10 | 12,700.00 | 39,170.00 (-5.17%) | same | same | same | 5/5 |
| request_11 | 12,510,645.00 | 12,338,045.00 (+1.02%) * | same | same | same | 3/5 |
| request_12 | 65,164.00 | 65,164.00 (+0.00%) * | same | same | same | 5/5 |
| request_13 | 433.40 | 470.40 (-3.50%) | same | **424.40 (+0.85%)** | 424.40 (+0.85%) | 5/5 |
| request_14 | 597.74 | 613.74 (-1.41%) | same | same | same | 5/5 |
| request_15 | 83.05 | 58.05 (+5.13%) | **92.05 (-1.85%)** | 58.05 (+5.13%) | 92.05 (-1.85%) | 5/5 |
| request_16 | 122,500.00 | 122,500.00 (+0.00%) * | same | same | same | 5/5 |
| request_17 | 243,849.58 | 242,919.58 (+0.66%) * | same | same | same | 4/5 |
| request_18 | 462.00 | 462.00 (+0.00%) * | same | same | same | 5/5 |
| request_19 | 28,820.00 | 29,700.00 (-1.13%) | same | same | same | 4/5 |
| request_20 | 5,400.00 | 5,340.00 (+0.18%) * | same | same | same | 5/5 |
| request_21 | 1,543.35 | 1,548.35 (-0.88%) * | same | same | same | 5/5 |
| request_22 | 475.46 | 476.46 (-0.64%) * | same | same | same | 5/5 |
| request_23 | 9,152.00 | 9,248.40 (-0.61%) * | same | same | same | 5/5 |
| request_24 | 13,420.00 | 13,540.00 (-0.58%) * | same | same | same | 5/5 |
| request_25 | 1,425,000.00 | 1,416,600.00 (+0.12%) * | same | same | same | 5/5 |
| **non-amount cells / within 2 % / exact amounts** | | 117/125 / 17 / 6 | 117/125 / 18 / 6 | 117/125 / 18 / 6 | 117/125 / 19 / 6 | |

The six exact amounts (01, 08, 09, 12, 16, 18) and all 123 matching cells are preserved by A1, E8 and A1+E8; no other
rule in section 3 keeps them while fixing anything. Recommendation: keep the engine as it is; if a zero-risk tweak is
wanted, A1 (skip the request_date+1 occurrence) is the only one with no counter-example in the samples.
