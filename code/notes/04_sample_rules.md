# 04 — Reverse-engineering the 25 solved samples (`dataset/sample_requests.csv`)

Companion files: `04_sample_reconstruction.json` (per-sample numbers) and
`04_sample_sim_prototype.py` (the throw-away simulator used for every number below;
run `.venv/Scripts/python code/notes/04_sample_sim_prototype.py mean dom -strict -h84 -g`).

## 0. Headline findings

1. **`amount_safe_to_pay` = clamp( min over the forecast window of (projected balance) − `minimum_balance_to_keep`, 0, `requested_amount`).**
   The projection starts from `current_available_balance` on `request_date`, adds/subtracts only cash events, and includes
   the request date itself.
2. **The variable-expense forecast cannot be reproduced exactly.** The organizers' reserve is always a round number
   (13,996,350; 2,268,600; 452; 487; 1,134; 624 …) even though the histories have cents, so the reference uses hidden
   nominal amounts (the generator's base values), not any statistic of the history. The historical **mean** is the closest
   estimator (median second); mean relative reserve error 5.7 % over the 21 uncapped samples, and 8 of them within 2 %.
   `max`, `mean+std`, `last`, `last 3`, 75th percentile are all clearly worse. Treat exact matching as impossible and
   scoring as tolerance-based.
3. **The forecast horizon behaves like 84–86 days, not 90.** With 90 days, three samples (request_12, request_13,
   request_03) contradict the answers because a rent on day 87 is being counted; with 84–86 days all three reproduce.
   22/25 `earliest_date_for_full_payment` values reproduce at 84 days vs 19/25 at 90.
4. Recurring monthly items recur on the **same day of month** (DOM); weekly/10-day/14-day/21-day/5-day items recur at
   `last_date + median_gap`, and an occurrence that would land **exactly on `request_date` is skipped** for those periodic
   series (rent/monthly items on the request date ARE counted: request_19 rent Sep 4, request_08 education Feb 7).
5. Income: a `scheduled` "Next confirmed salary" row anchors a monthly series (same amount, same DOM). Without one, the
   regular salary series is inferred from history (modal DOM, last regular amount) and amended by employer messages
   (new amount, new date, first salary, resumed salary). Irregular freelance income (request_09) IS counted at its mean
   and median gap. Income is NOT counted when a message says the payout is pending/unconfirmed (request_10), when the
   contract ended (request_12), or when the last payroll row is a "Final employer payroll" (request_05). Commissions,
   bonuses, arrears, prize proceeds, refunds and the "Second household income" (request_13) are not counted.
6. Same-day ordering: on the salary day the salary is applied **before** (or net with) that day's debits — the trough is
   the day before payday (request_19 family_support 12,650 on Sep 15 is not reserved; request_25 transport on Mar 15 not
   reserved). Several residuals (request_02, _04, _18, _23) look like one extra periodic occurrence right after payday,
   which I could not turn into a consistent rule.
7. Plan selection follows the problem statement ranking literally and reproduces all 25 methods/plans (see §6).
   `affordability_status` follows the chosen method (full→affordable_now, installments/partial/full-with-changes→
   affordable_with_plan, wait→affordable_later, not_recommended→not_affordable).
8. Installment eligibility: `number_of_payments <= max_installment_months` (all supplied options are 28/30/31-day
   cadences, so payments ≈ months). Blank max → installments never eligible.
9. Spending changes: greedy, smallest monthly amount first, `reduce` preferred over `stop` when both are allowed,
   only events whose next occurrence precedes the failing trough are used, stop until the full payment today is safe,
   max 3. `reduce_to` amount = `minimum_allowed_amount`; event id = the **latest settled row** of that recurring series.

## 1. Per-sample reconstruction (uncapped = safe < requested)

`reserve` = balance − min − amount_safe_to_pay (what the organizers held back). `mine` = my 84-day/mean/DOM model.

| req | user | balance | min | headroom | actual safe | actual reserve | my reserve | Δ (actual−mine) | earliest actual / mine |
|---|---|---|---|---|---|---|---|---|---|
| 01 | user_01 | 58481.10 | 18000 | 40481.10 | 25256 (cap) | ≤15225 | 10240 | – | 2024-03-03 / same |
| 02 | user_02 | 60383889.20 | 29158400 | 31225489.20 | 17229139.2 | 13996350 | 12888724 | +1107626 (+8.6 %) | 2025-09-15 / same |
| 03 | user_03 | 5810300 | 2668700 | 3141600 | 873000 | 2268600 | 2169863 | +98737 (+4.6 %) | 2019-11-15 / same |
| 04 | user_04 | 52206950 | 30686600 | 21520350 | 8401800 | 13118550 | 10911064 | +2207486 (+20 %) | 2024-06-15 / same |
| 05 | user_05 | 46475.10 | 13100 | 33375.10 | 737 | 32638.10 | 32206 | +432 (+1.3 %) | – / – |
| 06 | user_06 | 1942.40 | 800 | 1142.40 | 603.3 | 539.10 | 591.59 | −52 (−9 %) | 2026-01-15 / same |
| 07 | user_07 | 218945.56 | 93000 | 125945.56 | 87170.56 | 38775 | 39708 | −933 (−2.3 %) | 2024-10-23 / same |
| 08 | user_08 | 1536.57 | 800 | 736.57 | 284.57 | 452 | 451.37 | +0.6 (+0.1 %) | 2025-04-15 / same |
| 09 | user_09 | 2231.10 | 600 | 1631.10 | 166.61 (cap) | ≤1464 | 161 | – | 2026-07-04 / same |
| 10 | user_10 | 750155 | 225400 | 524755 | 12700 | 512055 | 486245 | +25810 (+5.3 %) | – / – |
| 11 | user_11 | 63531795 | 34140600 | 29391195 | 12510645 | 16880550 | 17071328 | −190778 (−1.1 %) | 2025-07-15 / 05-15 (06-15 with base salary) |
| 12 | user_12 | 193089.89 | 43200 | 149889.89 | 65164 (cap) | ≤84726 | 77728 (84 d) / 89520 (90 d) | – | 2026-04-05 / same (84 d only) |
| 13 | user_13 | 2789.52 | 1300 | 1489.52 | 433.4 | 1056.12 | 998.72 | +57 (+5.7 %) | 2024-05-15 / same (84 d only) |
| 14 | user_14 | 3931.74 | 2200 | 1731.74 | 597.74 | 1134 | 1115.45 | +18.6 (+1.7 %) | – / – |
| 15 | user_15 | 1770.05 | 1200 | 570.05 | 83.05 | 487 | 504.85 | −17.9 (−3.7 %) | – / – |
| 16 | user_16 | 362370 | 122400 | 239970 | 122500 (cap) | ≤117470 | 100859 | – | 2023-08-12 / same |
| 17 | user_17 | 550379.58 | 166100 | 384279.58 | 243849.58 | 140430 | 143639 | −3209 (−2.2 %) | 2026-03-15 / 04-15 (near miss) |
| 18 | user_18 | 2486 | 1400 | 1086 | 462 | 624 | 539.95 | +84 (+15.6 %) | 2026-09-15 / same |
| 19 | user_19 | 199545 | 92800 | 106745 | 28820 | 77925 | 76722 | +1203 (+1.6 %) | 2024-09-15 / same |
| 20 | user_20 | 102609.05 | 64500 | 38109.05 | 5400 | 32709.05 | 29139.37 | +3570 (+12 %) | – / – |
| 21 | user_21 | 3911.35 | 1800 | 2111.35 | 1543.35 | 568 | 438.22 | +130 (+30 %) | 2026-04-15 / 04-03 (status flips) |
| 22 | user_22 | 1132.46 | 500 | 632.46 | 475.46 | 157 | 154.72 | +2.3 (+1.5 %) | 2025-01-15 / same |
| 23 | user_23 | 51957.90 | 27000 | 24957.90 | 9152 | 15805.90 | 14865.25 | +941 (+6.3 %) | 2025-07-15 / same |
| 24 | user_24 | 85045 | 51000 | 34045 | 13420 | 20625 | 20505.71 | +119 (+0.6 %) | – / – |
| 25 | user_25 | 32063050 | 23379100 | 8683950 | 1425000 | 7258950 | 7273189 | −14239 (−0.2 %) | – / – |

Worked arithmetic for the reference cases (all amounts home currency):

* **request_02** (IDR): reserve 13,996,350 = pending merchant debit 1,651,100 (settles Aug 8) + Aug 5–14 recurring debits:
  utilities ~2,035,831 (Aug 7), insurance 1,132,400 (Aug 8), education 3,040,000 (Aug 9), groceries ~1,908,881 (Aug 9),
  healthcare ~1,538,994 (Aug 11), transport ~1,211,968 (Aug 12), cloud 369,550 (Aug 13) = 12,888,724 with means; the
  fixed-amount items are exact, the four variable ones need 7,803,300 in total (mine 6,695,674). Entertainment (Aug 15,
  salary day) would add 1,298,172 → 14,186,896 (closer, −1.4 %) but the same rule breaks request_19. Salary: no
  scheduled row; message_01 says monthly salary rises to 42,750,000 from 2025-08-15 → used (with the historical
  33,345,000 the earliest full-payment date would be 2025-10-15, actual 2025-09-15).
* **request_03** (IDR): reserve 2,268,600 = pending pharmacy 95,000 + rent 1,140,000 (Sep 4) + utilities ~284,388 (Sep 8)
  + groceries ~193,165 (Sep 8) + streaming 117,800 (Sep 10) + cloud 20,900 (Sep 14) + shopping ~168,698 (Sep 14) +
  dining ~149,913 (Sep 14) = 2,169,863. Salary series = "Payroll credit" on the 15th (4,365,000); the arrears row
  (Aug 20) and the blank Aug 31 net-salary row (image_01 = 4,365,000) are already settled.
* **request_08** (EUR): 452 = education 89 (Feb 7 = request date) + debt 177 + music 14 + delivery 24 + dining ~50.84
  + groceries ~59.04 + transport ~37.49 = 451.37. Salary reduced to 1,422.85 by message (Feb 15).
* **request_14** (EUR): 1,134 = utilities ~148 + healthcare ~92 + debt 350 + cloud 14 + shopping ~129 + family 226 +
  groceries ~105 + transport ~51 = 1,115.45 (salary 2,717 resumes Aug 15 per message).
* **request_15** (EUR): 487 ≈ utilities ~86 + education 159 + debt 84 + music 11 + groceries ~60 (Jan 13 only; the
  Jan 6 request-date occurrence is skipped) + transport ~32 ×2 + dining ~41 = 504.85. First salary 1,661 on Jan 15 (message).
* **request_19** (INR): 77,925 ≈ rent 36,100 (Sep 4) + utilities ~5,956 + groceries ~4,699 (Sep 10; the last grocery row is
  the image_04 order 2,854 on Sep 3) + healthcare ~8,809 + debt 11,850 + transport ~3,080 + cloud 395 + shopping ~5,834
  = 76,722. family_support 12,650 on Sep 15 (payday) is NOT reserved.
* **request_20** (INR): 32,709.05 = pending order 4,470 + telecom bill 704.05 (image_05; the ".05" proves the bill amount
  is used, and it is the "due till 06-Feb" figure, not 822.05) + education 8,740 (Feb 7) + healthcare ~6,337 + cloud 365
  + groceries ~3,701 + transport ~2,675 + entertainment ~2,148 = 29,139.37 (+3,570 unexplained). Pending refund 8,640 ignored.
* **request_21** (USD): 568 vs pending fuel 53 + utilities ~121 + groceries ~84 + streaming 47 + cloud 11 + shopping ~122
  = 438.22. The missing ~130 ≈ groceries 84 + transport 41 that fall on Apr 16 (day after payday). This is the one sample
  whose status depends on ~2 % of the requested amount.
* **request_25** (IDR): 7,258,950 vs utilities ~1,323,655 (Mar 6) + insurance 904,400 + streaming 573,800 + groceries
  ~1,199,175 + transport ~592,511 (Mar 10) + cloud 126,350 + shopping ~1,059,029 + dining ~1,034,677 (Mar 13 only; Mar 6
  request-date occurrence skipped) + entertainment ~459,592 = 7,273,189 (−0.2 %). USD salary 1,800 × 15,833.33
  (2024-03-15 USD→IDR) = 28,499,994 on Mar 15. Failed subscription debit ignored.
* **request_05**: "Final employer payroll" ⇒ no income; reserve 32,638 ≈ 84 days of expenses (mine 32,206).
* **request_10**: message_07 (payout pending, can change) ⇒ no income; reserve 512,055 sits between my 84-day (486,245)
  and 90-day (566,121) totals.
* **request_12**: message_09 (contract ended) ⇒ no income. 90-day reserve 89,520 > the 84,726 the answer allows; 84-day
  reserve 77,728 fits. The recommended installment plan (3 × 22,590.19 ending Jun 20) additionally requires reserve ≤ 82,120.
* **request_13**: scheduled salary 1,343.54 recurs; second household income ignored; expenses exceed income so the balance
  drifts down; earliest May 15 only holds if the Jun 2 rent (day 87) is outside the window.

## 2. Recurrence and forecasting rules that fit best

* Group settled home-currency-converted debits by `category` (event_type merged). ≥3 rows with a regular gap ⇒ recurring.
  Observed cadences: monthly (gaps 28–31), 5, 7, 10, 14, 21 days.
* Amount forecast = mean of the history (rounded values used by the organizers are unknowable). Foreign rows convert with
  the `settlement_date` rate in the stated direction (request_25 USD salary).
* Monthly items: next = same day-of-month after the last row, repeated monthly; include an occurrence on the request date.
* Periodic items: next = last + median gap, repeated; skip an occurrence equal to the request date (request_15, _23, _25).
* Blank-amount rows take the image amount and stay in history / future as their status says (request_17 groceries 41,272
  settled; request_16 rent balance 100,000 scheduled Aug 16; request_20 bill 704.05 pending Feb 9).
* Known future rows: `pending`/`scheduled` debits at settlement_date (request_02 1,651,100; request_04 school fee
  1,704,300; request_24 insurance 1,830 in addition to the recurring 2,510). Pending credits/refunds (request_20),
  `failed` (request_05, _25), `cancelled` (request_06), `unrealized` (request_21, _22) ignored. Settled refund pairs and
  cancelled-then-settled pairs are already in the balance (request_01).
* Message effects seen: salary raise (request_02, used), salary date change (request_07, used), salary cut (request_08,
  already in history), temporary pay continues (request_06), salary resumes on date (request_14), first salary on date
  (request_15), bonus pending (request_04, ignored), payout pending (request_10, income dropped), contract ended
  (request_12, income dropped), rent +12 % from next payment (request_16, applied to the recurring rent), commission
  unconfirmed (request_11, commissions dropped; the stated base 38,760,000 seems NOT to replace the historical
  23,256,000 — see §7), internal transfer (request_18, no effect), unrealized gains (request_22), prize pending
  (request_23, ignored), prize already paid (request_24).
* Horizon: 84 days from request_date inclusive reproduces everything a 90-day horizon breaks and nothing else; 87+ breaks
  request_12/13. Use 84 (document as an assumption; the statement says 90).

## 3. `earliest_date_for_full_payment`

First date D in the window such that paying `requested_amount` on D keeps the projected balance ≥ min on every day from D
to the end of the window (no spending changes). Equals request_date when safe ≥ requested (request_01, _09, _12, _16);
otherwise it is always a payday in the samples (15th, or the message-moved 23rd for request_07 → Oct 23 is the 2nd
payday because one salary is not enough). Empty when no such date (request_05, _10, _14, _15, _20, _24, _25). It is
independent of payment preferences (request_12: earliest = request date, method installments).

## 4. Option eligibility and plan strings

* `full_payment`: eligible iff in `payment_methods_user_will_consider`; safe iff safe ≥ requested.
* `installments`: option must be in the user's methods and `number_of_payments <= max_installment_months`
  (request_02 3≤7, request_07 3≤12, request_12 3≤11 while 21 fails, request_17 3≤3, request_22 3≤6, request_19 2≤2
  eligible but beaten). Payments on `first_payment_date + k*payment_frequency_days`, amount = `payment_amount`
  (string exactly as in the CSV: `15952906.67`, `68432`, `22590.19`). Each payment inside the window is checked against
  the projection. Last payment ≤ desired date in all samples.
* `partial_payment`: `allows_partial_payment` true AND method accepted AND 0 < safe < requested AND earliest ≤ desired.
  Plan `request_date:safe|earliest:requested−safe` (request_19: `2024-09-04:28820|2024-09-15:10840`). request_18 shows
  that `allows_partial_payment=false` blocks it even though the user accepts partial and the numbers fit.
* `wait`: user accepts full_payment and an earliest date exists; plan `earliest:requested`. In every sample the
  earliest date equals or precedes the desired date; when it is later (request_06/11/21) the samples use spending
  changes instead.
* `not_recommended`: plan `none`, earliest empty (no sample has not_recommended with a non-empty earliest).
* Ranking check (statement order: completes by deadline → no spending changes → lowest total paid → earliest start →
  fewest payments → lowest option id) reproduces all 25 choices, e.g. request_19 partial (39,660) beats option_53
  (41,246.40); request_06/11/21 full+changes beats wait (misses deadline).
* Number formatting in plans/explanations: integers without decimals, otherwise exactly 2 decimals (`620.40`, `996.60`,
  `3246.10`, `23.50`). `amount_safe_to_pay` is a plain float (`17229139.2`, `603.3`, `12510645`).

## 5. Spending changes

Only used to make **full payment today** safe when the no-change plans miss the deadline (3 samples). Candidates: latest
row of a recurring series whose flexibility allows the action and whose category is in the matching user list;
`reduce_to` uses `minimum_allowed_amount` (665950, 23.50); stop/reduce never on the same event.

* request_06: gap 17.10 → `stop:event_476` (streaming 19).
* request_11: gap 599,355 → `reduce_to:event_989:665950` (dining, saves 684,072 on May 14). cloud_storage (168,150,
  stoppable, user willing) not used — consistent only if its next occurrence (Apr 14 + 31 = May 15) is not before the
  trough, or if candidates are tried in an order that reaches dining first.
* request_21: gap 31.05 → `stop:event_1815` (cloud 11) + `reduce_to:event_1816:23.50` (streaming, 47→23.5) = 34.50.
  A single `reduce` of shopping (saves 72.81) or `stop` of streaming (47) would have sufficed, so the reference is a
  greedy accumulation over candidates ordered by amount ascending (11, 47, 122…) with reduce preferred over stop; output
  order = application order.

## 6. Explanation templates (verbatim patterns)

Amounts: currency code + thousands separators, 2 decimals only when fractional. Dates: `D Month YYYY` (no leading zero).

* full now (2 variants): `Pay {CUR} {amt} today. This leaves at least {CUR} {min} available over the next 90 days.` /
  `Pay {CUR} {amt} today. This keeps the {CUR} {min} minimum available over the next 90 days.`
* installments: `Use {n} installments of {CUR} {amt}, starting {date}. This leaves at least {CUR} {min} available.`
* partial: `Pay {CUR} {a} today and the remaining {CUR} {b} on {date}. This completes the full request and keeps the {CUR} {min} minimum protected.`
* wait (2 variants): `Pay {CUR} {amt} in full on {date}. Paying earlier would take the balance below the {CUR} {min} minimum.` /
  `Wait until {date}, then pay {CUR} {amt} in full. Paying sooner would put the {CUR} {min} minimum at risk.`
* full with changes: `Stop the {desc}, then pay …` / `Reduce the {desc} to {CUR} {amt}, then pay {CUR} {req} today. This leaves at least {CUR} {min} available.` /
  `Stop the {desc1} and reduce the {desc2} to {CUR} {amt}, then pay …` (desc = event description, lower-cased).
* not_recommended A: `Do not make this payment by {desired date}. None of the available options keeps the {CUR} {min} minimum protected.`
  (request_05, _10, _15, _20, _25)
* not_recommended B: `Do not proceed with the {CUR} {req} request. Although {CUR} {safe} is available today, the full amount cannot be completed safely within 90 days.`
  (request_14, _24: allows_partial = true, partial is the only accepted method, safe > 0, no supplied option acceptable)

## 7. Rules the organizers appear to follow (implementable list)

1. Balance projection per day from request_date over an 84-day window (inclusive), starting at
   `current_available_balance`; safe amount = max(0, min(requested, min_t(balance_t) − min_balance)).
2. Debits counted: pending/scheduled debits at settlement_date (blank amounts from images); recurring series forecast
   at the historical mean; monthly on the same DOM (request-date occurrence included), shorter periods at last+gap
   (request-date occurrence skipped).
3. Credits counted: scheduled salary rows (recurring monthly from that row), otherwise the regular salary series from
   history amended by employer messages (amount/date/first/resume). Irregular but regular-cadence freelance income
   counts at mean/median gap. Not counted: pending/unconfirmed payouts, ended contracts, "Final employer payroll",
   bonuses, commissions, arrears, refunds, prizes, unrealized investment values, failed/cancelled rows, credits linked
   to a same-source reversal. Salary and same-day debits: salary first.
4. Foreign rows converted with the settlement-date rate in the stated direction.
5. earliest date = first D with a safe single full payment for the rest of the window; blank if none.
6. Candidate plans: full (if accepted); installments (accepted, n_payments ≤ max months, each payment safe); partial
   (allowed, accepted, 0<safe<req, earliest ≤ desired, two payments); wait (accepts full, earliest exists); full-today
   with ≤3 greedy spending changes (only when needed); fallback not_recommended.
7. Rank by: completes by desired date, no spending changes, lowest total paid, earliest start, fewest payments, lowest
   option id. Status from the chosen method.
8. Output formatting as in §4/§6.

## 8. Unresolved / ambiguous

* Variable-expense amounts (hidden nominal values) — irreducible noise of a few % of the reserve; flips request_21's
  status and request_17's earliest date in my model.
* request_11: message base salary 38,760,000 vs history 23,256,000 — earliest 2025-07-15 is only approachable with the
  historical base (my model gives Jun 15 with it, May 15 with the message amount).
* Same-day debit/credit ordering on payday: salary-first fits request_19/_25; four other residuals hint at an extra
  periodic occurrence after payday. Not modelled.
* Horizon 84–86 days (any of these fit; 84 = 12 weeks chosen).
* Spending-change candidate order (amount ascending vs. event id) — both fit request_21; cloud in request_11 is
  explained only by "next occurrence not before the trough" or by an order that tries dining first.
* `wait` when earliest > desired and no change helps: no sample; suggest affordable_later + wait (ranking rule 1 is a
  rank, not a filter).
* User accepts only partial/installments while safe ≥ requested and no eligible option: no sample.
