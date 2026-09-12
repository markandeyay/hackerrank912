# 4 — Distribution and outlier review of `output.csv` (250 rows)

Script: `code/notes/improve/4_outliers.py` (read-only against the engine; rebuilds every state with the cached
model evidence, checks `output.csv` against the engine, and dumps every flagged row). Every flagged row was also
run through `.venv/Scripts/python code/debug_request.py <id> --llm --days 90`; the debug output agrees with the
dumps and with `output.csv` for all of them (no `MISMATCH` flag was raised, i.e. output.csv == engine for all 250).

## 1. Distribution

### Status / method mix

| affordability_status | output (250) | samples (25) |
|---|---|---|
| affordable_now | 58 (23%) | 3 (12%) |
| affordable_with_plan | 85 (34%) | 9 (36%) |
| affordable_later | 61 (24%) | 6 (24%) |
| not_affordable | 46 (18%) | 7 (28%) |

| recommended_payment_method | output (250) | samples (25) |
|---|---|---|
| full_payment | 70 (28%) | 6 (24%) |
| installments | 63 (25%) | 5 (20%) |
| partial_payment | 10 (4%) | 1 (4%) |
| wait | 61 (24%) | 6 (24%) |
| not_recommended | 46 (18%) | 7 (28%) |

Status/method pairs are exactly the six allowed ones: later/wait 61, now/full 58, plan/full(+changes) 12,
plan/installments 63, plan/partial 10, not_affordable/not_recommended 46. No illegal pair.

### Breakdown of the 250 (method columns: full / partial / instal / wait / not_rec)

| driver | value | n | full | partial | instal | wait | not_rec |
|---|---|---|---|---|---|---|---|
| request_type | debt_repayment | 28 | 13 | 1 | 5 | 4 | 5 |
| | education | 28 | 8 | 2 | 5 | 7 | 6 |
| | emergency_expense | 27 | 9 | 1 | 6 | 8 | 3 |
| | family_transfer | 28 | 9 | 0 | 8 | 8 | 3 |
| | housing | 28 | 8 | 2 | 7 | 5 | 6 |
| | investment | 28 | 9 | 0 | 7 | 4 | 8 |
| | other | 27 | 2 | 1 | 8 | 9 | 7 |
| | purchase | 28 | 5 | 2 | 9 | 8 | 4 |
| | travel | 28 | 7 | 1 | 8 | 8 | 4 |
| currency | EUR | 54 | 12 | 1 | 22 | 12 | 7 |
| | IDR | 50 | 13 | 3 | 13 | 12 | 9 |
| | INR | 60 | 19 | 3 | 8 | 17 | 13 |
| | USD | 39 | 12 | 2 | 7 | 10 | 8 |
| | ZAR | 47 | 14 | 1 | 13 | 10 | 9 |
| methods accepted | full | 54 | 31 | 0 | 0 | 22 | 1 |
| | full+instal | 33 | 8 | 0 | 0 | 20 | 5 |
| | full+partial | 38 | 21 | 0 | 0 | 12 | 5 |
| | full+partial+instal | 23 | 10 | 0 | 0 | 7 | 6 |
| | instal only | 38 | 0 | 0 | 33 | 0 | 5 |
| | partial only | 16 | 0 | 1 | 0 | 0 | 15 |
| | partial+instal | 48 | 0 | 9 | 30 | 0 | 9 |
| allows_partial | false | 170 | 46 | 0 | 48 | 45 | 31 |
| | true | 80 | 24 | 10 | 15 | 16 | 15 |
| days to desired | 0-30 | 55 | 34 | 0 | 0 | 5 | 16 |
| | 31-60 | 56 | 18 | 7 | 8 | 7 | 16 |
| | 61-90 | 139 | 18 | 3 | 55 | 49 | 14 |

Plausibility:

* Method eligibility is respected everywhere: no `full_payment`/`wait` for users who do not accept full payment,
  no `installments` for users without it, no `partial_payment` when the request forbids it.
* Users who accept full payment (148 rows) almost never end in `not_recommended` (17, all with no safe full date in
  the window); users who accept only partial (16) are almost always `not_recommended` (15) because partial needs
  `0 < safe < requested` *and* `allows_partial_payment` *and* an earliest date before the deadline — three
  independent conditions. `full+installments` users get `wait` 20/33 times because waiting for payday is cheaper
  than any financed option (ranking rule 3) — the sample set shows the same (samples 03, 08, 13, 22).
* Short deadlines (0-30 days) are dominated by `full_payment` (34) and `not_recommended` (16): no installment
  option can complete in 30 days and `wait` past a 1-13 day deadline is rare. 61-90 day requests carry almost
  all installments (55/63) and waits (49/61), which is where the 28/30/31-day cadences fit.
* Compared with the 25 samples the output has more `affordable_now` (23% vs 12%) and fewer `not_affordable`
  (18% vs 28%); with n=25 each sample percentage has a ±9-10 pp standard error, so both differences are within
  noise. Currency and request type are close to uniform by construction (the generator assigns ~28 per type).

## 2. Flagged rows (65 of 250) and classification

Checks B (affordable_now with post-payment trough within 1 % of the minimum or headroom < requested),
C (wait whose earliest date is not an income day), D (installments chosen while full was safe and accepted; full
chosen while a cheaper safe plan exists), E (earliest date neither request date nor income day) and G (partial:
second payment not on an income day or after the deadline) flagged **zero** rows. Every earliest date in the file is
either `request_date` or a projected salary/income day; all 10 partial plans put the second payment on a payday on
or before the deadline.

| flag | rows | verdict |
|---|---|---|
| A not_affordable with headroom > 2× requested | 3 (47, 159, 251) | CORRECT (see below) |
| F amount_safe_to_pay = 0 | 2 (64, 97) | CORRECT |
| H spending changes not the smallest sufficient set | 17 | CORRECT by policy (sample 21 confirms greedy) |
| I affordable_later with earliest after the deadline | 3 (78, 114, 120) | policy question, see §3 |
| J salary history but no projected income | 21 | CORRECT (messages / final-payroll rows) |
| K forecast uses foreign-currency salary/event | 26 | CORRECT (conversions verified) |
| output.csv vs engine mismatch | 0 | — |

### A — not_affordable despite large headroom

* **request_47** (IDR, headroom 82.9 M vs requested 38.1 M, methods full+installments): the user's 20 settled
  salary rows are weekly gig payouts (RideGrid). `message_34` (service provider, 2025-05-04) says the next payout is
  still pending and not withdrawable — the same template as sample 10, whose reference answer suppresses the gig
  stream and returns `not_affordable`. Without income the 84-day debits eat the headroom; safe = 5.1 M, no
  earliest date, the 3 installment options fail. CORRECT (evidence-driven, matches sample 10).
* **request_159** (ZAR, headroom 31.6 k vs 13.4 k, full+partial): identical situation (ShiftPay payout pending,
  `message_123`). Safe 1,655, no earliest. CORRECT (same rule as sample 10).
* **request_251** (EUR, headroom 3,349 vs 1,514, methods partial+installments, max 11 months): the full amount is
  safe today (safe = requested, earliest = request_date) but the user does not accept full payment, partial
  requires `safe < requested`, and the only installment option has 15 payments > 11. No eligible plan →
  `not_recommended`/`not_affordable` with `earliest_date = 2025-05-03` reported. CORRECT under the statement
  ("not_recommended is the fallback when no safe eligible payment is available") and under mismatches.md
  assumption 8 (samples 14/24 map not_recommended → not_affordable). It is the "no sample" corner of
  04_sample_rules §8; the label is semantically odd but there is no better-supported alternative.

### F — amount_safe_to_pay = 0

* **request_64** (INR, headroom 62,473): pending `event_6033` "Large grocery tax invoice" has a blank amount; image_10
  reads 79,679.26 (model and manual transcription agree, itemised total). That single pending debit on 06-10 exceeds
  the headroom before the 06-15 salary → trough −931 → safe 0; installments from 06-19 are safe. CORRECT.
* **request_97** (INR, headroom 8,866, installments only): 03-06..03-14 debits (utilities 2,078, groceries 1,438,
  loan 3,531, music 219, fuel 810, dining 1,167 = 9,243) exceed the headroom before the 03-15 salary, so the balance
  dips to 29,322 < 29,700 even with no payment. Safe 0; installments starting 03-19 with two changes. CORRECT.

### H — spending changes (17 rows: 55, 88, 89, 93, 97, 99, 100, 105, 107, 109, 125, 128, 145, 148, 150, 152, 225)

In all 17 a smaller (usually single) change would also make the payment safe, e.g. request_55 `stop:event_5101`
alone vs the chosen `stop:event_5102|stop:event_5101`. The engine applies the documented greedy rule (cheapest series
first, add until safe). I re-ran the subset test on the samples: in **sample 21** a single change
(`reduce_to:event_1854:41` or `reduce_to:event_1817:49.60`) suffices, yet the reference answer is the greedy pair
`stop:event_1815|reduce_to:event_1816:23.50` — exactly what the engine produces. So the greedy rule is the one the
organizers use and these 17 rows are CORRECT by policy. All change ids are the latest settled row of their series
(0 mismatches), every set has ≤ 3 entries, and each added change raises the failing trough.

### I — affordable_later past the deadline (3 rows)

request_78, 114, 120: desired date is the 14th, payday the 15th, so `wait` completes one day late. In all three
`wait` is the only candidate (78: full+partial but the request forbids partial; 114/120: full only). See §3.

### J — no projected income despite salary history (21 rows)

| suppressing note | rows | evidence |
|---|---|---|
| gig payout pending (service-provider message) | 27, 47, 59, 123, 159, 199, 215 | same template as sample 10 (reference: income not counted) |
| income ended per message | 29, 61, 75, 111, 133, 165, 201, 213, 237, 241, 246, 265 | employer messages "seasonal contract has ended" / "employment has ended" |
| last payroll is final | 174, 255 | latest settled salary row is "Final employer payroll" (sample 05 rule) |

All CORRECT; each has an explicit message or terminal payroll row.

### K — foreign-currency streams (26 rows)

`exchange_rates.csv` carries one constant rate per pair (USD→INR 83.33, USD→IDR 15,833.33, USD→EUR 0.92,
EUR→USD 1.09, EUR→ZAR 20). Every scheduled foreign salary converts exactly (e.g. request_39: 3,048 USD × 83.33 =
253,989.84 INR; request_41: 2,688 USD × 15,833.33 = 42,559,991.04 IDR; request_79: 1,428 USD × 0.92 = 1,313.76 EUR;
request_257: 1,793 EUR × 1.09 = 1,954.37 USD), and history-derived foreign salaries (48, 64, 71, 84, 98, 113, 125,
153, 169, 173, 183, 184, 214, 235, 245, 263, 267, 274) equal the modal history amount × the pair rate. request_78 has
one historical foreign row and nothing in the window. All CORRECT.

## 3. Summary

* Rows flagged: 65 / 250 (many by the informational J/K checks). Rows classified as BUG: **0**.
* `output.csv` is byte-identical to what the engine produces for all 250 rows.
* Every earliest date is a payday or the request date; every partial second payment is on a payday before the
  deadline; the ranking never picks installments over an accepted safe full payment; no affordable_now row is within
  1 % of the minimum after payment.
* Two policy points, no engine change proposed:
  1. **`wait` one day past the deadline (3 rows: 78, 114, 120).** The statement says a safe recommendation must
     "complete the full request by its deadline", which read literally makes these `not_recommended`/`not_affordable`
     with `earliest_date` still reported. The engine follows mismatches.md assumption 9 (rule 1 ranks, it does not
     filter). If the literal reading is adopted, the smallest change is in `planner.decide`: skip the `wait`
     candidate (and installment candidates) when `completes_by_deadline` is false — a one-line filter, no
     per-request logic. Expected effect: 3 rows move from affordable_later/wait to not_affordable/not_recommended.
     No sample decides this either way (04_sample_rules §8), so it is a coin flip; leaving it is defensible because
     the explanation states the date and the user can still act.
  2. **not_affordable while the amount is safe today (request_251).** Consistent with samples 14/24 and the
     statement's fallback wording; no change proposed.
